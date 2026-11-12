"""Serving logic for recommendations.

Three strategies, tried in order:

1. ``precomputed``: batch output of the active model version (the hybrid
   ranker) for users the model was trained on.
2. ``session_similarity``: for users the model has not seen (new sign-ups),
   items similar to what they viewed, clicked or wishlisted on the site,
   from the precomputed ``similar_items`` table, plus a popularity tiebreak.
   This is the item cold-start / new-user path and needs no ML runtime in the API.
3. ``popular``: recent popularity for users with no signal at all.

Every returned item is logged as an impression with the model version that
produced it, so clicks can be attributed per version.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Event, Impression, ModelVersion, Product, Recommendation, SimilarItem, User, WishlistItem

SESSION_STRATEGY_VERSION = "session-similarity-v1"
POPULAR_STRATEGY_VERSION = "popular-v1"
SIGNAL_EVENTS = ("view", "click", "wishlist_add", "add_to_cart")
SIGNAL_WEIGHTS = {"view": 1.0, "click": 1.5, "wishlist_add": 3.0, "add_to_cart": 3.0}


def active_version(db: Session) -> ModelVersion | None:
    return db.scalars(select(ModelVersion).where(ModelVersion.is_active.is_(True))).first()


def _excluded_products(db: Session, user: User | None) -> set[str]:
    if user is None:
        return set()
    wished = db.scalars(select(WishlistItem.product_id).where(WishlistItem.user_id == user.id))
    return set(wished)


def _popular(db: Session, k: int, exclude: set[str]) -> list[tuple[Product, float, list[dict]]]:
    rows = db.scalars(
        select(Product).where(Product.popularity_rank.is_not(None)).order_by(Product.popularity_rank).limit(k + len(exclude))
    )
    out = []
    for p in rows:
        if p.id in exclude:
            continue
        reason = {"type": "trending", "text": f"Trending: #{p.popularity_rank} in the store right now",
                  "details": {"rank": p.popularity_rank}}
        out.append((p, 1.0 / p.popularity_rank, [reason]))
        if len(out) == k:
            break
    return out


def _session_similarity(db: Session, user: User, k: int, exclude: set[str]):
    events = db.execute(
        select(Event.product_id, Event.event_type)
        .where(Event.user_id == user.id, Event.product_id.is_not(None), Event.event_type.in_(SIGNAL_EVENTS),
               Event.is_synthetic.is_(False))
        .order_by(Event.created_at.desc())
        .limit(50)
    ).all()
    wished = list(db.scalars(select(WishlistItem.product_id).where(WishlistItem.user_id == user.id)))
    signals: dict[str, float] = defaultdict(float)
    for pid, etype in events:
        signals[pid] += SIGNAL_WEIGHTS.get(etype, 1.0)
    for pid in wished:
        signals[pid] += SIGNAL_WEIGHTS["wishlist_add"]
    if not signals:
        return []

    seen = set(signals) | exclude
    scores: dict[str, float] = defaultdict(float)
    because: dict[str, tuple[str, float]] = {}
    for row in db.scalars(select(SimilarItem).where(SimilarItem.product_id.in_(list(signals)))):
        if row.similar_id in seen:
            continue
        contribution = signals[row.product_id] * row.score
        scores[row.similar_id] += contribution
        if contribution > because.get(row.similar_id, ("", 0.0))[1]:
            because[row.similar_id] = (row.product_id, contribution)
    if not scores:
        return []
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(list(scores) + list(signals))))}
    ranked = sorted(scores, key=lambda pid: (-scores[pid], products[pid].popularity_rank or 10**9))[:k]
    out = []
    for pid in ranked:
        source_id = because[pid][0]
        source = products.get(source_id)
        reason = {"type": "similar_to_session", "item_id": source_id,
                  "text": f'Similar to "{source.title if source else source_id}" you looked at',
                  "score": round(scores[pid], 4)}
        out.append((products[pid], scores[pid], [reason]))
    return out


def recommend_for_user(db: Session, user: User | None, k: int, surface: str) -> dict:
    exclude = _excluded_products(db, user)
    version = active_version(db)
    items: list[tuple[Product, float, list[dict]]] = []
    strategy, version_id = "popular", POPULAR_STRATEGY_VERSION

    if user is not None and version is not None:
        rows = db.execute(
            select(Recommendation, Product)
            .join(Product, Product.id == Recommendation.product_id)
            .where(Recommendation.user_id == user.id, Recommendation.model_version_id == version.id)
            .order_by(Recommendation.rank)
        ).all()
        items = [(p, r.score, r.reasons) for r, p in rows if p.id not in exclude][:k]
        if items:
            strategy, version_id = "precomputed", version.id
    if not items and user is not None:
        items = _session_similarity(db, user, k, exclude)
        if items:
            strategy, version_id = "session_similarity", SESSION_STRATEGY_VERSION
    if not items:
        items = _popular(db, k, exclude)

    request_id = str(uuid.uuid4())
    out = []
    for position, (product, score, reasons) in enumerate(items, start=1):
        impression = Impression(id=str(uuid.uuid4()), request_id=request_id, user_id=user.id if user else None,
                                surface=surface, model_version=version_id, product_id=product.id, position=position)
        db.add(impression)
        out.append({"product": product, "rank": position, "score": float(score), "reasons": reasons,
                    "impression_id": impression.id})
    db.commit()
    return {"request_id": request_id, "model_version": version_id, "strategy": strategy, "items": out}


def similar_products(db: Session, product_id: str, k: int) -> list[tuple[Product, float]]:
    rows = db.execute(
        select(SimilarItem, Product)
        .join(Product, Product.id == SimilarItem.similar_id)
        .where(SimilarItem.product_id == product_id)
        .order_by(SimilarItem.rank)
        .limit(k)
    ).all()
    return [(p, s.score) for s, p in rows]
