from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from cartsense_ml.data.convert import (
    PRODUCT_SCHEMA,
    RATINGS_SCHEMA,
    iter_jsonl_chunks,
    metadata_to_parquet,
    normalize_meta,
    parse_first_available,
    parse_price,
    pick_image_url,
    ratings_to_parquet,
    unique_item_ids,
)


def test_ratings_to_parquet_keeps_schema_and_rows(raw_files, tmp_path: Path):
    dest = tmp_path / "out" / "ratings.parquet"
    # A tiny block size forces several streamed batches
    rows = ratings_to_parquet(raw_files["ratings"], dest, block_bytes=48)
    table = pq.read_table(dest)
    assert rows == table.num_rows == 5
    assert table.schema.equals(RATINGS_SCHEMA)
    assert unique_item_ids(dest) == {"A", "B", "C"}


def test_iter_jsonl_chunks_batches_and_skips_bad_lines(raw_files):
    chunks = list(iter_jsonl_chunks(raw_files["meta"], chunk_size=3))
    assert [len(c) for c in chunks] == [3, 1]


@pytest.mark.parametrize(
    "raw,expected",
    [
        (19.99, 19.99),
        ("$1,299.00", 1299.0),
        ("—", None),
        (None, None),
        (0, None),
        (-3, None),
        (True, None),
        (float("nan"), None),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_pick_image_prefers_main_variant():
    images = [
        {"large": "alt.jpg", "variant": "PT01"},
        {"large": None, "hi_res": "main_hi.jpg", "variant": "MAIN"},
    ]
    assert pick_image_url(images) == "main_hi.jpg"
    assert pick_image_url([]) is None
    assert pick_image_url(None) is None


def test_parse_first_available():
    assert parse_first_available({"Date First Available": "October 2, 2001"}) == date(2001, 10, 2)
    assert parse_first_available({"Date First Available": "Sept. 2001"}) is None
    assert parse_first_available({}) is None


def test_normalize_meta_flattens_record():
    from conftest import META_RECORDS

    row = normalize_meta(META_RECORDS[0])
    assert row["item_id"] == "A"
    assert row["title"] == "Space Shooter"
    assert row["brand"] == "Acme"
    assert row["features"] == ["Fast"]
    assert row["description"] == "Line one.\nLine two."
    assert row["image_url"] == "main.jpg"
    assert row["date_first_available"] == date(2001, 10, 2)
    assert '"Rated": "Everyone"' in row["details_json"]
    assert set(row) == set(PRODUCT_SCHEMA.names)
    assert normalize_meta({"title": "no id"}) is None


def test_metadata_to_parquet_filters_to_rated_items(raw_files, tmp_path: Path):
    dest = tmp_path / "products.parquet"
    counts = metadata_to_parquet(raw_files["meta"], dest, chunk_size=2, keep_ids={"A", "B", "C"})
    table = pq.read_table(dest)
    assert counts == {"records_seen": 4, "records_written": 2}
    assert sorted(table.column("item_id").to_pylist()) == ["A", "B"]
    assert table.schema.equals(PRODUCT_SCHEMA)
    b = next(r for r in table.to_pylist() if r["item_id"] == "B")
    assert b["price"] is None and b["brand"] is None and b["details_json"] is None
