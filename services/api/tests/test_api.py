from conftest import auth


def register(client, email="new@example.com"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "display_name": "New"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def demo_token(client):
    r = client.post("/api/v1/auth/demo", json={"dataset_user_id": "AUSER1"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_products_list_search_filter_and_sort(client):
    r = client.get("/api/v1/products").json()
    assert r["total"] == 5 and [p["id"] for p in r["items"]][:2] == ["P5", "P1"]  # by popularity
    assert {p["id"] for p in client.get("/api/v1/products?q=zelda").json()["items"]} == {"P1", "P2"}
    assert {p["id"] for p in client.get("/api/v1/products?platform=PC").json()["items"]} == {"P3", "P4"}
    prices = [p["price"] for p in client.get("/api/v1/products?sort=price_desc").json()["items"]]
    assert prices[0] == 199.0 and prices[-1] is None
    assert client.get("/api/v1/products?page_size=1000").status_code == 422


def test_images_hidden_by_default(client):
    assert all(p["image_url"] is None for p in client.get("/api/v1/products").json()["items"])


def test_product_detail_similar_and_404(client):
    p = client.get("/api/v1/products/P1").json()
    assert p["title"].startswith("Zelda") and p["categories"] == ["Video Games", "Nintendo Switch"]
    assert [s["id"] for s in client.get("/api/v1/products/P1/similar").json()] == ["P2", "P5"]
    r = client.get("/api/v1/products/NOPE")
    assert r.status_code == 404 and r.json()["error"]["code"] == 404


def test_register_login_and_validation(client):
    register(client)
    assert client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "password123",
                                                      "display_name": "x"}).status_code == 409
    assert client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": "wrong-pass"}).status_code == 401
    ok = client.post("/api/v1/auth/login", json={"email": "NEW@example.com", "password": "password123"})
    assert ok.status_code == 200 and ok.json()["user"]["display_name"] == "New"
    bad = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "short", "display_name": ""})
    assert bad.status_code == 422 and len(bad.json()["error"]["details"]) == 3
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers=auth("garbage")).status_code == 401


def test_demo_user_gets_precomputed_recommendations_with_reasons(client):
    personas = client.get("/api/v1/auth/demo-users").json()
    assert personas[0]["dataset_user_id"] == "AUSER1" and personas[0]["reviews"] == 1
    token = demo_token(client)
    r = client.get("/api/v1/recommendations", headers=auth(token)).json()
    assert r["strategy"] == "precomputed" and r["model_version"] == "hybrid-test"
    assert [i["product"]["id"] for i in r["items"]] == ["P2", "P5"]
    assert r["items"][0]["reasons"][0]["type"] == "also_reviewed_with"
    assert [h["product"]["id"] for h in client.get("/api/v1/me/history", headers=auth(token)).json()] == ["P1"]


def test_guest_gets_popular(client):
    r = client.get("/api/v1/recommendations?k=3").json()
    assert r["strategy"] == "popular" and [i["product"]["id"] for i in r["items"]] == ["P5", "P1", "P3"]
    assert r["items"][0]["reasons"][0]["type"] == "trending"


def test_new_user_cold_start_from_session_events(client):
    token = register(client)
    assert client.get("/api/v1/recommendations", headers=auth(token)).json()["strategy"] == "popular"
    assert client.post("/api/v1/events", json={"event_type": "view", "product_id": "P1"},
                       headers=auth(token)).status_code == 201
    r = client.get("/api/v1/recommendations", headers=auth(token)).json()
    assert r["strategy"] == "session_similarity"
    assert [i["product"]["id"] for i in r["items"]] == ["P2", "P5"]  # similar to P1, never P1 itself
    assert "Zelda Breath of the Wild" in r["items"][0]["reasons"][0]["text"]


def test_wishlist_flow_excludes_wishlisted_from_recs(client):
    token = demo_token(client)
    assert client.post("/api/v1/me/wishlist", json={"product_id": "P2"}, headers=auth(token)).status_code == 201
    assert [p["id"] for p in client.get("/api/v1/me/wishlist", headers=auth(token)).json()] == ["P2"]
    recs = client.get("/api/v1/recommendations", headers=auth(token)).json()
    assert "P2" not in [i["product"]["id"] for i in recs["items"]]
    assert client.delete("/api/v1/me/wishlist/P2", headers=auth(token)).status_code == 200
    assert client.delete("/api/v1/me/wishlist/P2", headers=auth(token)).status_code == 404
    assert client.post("/api/v1/me/wishlist", json={"product_id": "NOPE"}, headers=auth(token)).status_code == 404


def test_event_validation(client):
    assert client.post("/api/v1/events", json={"event_type": "teleport"}).status_code == 422
    assert client.post("/api/v1/events", json={"event_type": "search"}).status_code == 422
    assert client.post("/api/v1/events", json={"event_type": "view", "product_id": "NOPE"}).status_code == 404
    assert client.post("/api/v1/events", json={"event_type": "click", "impression_id": "missing"}).status_code == 422


def test_impressions_and_clicks_give_ctr_per_model_version(client):
    token = demo_token(client)
    recs = client.get("/api/v1/recommendations", headers=auth(token)).json()
    first = recs["items"][0]
    client.post("/api/v1/events", json={"event_type": "click", "product_id": first["product"]["id"],
                                         "impression_id": first["impression_id"]}, headers=auth(token))
    client.get("/api/v1/recommendations")  # guest: popular-v1 impressions
    stats = {s["model_version"]: s for s in client.get("/api/v1/analytics/overview").json()["recommendation_stats"]}
    assert stats["hybrid-test"] == {"model_version": "hybrid-test", "impressions": 2, "clicks": 1, "ctr": 0.5}
    assert stats["popular-v1"]["clicks"] == 0
    overview = client.get("/api/v1/analytics/overview").json()
    assert overview["events_by_type"]["click"] == 1 and overview["active_model_version"] == "hybrid-test"
    assert overview["offline_metrics"] == [{"model": "hybrid", "stage": "test", "ndcg@10": 0.0182, "recall@10": 0.0287}]


def test_partner_api_requires_key(client, api_key):
    url = "/api/v1/partner/recommendations/AUSER1"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-API-Key": "wrong"}).status_code == 401
    r = client.get(url, headers={"X-API-Key": api_key})
    assert r.status_code == 200 and r.json()["strategy"] == "precomputed"


def test_loader_is_idempotent(client, tmp_path):
    from app.db import Product, SessionLocal, User
    from app.load_data import load_export
    from conftest import write_export

    with SessionLocal() as db:
        load_export(db, write_export(tmp_path / "again"))
        assert db.query(Product).count() == 5
        assert db.query(User).filter_by(is_demo=True).count() == 1
