"""Global time-based train/validation/test split.

Two cutoffs t1 < t2 are taken at quantiles of all interaction timestamps:

    train: ts <= t1        val: t1 < ts <= t2        test: ts > t2

Because the cutoffs are global (the same for every user), no model ever sees
an interaction that happened after the period it is evaluated on. A per-user
leave-last-out split would leak future popularity and co-occurrence signals
from other users into training.

Evaluation protocol used by later phases:
* validation: fit on train, score on val (model selection, ranker labels);
* test: refit on train + val, score on test (reported once).

Users and items that first appear after a cutoff are "cold" for that period;
the summary counts them so cold-start performance can be reported separately.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class Cutoffs:
    train_end: int  # inclusive upper bound for train (ms)
    val_end: int  # inclusive upper bound for val (ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "train_end_ms": self.train_end,
            "val_end_ms": self.val_end,
            "train_end": pd.Timestamp(self.train_end, unit="ms", tz="UTC").isoformat(),
            "val_end": pd.Timestamp(self.val_end, unit="ms", tz="UTC").isoformat(),
        }


def compute_cutoffs(timestamps: pd.Series, train_quantile: float, val_quantile: float) -> Cutoffs:
    # interpolation="lower" returns an observed timestamp, so a cutoff is a real event time
    t1 = int(timestamps.quantile(train_quantile, interpolation="lower"))
    t2 = int(timestamps.quantile(val_quantile, interpolation="lower"))
    if t2 <= t1:
        raise ValueError("validation window is empty: too many interactions share one timestamp")
    return Cutoffs(train_end=t1, val_end=t2)


def time_split(
    interactions: pd.DataFrame, cutoffs: Cutoffs
) -> dict[str, pd.DataFrame]:
    ts = interactions["timestamp"]
    masks = {
        "train": ts <= cutoffs.train_end,
        "val": (ts > cutoffs.train_end) & (ts <= cutoffs.val_end),
        "test": ts > cutoffs.val_end,
    }
    return {name: interactions[mask].reset_index(drop=True) for name, mask in masks.items()}


def _cold_counts(target: pd.DataFrame, history: pd.DataFrame) -> dict[str, int]:
    known_users = set(history["user_id"])
    known_items = set(history["item_id"])
    users = target["user_id"].drop_duplicates()
    warm_user_rows = target["user_id"].isin(known_users)
    warm_item_rows = target["item_id"].isin(known_items)
    return {
        "users": int(users.size),
        "warm_users": int(users.isin(known_users).sum()),
        "cold_users": int((~users.isin(known_users)).sum()),
        "rows_from_cold_users": int((~warm_user_rows).sum()),
        "rows_with_cold_items": int((~warm_item_rows).sum()),
        "cold_items": int((~target["item_id"].drop_duplicates().isin(known_items)).sum()),
    }


def summarize_split(splits: dict[str, pd.DataFrame], cutoffs: Cutoffs) -> dict[str, Any]:
    summary: dict[str, Any] = {"cutoffs": cutoffs.to_dict()}
    for name in SPLITS:
        df = splits[name]
        summary[name] = {
            "rows": len(df),
            "users": int(df["user_id"].nunique()),
            "items": int(df["item_id"].nunique()),
            "first": pd.Timestamp(int(df["timestamp"].min()), unit="ms", tz="UTC").isoformat() if len(df) else None,
            "last": pd.Timestamp(int(df["timestamp"].max()), unit="ms", tz="UTC").isoformat() if len(df) else None,
        }
    summary["val_vs_train"] = _cold_counts(splits["val"], splits["train"])
    summary["test_vs_train_val"] = _cold_counts(
        splits["test"], pd.concat([splits["train"], splits["val"]], ignore_index=True)
    )
    return summary


def run_split(
    interactions_path: Path,
    out_dir: Path,
    reports_dir: Path,
    train_quantile: float,
    val_quantile: float,
) -> dict[str, Any]:
    interactions = pd.read_parquet(interactions_path)
    cutoffs = compute_cutoffs(interactions["timestamp"], train_quantile, val_quantile)
    splits = time_split(interactions, cutoffs)

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in splits.items():
        df.to_parquet(out_dir / f"{name}.parquet", index=False)

    summary = summarize_split(splits, cutoffs)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "split_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    log.info("split: %s", {k: summary[k]["rows"] for k in SPLITS})
    return summary
