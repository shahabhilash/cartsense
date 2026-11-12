"""Content-based recommender over product text (TF-IDF).

Item representation
    One document per product: title (repeated, so it carries more weight),
    brand, every category level, features and the description (truncated).
    Brand and category values are also added as single tokens such as
    ``brand_nintendo`` and ``cat_nintendo_switch`` so they match exactly.

    The vocabulary and IDF weights are fitted only on products available at
    the cutoff, so text statistics of future products do not leak in. Every
    product is then transformed, including new ones without interactions,
    which is what makes this model useful for item cold start.

User profile
    The recency-weighted sum of the vectors of the user's history items
    (``0.5 ** (age / half_life)``), L2-normalised. Score = cosine similarity
    between the profile and each item.

Users without history get recent popularity. A small popularity term is
added for every user to order items that have no text overlap.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from cartsense_ml.data.dataset import InteractionDataset
from cartsense_ml.models.base import Recommender
from cartsense_ml.models.popularity import DAY_MS, normalized_recent_popularity

_TOKEN_SAFE = re.compile(r"[^a-z0-9]+")


def _tag(prefix: str, value: str) -> str:
    return prefix + "_" + _TOKEN_SAFE.sub("_", value.lower()).strip("_")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def product_documents(products: pd.DataFrame, title_weight: int = 3, max_description_chars: int = 2000) -> list[str]:
    docs = []
    for row in products.itertuples(index=False):
        title = getattr(row, "title", None) or ""
        brand = getattr(row, "brand", None)
        categories = _as_list(getattr(row, "categories", None))
        features = _as_list(getattr(row, "features", None))
        description = (getattr(row, "description", None) or "")[:max_description_chars]
        tags = [_tag("cat", c) for c in categories]
        if brand:
            tags.append(_tag("brand", brand))
        parts = [title] * title_weight + ([brand] if brand else []) + categories + tags + features + [description]
        docs.append(" ".join(p for p in parts if p))
    return docs


class ContentTfidf(Recommender):
    name = "content_tfidf"

    def __init__(
        self,
        max_features: int = 50_000,
        ngram_max: int = 2,
        min_df: int = 2,
        half_life_days: float = 365.0,
        popularity_weight: float = 1e-3,
        seed: int = 42,
    ):
        super().__init__(seed=seed)
        self.max_features = max_features
        self.ngram_max = ngram_max
        self.min_df = min_df
        self.half_life_days = half_life_days
        self.popularity_weight = popularity_weight

    def params(self) -> dict[str, Any]:
        return {
            **super().params(),
            "max_features": self.max_features,
            "ngram_max": self.ngram_max,
            "min_df": self.min_df,
            "half_life_days": self.half_life_days,
            "popularity_weight": self.popularity_weight,
        }

    def _fit(self, ds: InteractionDataset) -> None:
        docs = product_documents(ds.products)
        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=(1, self.ngram_max),
            min_df=self.min_df,
            stop_words="english",
            sublinear_tf=True,
            dtype=np.float32,
        )
        available_docs = [d for d, a in zip(docs, ds.available) if a]
        self.vectorizer.fit(available_docs)
        self.item_vectors = normalize(self.vectorizer.transform(docs)).tocsr().astype(np.float32)
        self.item_vectors_t = self.item_vectors.T.tocsr()

        h = ds.history
        weights = np.power(0.5, (ds.cutoff_ms - h["timestamp"].to_numpy()) / DAY_MS / self.half_life_days)
        history_weights = sp.csr_matrix(
            (weights.astype(np.float32), (h["user_idx"].to_numpy(), h["item_idx"].to_numpy())),
            shape=(ds.n_users, ds.n_items),
        )
        self.user_profiles = normalize(history_weights @ self.item_vectors).tocsr()
        self.pop = normalized_recent_popularity(ds, half_life_days=180.0)

    def score(self, user_idx: np.ndarray) -> np.ndarray:
        scores = np.tile(self.popularity_weight * self.pop, (len(user_idx), 1))
        warm = np.flatnonzero(user_idx >= 0)
        if warm.size:
            sims = (self.user_profiles[user_idx[warm]] @ self.item_vectors_t).toarray()
            scores[warm] += sims
        cold = np.flatnonzero(user_idx < 0)
        if cold.size:
            scores[cold] = self.pop  # popularity only
        return scores

    # ------------------------------------------------------------------ #
    # Similar products and explanations
    # ------------------------------------------------------------------ #
    def similar_items(self, item_idx: int, k: int = 10, available_only: bool = True) -> list[tuple[int, float]]:
        sims = (self.item_vectors[item_idx] @ self.item_vectors_t).toarray().ravel()
        sims[item_idx] = -np.inf
        if available_only:
            sims[~self.ds.available] = -np.inf
        top = np.argsort(-sims, kind="stable")[:k]
        return [(int(i), float(sims[i])) for i in top if np.isfinite(sims[i]) and sims[i] > 0]

    def shared_terms(self, item_a: int, item_b: int, n: int = 3) -> list[str]:
        """Highest-weighted terms present in both products (readable ones first)."""
        a, b = self.item_vectors[item_a], self.item_vectors[item_b]
        common = np.intersect1d(a.indices, b.indices)
        if common.size == 0:
            return []
        weight = np.asarray(a[:, common].toarray()).ravel() * np.asarray(b[:, common].toarray()).ravel()
        vocab = self.vectorizer.get_feature_names_out()
        terms = [vocab[j] for j in common[np.argsort(-weight)]]
        # tag tokens are for matching; show their readable form
        pretty = [t.split("_", 1)[1].replace("_", " ") if t.startswith(("cat_", "brand_")) else t for t in terms]
        seen: list[str] = []
        for t in pretty:
            if t not in seen and not any(t in s for s in seen):
                seen.append(t)
            if len(seen) == n:
                break
        return seen
