"""Guest personalisation, A/B testing and the additive schema upgrade."""

import pytest
from conftest import auth
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings
from app.db import init_db
from app.experiments import CONTROL, TREATMENT, assign_variant, two_proportion_z_test, unit_id

SESSION = {"X-Session-Id": "browser-abc"}


@pytest.fixture()
def ab_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "ab_control_share", 0.5)
    yield
    # monkeypatch restores the setting


def view(client, product_id, session="browser-abc", headers=None):
    r = client.post("/api/v1/events", json={"event_type": "view", "product_id": product_id, "session_id": session},
                    headers=headers or {})
    assert r.status_code == 201


# --------------------------------------------------------------------------- #
# Guest personalisation
# --------------------------------------------------------------------------- #
def test_guest_gets_recommendations_from_their_session(client):
    assert client.get("/api/v1/recommendations", headers=SESSION).json()["strategy"] == "popular"
    view(client, "P1")
    r = client.get("/api/v1/recommendations", headers=SESSION).json()
    assert r["strategy"] == "session_similarity"
    assert [i["product"]["id"] for i in r["items"]] == ["P2", "P5"]
    # another browser without that history still sees trending
    other = client.get("/api/v1/recommendations", headers={"X-Session-Id": "someone-else"}).json()
    assert other["strategy"] == "popular"


def test_guest_history_carries_over_after_sign_up(client):
    view(client, "P3")
    token = client.post("/api/v1/auth/register", json={"email": "g@example.com", "password": "password123",
                                                       "display_name": "G"}).json()["access_token"]
    r = client.get("/api/v1/recommendations", headers={**auth(token), **SESSION}).json()
    assert r["strategy"] == "session_similarity"
    assert [i["product"]["id"] for i in r["items"]] == ["P4"]


def test_impressions_record_the_session(client):
    view(client, "P1")
    client.get("/api/v1/recommendations", headers=SESSION)
    from app.db import Impression, SessionLocal

    with SessionLocal() as db:
        sessions = {i.session_id for i in db.query(Impression).all()}
    assert sessions == {"browser-abc"}


# --------------------------------------------------------------------------- #
# A/B testing
# --------------------------------------------------------------------------- #
def test_assignment_is_stable_and_respects_the_split():
    units = [unit_id(None, f"s{i}") for i in range(4000)]
    first = [assign_variant(u, "exp", 0.5) for u in units]
    assert first == [assign_variant(u, "exp", 0.5) for u in units]  # stable
    share = first.count(CONTROL) / len(first)
    assert 0.46 < share < 0.54
    assert all(assign_variant(u, "exp", 0.0) == TREATMENT for u in units[:50])
    assert unit_id(7, "s1") == "user:7" and unit_id(None, None) is None


def test_two_proportion_z_test_matches_hand_calculation():
    # p1 = 0.10, p2 = 0.20, pooled 0.15: z = 0.1 / sqrt(0.15 * 0.85 * 0.02) = 1.9803
    z, p = two_proportion_z_test(10, 100, 20, 100)
    assert z == pytest.approx(1.9803, abs=1e-3)
    assert p == pytest.approx(0.0477, abs=1e-3)
    assert two_proportion_z_test(0, 0, 1, 10) == (None, None)


def _session_in(variant: str, prefix: str) -> str:
    settings = get_settings()
    return next(f"{prefix}{i}" for i in range(1000)
                if assign_variant(unit_id(None, f"{prefix}{i}"), settings.ab_experiment, 0.5) == variant)


def test_control_group_gets_popularity_even_with_history(client, ab_on):
    control = _session_in(CONTROL, "c")
    treatment = _session_in(TREATMENT, "t")
    for s in (control, treatment):
        view(client, "P1", session=s)
    c = client.get("/api/v1/recommendations", headers={"X-Session-Id": control}).json()
    t = client.get("/api/v1/recommendations", headers={"X-Session-Id": treatment}).json()
    assert (c["variant"], c["strategy"]) == ("control", "popular")
    assert (t["variant"], t["strategy"]) == ("treatment", "session_similarity")


def test_ab_results_report_ctr_and_conversion_per_variant(client, ab_on):
    control = _session_in(CONTROL, "cc")
    treatment = _session_in(TREATMENT, "tt")
    view(client, "P1", session=treatment)
    c = client.get("/api/v1/recommendations?k=2", headers={"X-Session-Id": control}).json()
    t = client.get("/api/v1/recommendations?k=2", headers={"X-Session-Id": treatment}).json()
    # treatment clicks one recommendation and adds it to the bag; control does nothing
    item = t["items"][0]
    client.post("/api/v1/events", json={"event_type": "click", "product_id": item["product"]["id"],
                                        "impression_id": item["impression_id"], "session_id": treatment})
    client.post("/api/v1/events", json={"event_type": "add_to_cart", "product_id": item["product"]["id"],
                                        "session_id": treatment})

    ab = client.get("/api/v1/analytics/overview").json()["ab_test"]
    by = {v["variant"]: v for v in ab["variants"]}
    assert ab["enabled"] is True and ab["control_share"] == 0.5
    assert by["control"] == {"variant": "control", "units": 1, "impressions": len(c["items"]), "clicks": 0,
                             "ctr": 0.0, "converted_units": 0, "conversion_rate": 0.0}
    assert by["treatment"]["clicks"] == 1 and by["treatment"]["converted_units"] == 1
    assert by["treatment"]["ctr"] == pytest.approx(1 / len(t["items"]), abs=1e-4)
    assert ab["ctr_lift"] is None  # control CTR is 0, so lift is undefined


def test_ab_off_by_default(client):
    r = client.get("/api/v1/recommendations").json()
    assert r["variant"] is None
    assert client.get("/api/v1/analytics/overview").json()["ab_test"]["enabled"] is False


# --------------------------------------------------------------------------- #
# Schema upgrade for databases created before these columns existed
# --------------------------------------------------------------------------- #
def test_init_db_adds_new_columns_to_an_existing_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE impressions (id VARCHAR(36) PRIMARY KEY, request_id VARCHAR(36), user_id INTEGER, "
            "surface VARCHAR(30), model_version VARCHAR(64), product_id VARCHAR(20), position INTEGER, "
            "created_at DATETIME)"
        ))
        conn.execute(text("INSERT INTO impressions (id, request_id, surface, model_version, product_id, position) "
                          "VALUES ('i1', 'r1', 'home', 'v1', 'P1', 1)"))
    init_db(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("impressions")}
    assert {"session_id", "variant"} <= columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM impressions")).scalar() == 1  # data kept
    init_db(engine)  # running it again is a no-op
