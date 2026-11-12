"""Evaluate a fitted recommender on a target window.

Ground truth for a user is the set of products they interacted with in the
target window, minus anything already in their history (those are filtered
out of the recommendations, so counting them would only lower every model's
recall by the same amount).

Results are reported for all target users and separately for warm users (with
history before the cutoff) and cold users (without). An oracle recall ceiling
shows the best recall any model could reach given the cutoff catalogue: the
share of a user's relevant items that were recommendable, capped at k.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cartsense_ml.data.dataset import InteractionDataset
from cartsense_ml.eval.metrics import all_metrics
from cartsense_ml.models.base import Recommender


@dataclass
class EvalTarget:
    user_ids: np.ndarray
    user_idx: np.ndarray  # -1 for users without history
    relevant: list[set[int]]

    @property
    def warm(self) -> np.ndarray:
        return self.user_idx >= 0

    def __len__(self) -> int:
        return len(self.user_ids)


def build_target(ds: InteractionDataset, target: pd.DataFrame) -> EvalTarget:
    df = pd.DataFrame(
        {
            "user_id": target["user_id"].to_numpy(),
            "item_idx": ds.encode_items(target["item_id"]),
        }
    )
    if (df["item_idx"] < 0).any():
        raise ValueError("target contains items outside the catalogue")
    df["user_idx"] = ds.encode_users(df["user_id"])

    # Drop (user, item) pairs already present in that user's history
    warm = df[df["user_idx"] >= 0]
    if len(warm):
        in_history = np.asarray(
            ds.matrix[warm["user_idx"].to_numpy(), warm["item_idx"].to_numpy()]
        ).ravel() > 0
        df = df.drop(index=warm.index[in_history])

    grouped = df.groupby("user_id", sort=True)
    user_ids = np.array(list(grouped.groups.keys()), dtype=object)
    relevant = [set(g["item_idx"].tolist()) for _, g in grouped]
    return EvalTarget(user_ids=user_ids, user_idx=ds.encode_users(user_ids), relevant=relevant)


def oracle_recall(ds: InteractionDataset, relevant: list[set[int]], k: int) -> float:
    """Best achievable Recall@k when only available items can be recommended."""
    avail = ds.available
    reachable = np.array([sum(1 for i in r if avail[i]) for r in relevant], dtype=np.float64)
    sizes = np.array([len(r) for r in relevant], dtype=np.float64)
    return float((np.minimum(reachable, k) / sizes).mean())


def _subset(recs: np.ndarray, relevant: list[set[int]], mask: np.ndarray):
    idx = np.flatnonzero(mask)
    return recs[idx], [relevant[i] for i in idx]


def evaluate(
    model: Recommender,
    ds: InteractionDataset,
    target: EvalTarget,
    k_values: list[int],
    batch_size: int = 2048,
) -> dict[str, Any]:
    n_available = int(ds.available.sum())
    start = time.perf_counter()
    recs = model.recommend(target.user_idx, max(k_values), batch_size=batch_size)
    recommend_seconds = time.perf_counter() - start

    result: dict[str, Any] = {
        "n_users": len(target),
        "n_warm_users": int(target.warm.sum()),
        "n_cold_users": int((~target.warm).sum()),
        "n_recommendable_items": n_available,
        "recommend_seconds": round(recommend_seconds, 3),
        "overall": all_metrics(recs, target.relevant, k_values, n_available),
        "oracle_recall": {f"recall@{k}": oracle_recall(ds, target.relevant, k) for k in k_values},
    }
    for name, mask in (("warm_users", target.warm), ("cold_users", ~target.warm)):
        if mask.any():
            r, rel = _subset(recs, target.relevant, mask)
            result[name] = all_metrics(r, rel, k_values, n_available)
    return result
