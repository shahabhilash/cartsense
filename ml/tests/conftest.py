"""Shared fixtures: tiny gzip files shaped like the real Amazon Reviews 2023 files."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

RATINGS_CSV = """user_id,parent_asin,rating,timestamp
U1,A,5.0,1000
U1,B,4.0,2000
U2,A,3.0,1500
U2,C,1.0,2500
U3,B,5.0,3000
"""

META_RECORDS = [
    {
        "parent_asin": "A",
        "title": "  Space Shooter  ",
        "main_category": "Video Games",
        "store": "Acme",
        "categories": ["Video Games", "PC", "Games"],
        "features": ["Fast", "", None],
        "description": ["Line one.", "Line two."],
        "price": 19.99,
        "average_rating": 4.5,
        "rating_number": 120,
        "images": [
            {"thumb": "t.jpg", "large": "alt.jpg", "variant": "PT01", "hi_res": None},
            {"thumb": "t.jpg", "large": "main.jpg", "variant": "MAIN", "hi_res": None},
        ],
        "details": {"Date First Available": "October 2, 2001", "Rated": "Everyone"},
    },
    {
        "parent_asin": "B",
        "title": "Racing Wheel",
        "main_category": "Video Games",
        "store": None,
        "categories": [],
        "features": [],
        "description": [],
        "price": "—",
        "average_rating": 3.9,
        "rating_number": 8,
        "images": [],
        "details": {},
    },
    # Not in the ratings file: must be filtered out
    {"parent_asin": "Z", "title": "Unrated thing", "price": "$5.00"},
    # Missing id: must be dropped
    {"title": "No id"},
]


@pytest.fixture
def raw_files(tmp_path: Path) -> dict[str, Path]:
    ratings = tmp_path / "ratings.csv.gz"
    with gzip.open(ratings, "wt", encoding="utf-8") as fh:
        fh.write(RATINGS_CSV)

    meta = tmp_path / "meta.jsonl.gz"
    with gzip.open(meta, "wt", encoding="utf-8") as fh:
        for rec in META_RECORDS:
            fh.write(json.dumps(rec) + "\n")
        fh.write("{not valid json\n")
    return {"ratings": ratings, "meta": meta}
