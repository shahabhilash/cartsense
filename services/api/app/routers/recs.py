"""Recommendations, behaviour events, analytics and the partner API."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import ApiClient, Event, Impression, Product, User, get_db
from app.experiments import ab_results
from app.recommend import active_version, recommend_for_user
from app.routers.catalog import _hide_images
from app.schemas import AnalyticsOverview, EventIn, EventOut, RecommendationList
from app.security import api_client, optional_user

router = APIRouter(tags=["recommendations"])


def _serialise(result: dict) -> dict:
    _hide_images([i["product"] for i in result["items"]])
    return result


@router.get("/recommendations", response_model=RecommendationList)
def recommendations(
    k: int = Query(default=12, ge=1, le=20),
    surface: str = Query(default="home", pattern="^(home|product|cart|wishlist)$"),
    user: User | None = Depends(optional_user),
    x_session_id: str | None = Header(default=None, max_length=64),
    db: Session = Depends(get_db),
):
    """Recommendations for the signed-in user or the guest's browser session
    (sent as the X-Session-Id header)."""
    result = recommend_for_user(db, user, k, surface, session_id=x_session_id)
    db.expunge_all()
    return _serialise(result)


@router.post("/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def log_event(body: EventIn, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    if body.product_id and db.get(Product, body.product_id) is None:
        raise HTTPException(404, f"product {body.product_id} not found")
    if body.impression_id and db.get(Impression, body.impression_id) is None:
        raise HTTPException(422, "unknown impression_id")
    if body.event_type == "search" and not body.query:
        raise HTTPException(422, "search events need a query")
    event = Event(user_id=user.id if user else None, session_id=body.session_id, event_type=body.event_type,
                  product_id=body.product_id, query=body.query, impression_id=body.impression_id,
                  is_synthetic=False)
    db.add(event)
    db.commit()
    return {"id": event.id, "event_type": event.event_type}


@router.get("/analytics/overview", response_model=AnalyticsOverview)
def analytics(days: int = Query(default=14, ge=1, le=90), db: Session = Depends(get_db)):
    """Store activity and recommendation click-through per model version.
    Synthetic events are excluded from every number."""
    real = Event.is_synthetic.is_(False)
    by_type = dict(db.execute(select(Event.event_type, func.count()).where(real).group_by(Event.event_type)).all())

    since = datetime.now(timezone.utc) - timedelta(days=days)
    day = func.date(Event.created_at)
    by_day = [{"date": str(d), "events": n} for d, n in
              db.execute(select(day, func.count()).where(real, Event.created_at >= since).group_by(day).order_by(day))]

    impressions = dict(db.execute(select(Impression.model_version, func.count()).group_by(Impression.model_version)).all())
    clicks = dict(db.execute(
        select(Impression.model_version, func.count(func.distinct(Event.impression_id)))
        .join(Impression, Impression.id == Event.impression_id)
        .where(real, Event.event_type == "click").group_by(Impression.model_version)
    ).all())
    stats = [{"model_version": v, "impressions": n, "clicks": clicks.get(v, 0),
              "ctr": round(clicks.get(v, 0) / n, 4) if n else 0.0} for v, n in sorted(impressions.items())]

    version = active_version(db)
    offline = (version.details or {}).get("offline_metrics", []) if version else []
    settings = get_settings()
    return {"events_by_type": by_type, "events_by_day": by_day, "recommendation_stats": stats,
            "active_model_version": version.id if version else None, "offline_metrics": offline,
            "ab_test": ab_results(db, settings.ab_experiment, settings.ab_control_share)}


@router.get("/partner/recommendations/{dataset_user_id}", response_model=RecommendationList)
def partner_recommendations(
    dataset_user_id: str,
    k: int = Query(default=10, ge=1, le=20),
    client: ApiClient = Depends(api_client),
    db: Session = Depends(get_db),
):
    """For external stores: recommendations for one of their users (identified
    by the dataset user id here), authenticated with an API key."""
    user = db.scalars(select(User).where(User.dataset_user_id == dataset_user_id)).first()
    result = recommend_for_user(db, user, k, surface="partner")
    db.expunge_all()
    return _serialise(result)
