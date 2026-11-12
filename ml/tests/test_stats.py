import json
from pathlib import Path

import pandas as pd
import pytest

from cartsense_ml.data.stats import compute_stats, platform_of, write_report


@pytest.fixture
def tables():
    interactions = pd.DataFrame(
        {
            "user_id": ["U1", "U1", "U1", "U2", "U2", "U3"],
            "item_id": ["A", "B", "C", "A", "B", "A"],
            "rating": [5.0, 4.0, 5.0, 3.0, 1.0, 5.0],
            # 2020-01-01 and 2021-01-01 (UTC)
            "timestamp": [1577836800000] * 3 + [1609459200000] * 3,
        }
    )
    products = pd.DataFrame(
        {
            "item_id": ["A", "B", "C"],
            "brand": ["Acme", "Acme", None],
            "categories": [["Video Games", "PC"], ["Video Games", "PC", "Games"], ["Video Games"]],
            "features": [["x"], [], ["y"]],
            "description": ["d", None, "d"],
            "price": [9.99, None, None],
        }
    )
    return interactions, products


def test_compute_stats_counts(tables):
    stats = compute_stats(*tables)
    assert stats["interactions"] == 6
    assert stats["users"] == 3 and stats["items"] == 3
    assert stats["density"] == round(6 / 9, 6)
    assert stats["interactions_per_user"]["max"] == 3
    assert stats["interactions_per_item"]["min"] == 1
    assert stats["rating_distribution"] == {"1": 1, "3": 1, "4": 1, "5": 3}
    assert stats["interactions_per_year"] == {"2020": 3, "2021": 3}
    assert stats["time_range"]["first"].startswith("2020-01-01")
    assert stats["metadata_coverage"]["features"] == round(2 / 3, 4)
    assert stats["metadata_coverage"]["price"] == round(1 / 3, 4)
    assert stats["top_platforms"] == {"PC": 2}
    assert stats["top_brands"] == {"Acme": 2}


def test_platform_of():
    assert platform_of(["Video Games", "Xbox One"]) == "Xbox One"
    assert platform_of(["Video Games"]) is None
    assert platform_of(None) is None


def test_write_report_creates_json_and_markdown(tables, tmp_path: Path):
    stats = compute_stats(*tables)
    json_path, md_path = write_report(stats, {"interactions": 6}, "Video_Games", tmp_path)
    assert json.loads(json_path.read_text())["stats"]["users"] == 3
    md = md_path.read_text()
    assert md.startswith("# Dataset report: Video_Games (5-core)")
    assert "| Users | 3 |" in md
