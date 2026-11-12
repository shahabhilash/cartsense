import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cartsense_ml.data.split import Cutoffs, compute_cutoffs, run_split, summarize_split, time_split


@pytest.fixture
def interactions():
    rng = np.random.default_rng(0)
    n = 1000
    return pd.DataFrame(
        {
            "user_id": [f"U{i}" for i in rng.integers(0, 80, n)],
            "item_id": [f"I{i}" for i in rng.integers(0, 50, n)],
            "rating": rng.integers(1, 6, n).astype("float32"),
            "timestamp": np.sort(rng.integers(1_000_000, 9_000_000, n)),
        }
    )


def test_splits_partition_rows_without_time_overlap(interactions):
    cutoffs = compute_cutoffs(interactions["timestamp"], 0.8, 0.9)
    splits = time_split(interactions, cutoffs)

    assert sum(len(s) for s in splits.values()) == len(interactions)
    assert splits["train"]["timestamp"].max() <= cutoffs.train_end
    assert splits["val"]["timestamp"].min() > cutoffs.train_end
    assert splits["val"]["timestamp"].max() <= cutoffs.val_end
    assert splits["test"]["timestamp"].min() > cutoffs.val_end
    # roughly the requested proportions
    assert abs(len(splits["train"]) / len(interactions) - 0.8) < 0.01
    assert abs(len(splits["val"]) / len(interactions) - 0.1) < 0.01


def test_cutoffs_are_observed_timestamps(interactions):
    cutoffs = compute_cutoffs(interactions["timestamp"], 0.8, 0.9)
    observed = set(interactions["timestamp"])
    assert cutoffs.train_end in observed and cutoffs.val_end in observed


def test_degenerate_timestamps_rejected():
    ts = pd.Series([5] * 100)
    with pytest.raises(ValueError):
        compute_cutoffs(ts, 0.8, 0.9)


def test_cold_start_counts():
    df = pd.DataFrame(
        {
            "user_id": ["U1", "U2", "U1", "U3", "U1", "U4"],
            "item_id": ["A", "B", "A", "C", "B", "D"],
            "rating": [5.0] * 6,
            "timestamp": [1, 2, 3, 4, 5, 6],
        }
    )
    splits = time_split(df, Cutoffs(train_end=2, val_end=4))
    summary = summarize_split(splits, Cutoffs(train_end=2, val_end=4))
    # val = (U1,A,3), (U3,C,4): U1 warm, U3 cold, C is a new item
    assert summary["val_vs_train"]["warm_users"] == 1
    assert summary["val_vs_train"]["cold_users"] == 1
    assert summary["val_vs_train"]["cold_items"] == 1
    # test = (U1,B,5), (U4,D,6) measured against train+val history
    assert summary["test_vs_train_val"]["cold_users"] == 1
    assert summary["test_vs_train_val"]["rows_with_cold_items"] == 1


def test_run_split_writes_files(interactions, tmp_path: Path):
    path = tmp_path / "interactions.parquet"
    interactions.to_parquet(path)
    summary = run_split(path, tmp_path / "splits", tmp_path / "reports", 0.8, 0.9)
    for name in ("train", "val", "test"):
        assert len(pd.read_parquet(tmp_path / "splits" / f"{name}.parquet")) == summary[name]["rows"]
    saved = json.loads((tmp_path / "reports" / "split_summary.json").read_text())
    assert saved["cutoffs"]["train_end_ms"] == summary["cutoffs"]["train_end_ms"]
