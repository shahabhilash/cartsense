from pathlib import Path

import pandas as pd

from cartsense_ml.data.clean import CleanReport, clean_interactions, run_clean


def _ratings(rows):
    return pd.DataFrame(rows, columns=["user_id", "parent_asin", "rating", "timestamp"])


def test_clean_interactions_applies_each_rule_and_counts_it():
    ratings = _ratings(
        [
            ("U1", "A", 5.0, 100),
            ("U1", "A", 2.0, 300),  # duplicate pair, later review wins
            ("U1", "B", 4.0, 200),
            ("U2", "A", 0.0, 150),  # invalid rating
            ("U2", None, 3.0, 160),  # missing item
            ("U3", "X", 4.0, 170),  # item not in catalogue
        ]
    )
    report = CleanReport()
    out = clean_interactions(ratings, {"A", "B"}, report)

    assert report.raw_interactions == 6
    assert report.dropped_missing_fields == 1
    assert report.dropped_invalid_rating == 1
    assert report.dropped_duplicate_pairs == 1
    assert report.dropped_unknown_or_untitled_item == 1
    assert report.interactions == 2
    assert list(out.columns) == ["user_id", "item_id", "rating", "timestamp"]
    # sorted by time, and the kept (U1, A) row is the latest one
    assert out["timestamp"].tolist() == [200, 300]
    assert out.loc[out.item_id == "A", "rating"].item() == 2.0


def test_run_clean_writes_consistent_tables(tmp_path: Path):
    ratings = _ratings([("U1", "A", 5.0, 1), ("U2", "B", 4.0, 2), ("U3", "C", 3.0, 3)])
    products = pd.DataFrame(
        {
            "item_id": ["A", "A", "B", "C", "D"],
            "title": ["Game A", "Game A dup", None, "Game C", "Never rated"],
        }
    )
    ratings.to_parquet(tmp_path / "ratings.parquet")
    products.to_parquet(tmp_path / "products.parquet")

    report = run_clean(tmp_path / "ratings.parquet", tmp_path / "products.parquet", tmp_path / "out")
    inter = pd.read_parquet(tmp_path / "out" / "interactions.parquet")
    prods = pd.read_parquet(tmp_path / "out" / "products.parquet")

    # B has no title so its interaction goes; D has no interactions so it goes
    assert set(inter.item_id) == {"A", "C"}
    assert set(prods.item_id) == {"A", "C"}
    assert prods.loc[prods.item_id == "A", "title"].item() == "Game A"
    assert report.dropped_duplicate_products == 1
    assert report.dropped_untitled_products == 1
    assert report.dropped_products_without_interactions == 1
    assert report.products == 2 and report.interactions == 2
