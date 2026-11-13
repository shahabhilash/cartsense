"""Store feedback: reading events, turning them into interactions, merging for retraining."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from cartsense_ml.export import select_recommendation_users
from cartsense_ml.feedback import (
    load_site_events,
    merge_site_interactions,
    normalize_url,
    to_interactions,
)


@pytest.fixture
def store_db(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'store.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, dataset_user_id VARCHAR)"))
        conn.execute(text("CREATE TABLE events (id INTEGER PRIMARY KEY, user_id INTEGER, session_id VARCHAR, "
                          "event_type VARCHAR, product_id VARCHAR, query VARCHAR, is_synthetic BOOLEAN, created_at DATETIME)"))
        conn.execute(text("INSERT INTO users VALUES (1, 'ADEMO'), (2, NULL)"))
        rows = [
            # demo shopper 1: viewed then bagged A -> one interaction, strength 5
            (1, None, "view", "A", 0, "2026-11-01 10:00:00"),
            (1, None, "add_to_cart", "A", 0, "2026-11-01 10:05:00"),
            # store account 2: clicked B
            (2, None, "click", "B", 0, "2026-11-01 11:00:00"),
            # guest with two products (kept) and a guest with one (dropped)
            (None, "g1", "view", "A", 0, "2026-11-01 12:00:00"),
            (None, "g1", "view", "C", 0, "2026-11-01 12:01:00"),
            (None, "g2", "view", "C", 0, "2026-11-01 12:02:00"),
            # ignored: synthetic, search (no product), unknown product
            (2, None, "click", "C", 1, "2026-11-01 13:00:00"),
            (2, None, "search", None, 0, "2026-11-01 13:01:00"),
            (2, None, "view", "NOT_IN_CATALOGUE", 0, "2026-11-01 13:02:00"),
        ]
        for i, (uid, sid, etype, pid, synthetic, ts) in enumerate(rows, start=1):
            conn.execute(text("INSERT INTO events (id, user_id, session_id, event_type, product_id, is_synthetic, created_at) "
                              "VALUES (:i, :u, :s, :e, :p, :syn, :ts)"),
                         {"i": i, "u": uid, "s": sid, "e": etype, "p": pid, "syn": synthetic, "ts": ts})
    engine.dispose()
    return url


def test_store_events_become_weighted_interactions(store_db):
    events = load_site_events(store_db)
    assert len(events) == 7  # synthetic and product-less events are not read
    site = to_interactions(events, catalogue={"A", "B", "C"})
    got = {(r.user_id, r.item_id): r.rating for r in site.itertuples()}
    assert got == {
        ("ADEMO", "A"): 5.0,  # demo shopper maps to their dataset id; strongest signal wins
        ("site:2", "B"): 4.0,
        ("session:g1", "A"): 3.0,
        ("session:g1", "C"): 3.0,
    }
    assert set(site["source"]) == {"store"}
    assert site["timestamp"].is_monotonic_increasing


def test_empty_store_gives_empty_feedback():
    empty = pd.DataFrame(columns=["user_id", "session_id", "event_type", "product_id", "created_at", "dataset_user_id"])
    assert to_interactions(empty, {"A"}).empty


def test_merge_places_store_activity_after_the_dataset():
    dataset = pd.DataFrame({"user_id": ["U1", "U2"], "item_id": ["A", "B"], "rating": [5.0, 4.0],
                            "timestamp": [1000, 2000]})
    site = pd.DataFrame({"user_id": ["site:9", "U1"], "item_id": ["C", "A"], "rating": [3.0, 5.0],
                         "timestamp": [1_800_000_000_000, 1_800_000_000_500], "source": ["store", "store"]})
    merged = merge_site_interactions(dataset, site)
    # store events land right after the last dataset timestamp, order kept
    store = merged[merged["source"] == "store"].sort_values("timestamp")
    assert store["timestamp"].tolist() == [2001, 2002]
    assert store["user_id"].tolist() == ["site:9", "U1"]
    # (U1, A) appears once: the newer store interaction replaces the dataset one
    assert len(merged[(merged.user_id == "U1") & (merged.item_id == "A")]) == 1
    assert len(merged) == 3


def test_merge_without_store_data_is_the_dataset():
    dataset = pd.DataFrame({"user_id": ["U1"], "item_id": ["A"], "rating": [5.0], "timestamp": [1]})
    out = merge_site_interactions(dataset, None)
    assert out.drop(columns=["source"]).equals(dataset)


def test_recommendations_go_to_demo_shoppers_and_store_accounts():
    user_ids = np.array(["U1", "U2", "U3", "site:5", "session:x"], dtype=object)
    counts = np.array([3, 9, 1, 50, 40])
    demo, site = select_recommendation_users(user_ids, counts, n_demo=2)
    assert user_ids[demo].tolist() == ["U2", "U1"]  # most active dataset users, store ids excluded
    assert user_ids[site].tolist() == ["site:5"]  # guest sessions get no precomputed list


def test_normalize_url():
    assert normalize_url(' "postgres://u:p@h/db" ') == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("sqlite:///x.db") == "sqlite:///x.db"
