"""Structured "Why this?" explanations for recommendations.

Each reason comes from the signal the model actually used:

* item-kNN: the history item with the largest similarity contribution
  ("people who reviewed X also reviewed this");
* ALS: the history item closest to the recommendation in the latent space;
* content: the most similar history item by text, plus the terms they share;
* platform popularity: the user's share of history on the item's platform;
* popularity (and every user without history): the item's popularity rank.

A platform reason is added for any model when the item's platform is one of
the user's main platforms. Reasons are plain data (``Reason.to_dict``) so the
API can return them as JSON and the store can render them however it likes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from cartsense_ml.data.dataset import InteractionDataset
from cartsense_ml.data.stats import platform_of
from cartsense_ml.models.base import Recommender
from cartsense_ml.models.collaborative import ALS, ItemKNN
from cartsense_ml.models.content import ContentTfidf
from cartsense_ml.models.popularity import CategoryPopular, recency_weighted_counts

MIN_PLATFORM_SHARE = 0.25


@dataclass
class Reason:
    type: str
    text: str
    item_id: str | None = None
    score: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, {}, [])}


class Explainer:
    def __init__(self, model: Recommender):
        self.model = model
        self.ds: InteractionDataset = model.ds
        pop = recency_weighted_counts(self.ds, 180.0)
        pop[~self.ds.available] = -1
        # 1-based popularity rank of every item among available items
        order = np.argsort(-pop, kind="stable")
        self.pop_rank = np.empty_like(order)
        self.pop_rank[order] = np.arange(1, len(order) + 1)
        self.platforms = [platform_of(c) for c in self.ds.products["categories"]]
        self.titles = self.ds.products["title"].fillna("").tolist()

    # ------------------------------------------------------------------ #
    def explain(self, user_idx: int, item_idx: int, max_reasons: int = 2) -> list[Reason]:
        reasons: list[Reason] = []
        if user_idx >= 0:
            reasons += self._model_reasons(user_idx, item_idx)
            platform_reason = self._platform_reason(user_idx, item_idx)
            if platform_reason and not any(r.type == "popular_on_platform" for r in reasons):
                reasons.append(platform_reason)
        if len(reasons) < max_reasons:
            reasons.append(self._popularity_reason(item_idx))
        return reasons[:max_reasons]

    def explain_list(self, user_idx: int, item_idxs, max_reasons: int = 2) -> list[list[dict[str, Any]]]:
        return [[r.to_dict() for r in self.explain(user_idx, int(i), max_reasons)] for i in item_idxs]

    # ------------------------------------------------------------------ #
    def _title(self, item_idx: int) -> str:
        return self.titles[item_idx] or str(self.ds.item_ids[item_idx])

    def _history_reason(self, kind: str, text: str, item: int, score: float, **details) -> Reason:
        return Reason(kind, text, item_id=str(self.ds.item_ids[item]), score=round(score, 4), details=details)

    def _model_reasons(self, user_idx: int, item_idx: int) -> list[Reason]:
        m = self.model
        if isinstance(m, ItemKNN):
            top = m.contributions(user_idx, item_idx)[:1]
            return [
                self._history_reason(
                    "also_reviewed_with", f'People who reviewed "{self._title(i)}" also reviewed this', i, s
                )
                for i, s in top
            ]
        if isinstance(m, ALS):
            top = m.contributions(user_idx, item_idx)[:1]
            return [
                self._history_reason(
                    "similar_taste",
                    f'Liked by players with similar taste; close to "{self._title(i)}" in your history',
                    i, s,
                )
                for i, s in top
            ]
        if isinstance(m, ContentTfidf):
            history = self.ds.matrix[user_idx].indices
            if history.size == 0:
                return []
            sims = (m.item_vectors[history] @ m.item_vectors[item_idx].T).toarray().ravel()
            best = int(np.argmax(sims))
            if sims[best] <= 0:
                return []
            source = int(history[best])
            terms = m.shared_terms(source, item_idx)
            suffix = f" (shared: {', '.join(terms)})" if terms else ""
            return [
                self._history_reason(
                    "similar_content", f'Similar to "{self._title(source)}"{suffix}', source, float(sims[best]),
                    shared_terms=terms,
                )
            ]
        if isinstance(m, CategoryPopular):
            reason = self._platform_reason(user_idx, item_idx, min_share=0.0)
            return [reason] if reason else []
        return []

    def _platform_reason(self, user_idx: int, item_idx: int, min_share: float = MIN_PLATFORM_SHARE) -> Reason | None:
        platform = self.platforms[item_idx]
        if not platform:
            return None
        history = self.ds.matrix[user_idx].indices
        counts = Counter(self.platforms[i] for i in history if self.platforms[i])
        total = sum(counts.values())
        if not total:
            return None
        share = counts.get(platform, 0) / total
        if share <= min_share or share == 0:
            return None
        return Reason(
            "popular_on_platform",
            f"Popular on {platform}, {share:.0%} of what you have reviewed",
            score=round(share, 4),
            details={"platform": platform},
        )

    def _popularity_reason(self, item_idx: int) -> Reason:
        rank = int(self.pop_rank[item_idx])
        text = f"Trending: #{rank} in the store right now" if rank <= 100 else "Recommended to shoppers like you"
        return Reason("trending" if rank <= 100 else "general", text, score=float(rank), details={"rank": rank})
