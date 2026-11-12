"""Common interface for all recommenders.

A model implements ``fit`` and ``score``; ``recommend`` is shared. It scores
users in batches, removes items the store could not offer at the cutoff and
items the user already interacted with, and returns the top-k item indices.

Users without history are passed as index -1, so each model decides its own
cold-start behaviour inside ``score``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from cartsense_ml.data.dataset import InteractionDataset


class NotFittedError(RuntimeError):
    pass


class Recommender(ABC):
    name: str = "base"

    def __init__(self, seed: int = 42):
        self.seed = seed
        self._ds: InteractionDataset | None = None

    # ------------------------------------------------------------------ #
    # To implement
    # ------------------------------------------------------------------ #
    @abstractmethod
    def _fit(self, ds: InteractionDataset) -> None:
        """Learn parameters from ``ds.history``."""

    @abstractmethod
    def score(self, user_idx: np.ndarray) -> np.ndarray:
        """Return a (len(user_idx), n_items) float array; higher is better.
        ``user_idx == -1`` marks a user with no history."""

    def params(self) -> dict[str, Any]:
        """Hyperparameters to log with the experiment."""
        return {"seed": self.seed}

    # ------------------------------------------------------------------ #
    # Shared behaviour
    # ------------------------------------------------------------------ #
    def fit(self, ds: InteractionDataset) -> "Recommender":
        self._ds = ds
        self._fit(ds)
        return self

    @property
    def ds(self) -> InteractionDataset:
        if self._ds is None:
            raise NotFittedError(f"{self.name} has not been fitted")
        return self._ds

    def recommend(
        self,
        user_idx: np.ndarray,
        k: int,
        exclude_seen: bool = True,
        batch_size: int = 2048,
    ) -> np.ndarray:
        """Top-k item indices per user, shape (len(user_idx), k), best first."""
        ds = self.ds
        user_idx = np.asarray(user_idx, dtype=np.int64)
        if k > int(ds.available.sum()):
            raise ValueError(f"k={k} exceeds the {int(ds.available.sum())} recommendable items")

        # Rank only recommendable columns: smaller arrays, and no large block of
        # identical -inf values for the partition step to wade through.
        avail_idx = np.flatnonzero(ds.available)
        position = np.full(ds.n_items, -1, dtype=np.int64)
        position[avail_idx] = np.arange(avail_idx.size)

        out = np.empty((len(user_idx), k), dtype=np.int64)
        for start in range(0, len(user_idx), batch_size):
            batch = user_idx[start : start + batch_size]
            full = self.score(batch)
            if full.shape != (len(batch), ds.n_items):
                raise ValueError(f"{self.name}.score returned shape {full.shape}")
            scores = np.asarray(full, dtype=np.float32)[:, avail_idx]  # fancy indexing copies
            if exclude_seen:
                warm = np.flatnonzero(batch >= 0)
                if warm.size:
                    rows, cols = ds.matrix[batch[warm]].nonzero()
                    cols = position[cols]
                    keep = cols >= 0
                    scores[warm[rows[keep]], cols[keep]] = -np.inf
            out[start : start + len(batch)] = avail_idx[top_k(scores, k)]
        return out


def top_k(scores: np.ndarray, k: int) -> np.ndarray:
    """Indices of the k largest scores per row, sorted best first.
    Ties are broken by the lower item index, so results are deterministic."""
    n_items = scores.shape[1]
    if k >= n_items:
        cand = np.tile(np.arange(n_items), (scores.shape[0], 1))
    else:
        cand = np.argpartition(-scores, k - 1, axis=1)[:, :k]
        # argpartition may cut a tie group arbitrarily; widen to the full tie at the boundary
        kth = np.take_along_axis(scores, cand, axis=1).min(axis=1, keepdims=True)
        if np.any((scores >= kth).sum(axis=1) > k):
            return _top_k_with_ties(scores, k)
    cand_scores = np.take_along_axis(scores, cand, axis=1)
    order = np.lexsort((cand, -cand_scores), axis=1)
    return np.take_along_axis(cand, order, axis=1)[:, :k]


def _top_k_with_ties(scores: np.ndarray, k: int) -> np.ndarray:
    # Stable sort on the negated scores keeps equal scores in item-index order
    return np.argsort(-scores, axis=1, kind="stable")[:, :k]
