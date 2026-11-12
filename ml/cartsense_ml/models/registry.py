"""Name -> class lookup so experiments can be described in YAML."""

from __future__ import annotations

from typing import Any

from cartsense_ml.models.base import Recommender
from cartsense_ml.models.collaborative import ALS, ItemKNN
from cartsense_ml.models.content import ContentTfidf
from cartsense_ml.models.popularity import CategoryPopular, MostPopular, RandomRecommender, RecentPopular

MODELS: dict[str, type[Recommender]] = {
    "random": RandomRecommender,
    "most_popular": MostPopular,
    "recent_popular": RecentPopular,
    "category_popular": CategoryPopular,
    "content_tfidf": ContentTfidf,
    "item_knn": ItemKNN,
    "als": ALS,
}


def build_model(name: str, params: dict[str, Any] | None = None, seed: int = 42) -> Recommender:
    if name not in MODELS:
        raise KeyError(f"unknown model {name!r}; available: {sorted(MODELS)}")
    return MODELS[name](seed=seed, **(params or {}))
