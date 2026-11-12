"""Integer-encoded interaction data for training and evaluation.

Every model works on the same ``InteractionDataset``: a fixed item index over
the whole product catalogue, a user index over users seen in the history, a
sparse user-item matrix, and an ``available`` mask.

Availability at the cutoff
--------------------------
When evaluating at cutoff T, a product may only be recommended if the store
could have known about it at T:

* it has at least one interaction in the history (on or before T), or
* its metadata lists a "Date First Available" on or before T.

Products released after T are excluded even though they exist in the
metadata file; recommending them would use knowledge of the future. Their
interactions still count as relevant in the target window, so every model's
recall is capped by the same ceiling, which the evaluation report states.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from cartsense_ml.config import DataConfig

STAGES = ("val", "test")


@dataclass
class InteractionDataset:
    item_ids: np.ndarray
    user_ids: np.ndarray
    history: pd.DataFrame  # columns: user_idx, item_idx, rating, timestamp
    available: np.ndarray  # bool, one per item
    products: pd.DataFrame  # aligned with item_ids (row i describes item i)
    cutoff_ms: int
    item_index: dict[str, int] = field(repr=False, default_factory=dict)
    user_index: dict[str, int] = field(repr=False, default_factory=dict)
    _matrix: sp.csr_matrix | None = field(repr=False, default=None)

    @property
    def n_users(self) -> int:
        return len(self.user_ids)

    @property
    def n_items(self) -> int:
        return len(self.item_ids)

    @property
    def matrix(self) -> sp.csr_matrix:
        """Binary users x items CSR matrix of the history."""
        if self._matrix is None:
            h = self.history
            self._matrix = sp.csr_matrix(
                (np.ones(len(h), dtype=np.float32), (h["user_idx"].to_numpy(), h["item_idx"].to_numpy())),
                shape=(self.n_users, self.n_items),
            )
            self._matrix.sum_duplicates()
            self._matrix.data[:] = 1.0
        return self._matrix

    def encode_users(self, user_ids) -> np.ndarray:
        """Map user ids to indices; users without history map to -1."""
        return np.fromiter((self.user_index.get(u, -1) for u in user_ids), dtype=np.int64)

    def encode_items(self, item_ids) -> np.ndarray:
        """Map item ids to indices; ids outside the catalogue map to -1."""
        return np.fromiter((self.item_index.get(i, -1) for i in item_ids), dtype=np.int64)


def build_dataset(
    history: pd.DataFrame, products: pd.DataFrame, cutoff_ms: int | None = None
) -> InteractionDataset:
    """Encode ``history`` (user_id, item_id, rating, timestamp) against the full catalogue."""
    if cutoff_ms is None:
        cutoff_ms = int(history["timestamp"].max())
    if len(history) and int(history["timestamp"].max()) > cutoff_ms:
        raise ValueError("history contains interactions after the cutoff")

    products = products.sort_values("item_id").reset_index(drop=True)
    item_ids = products["item_id"].to_numpy()
    item_index = {item: i for i, item in enumerate(item_ids)}

    user_ids = np.sort(history["user_id"].unique())
    user_index = {user: i for i, user in enumerate(user_ids)}

    item_idx = history["item_id"].map(item_index)
    if item_idx.isna().any():
        raise ValueError(f"{int(item_idx.isna().sum())} history rows reference items missing from products")
    encoded = pd.DataFrame(
        {
            "user_idx": history["user_id"].map(user_index).to_numpy(np.int64),
            "item_idx": item_idx.to_numpy(np.int64),
            "rating": history["rating"].to_numpy(np.float32),
            "timestamp": history["timestamp"].to_numpy(np.int64),
        }
    )

    seen = np.zeros(len(item_ids), dtype=bool)
    seen[encoded["item_idx"].unique()] = True
    available = seen.copy()
    if "date_first_available" in products:
        # Missing dates become NaT, and NaT <= cutoff is False
        listed = pd.to_datetime(products["date_first_available"]) <= pd.Timestamp(cutoff_ms, unit="ms")
        available |= listed.to_numpy(bool)

    return InteractionDataset(
        item_ids=item_ids,
        user_ids=user_ids,
        history=encoded,
        available=available,
        products=products,
        cutoff_ms=cutoff_ms,
        item_index=item_index,
        user_index=user_index,
    )


def load_stage(cfg: DataConfig, stage: str) -> tuple[InteractionDataset, pd.DataFrame]:
    """History dataset and target interactions for an evaluation stage.

    * ``val``:  history = train,       target = val
    * ``test``: history = train + val, target = test
    """
    if stage not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}, got {stage!r}")
    processed = cfg.paths.processed_dir
    splits = processed / "splits"
    summary = json.loads(Path(cfg.paths.reports_dir / "split_summary.json").read_text(encoding="utf-8"))
    products = pd.read_parquet(processed / "products.parquet")

    train = pd.read_parquet(splits / "train.parquet")
    if stage == "val":
        history, target = train, pd.read_parquet(splits / "val.parquet")
        cutoff = summary["cutoffs"]["train_end_ms"]
    else:
        history = pd.concat([train, pd.read_parquet(splits / "val.parquet")], ignore_index=True)
        target = pd.read_parquet(splits / "test.parquet")
        cutoff = summary["cutoffs"]["val_end_ms"]
    return build_dataset(history, products, cutoff_ms=cutoff), target
