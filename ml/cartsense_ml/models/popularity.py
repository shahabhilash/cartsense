"""Non-personalised and lightly personalised baselines.

* ``RandomRecommender``: uniform random scores; the floor every model must beat.
* ``MostPopular``: number of interactions per item in the history.
* ``RecentPopular``: interactions weighted by recency with exponential decay,
  ``w = 0.5 ** (age / half_life)``, where age is measured from the cutoff.
  An item reviewed a lot ten years ago should not outrank this year's hits.
* ``CategoryPopular``: recent popularity re-weighted by the user's affinity to
  the item's platform (the second category level, e.g. "PC" or
  "Nintendo Switch"). Users without history fall back to ``RecentPopular``.
  This is also the cold-start strategy for new site users once they browse.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import scipy.sparse as sp

from cartsense_ml.data.dataset import InteractionDataset
from cartsense_ml.data.stats import platform_of
from cartsense_ml.models.base import Recommender

DAY_MS = 86_400_000
UNKNOWN_PLATFORM = "<unknown>"


class RandomRecommender(Recommender):
    name = "random"

    def _fit(self, ds: InteractionDataset) -> None:
        self._rng = np.random.default_rng(self.seed)

    def score(self, user_idx: np.ndarray) -> np.ndarray:
        return self._rng.random((len(user_idx), self.ds.n_items), dtype=np.float32)


class MostPopular(Recommender):
    name = "most_popular"

    def _fit(self, ds: InteractionDataset) -> None:
        counts = np.bincount(ds.history["item_idx"].to_numpy(), minlength=ds.n_items)
        self.item_scores = counts.astype(np.float32)

    def score(self, user_idx: np.ndarray) -> np.ndarray:
        return np.broadcast_to(self.item_scores, (len(user_idx), self.ds.n_items))


def recency_weighted_counts(ds: InteractionDataset, half_life_days: float) -> np.ndarray:
    age_days = (ds.cutoff_ms - ds.history["timestamp"].to_numpy()) / DAY_MS
    weights = np.power(0.5, age_days / half_life_days)
    return np.bincount(ds.history["item_idx"].to_numpy(), weights=weights, minlength=ds.n_items)


class RecentPopular(MostPopular):
    name = "recent_popular"

    def __init__(self, half_life_days: float = 180.0, seed: int = 42):
        super().__init__(seed=seed)
        if half_life_days <= 0:
            raise ValueError("half_life_days must be positive")
        self.half_life_days = half_life_days

    def _fit(self, ds: InteractionDataset) -> None:
        self.item_scores = recency_weighted_counts(ds, self.half_life_days).astype(np.float32)

    def params(self) -> dict[str, Any]:
        return {**super().params(), "half_life_days": self.half_life_days}


class CategoryPopular(Recommender):
    """score(u, i) = affinity(u, platform(i)) * pop(i) + fallback_weight * pop(i)

    ``pop`` is recency-weighted popularity scaled to [0, 1]; ``affinity`` is
    the share of the user's history on each platform. The small fallback term
    orders items outside the user's platforms by popularity and serves users
    with no history.
    """

    name = "category_popular"

    def __init__(self, half_life_days: float = 180.0, fallback_weight: float = 1e-3, seed: int = 42):
        super().__init__(seed=seed)
        self.half_life_days = half_life_days
        self.fallback_weight = fallback_weight

    def _fit(self, ds: InteractionDataset) -> None:
        pop = recency_weighted_counts(ds, self.half_life_days)
        self.pop = (pop / pop.max() if pop.max() > 0 else pop).astype(np.float32)

        platforms = [platform_of(c) or UNKNOWN_PLATFORM for c in ds.products["categories"]]
        self.platform_names, self.item_platform = np.unique(platforms, return_inverse=True)

        # users x platforms counts, normalised to shares per user
        h = ds.history
        counts = sp.csr_matrix(
            (
                np.ones(len(h), dtype=np.float32),
                (h["user_idx"].to_numpy(), self.item_platform[h["item_idx"].to_numpy()]),
            ),
            shape=(ds.n_users, len(self.platform_names)),
        ).toarray()
        totals = counts.sum(axis=1, keepdims=True)
        self.affinity = np.divide(counts, totals, out=np.zeros_like(counts), where=totals > 0)

    def score(self, user_idx: np.ndarray) -> np.ndarray:
        n = len(user_idx)
        scores = np.tile(self.fallback_weight * self.pop, (n, 1))
        warm = np.flatnonzero(user_idx >= 0)
        if warm.size:
            item_affinity = self.affinity[user_idx[warm]][:, self.item_platform]
            scores[warm] += item_affinity * self.pop
        return scores

    def params(self) -> dict[str, Any]:
        return {
            **super().params(),
            "half_life_days": self.half_life_days,
            "fallback_weight": self.fallback_weight,
        }

    def top_platforms(self, user_idx: int, n: int = 3) -> list[tuple[str, float]]:
        """The user's strongest platforms with their share; used for explanations."""
        if user_idx < 0:
            return []
        row = self.affinity[user_idx]
        order = np.argsort(-row)[:n]
        return [(str(self.platform_names[j]), float(row[j])) for j in order if row[j] > 0]
