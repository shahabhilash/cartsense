"""Request and response models (Pydantic)."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

EventType = Literal["view", "click", "search", "wishlist_add", "wishlist_remove", "add_to_cart"]


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    brand: str | None
    platform: str | None
    price: float | None
    image_url: str | None
    review_count: int
    popularity_rank: int | None


class ProductDetail(ProductOut):
    categories: list[str]
    features: list[str]
    description: str | None
    release_date: date | None


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


class Reason(BaseModel):
    type: str
    text: str
    item_id: str | None = None
    score: float | None = None
    source: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RecommendedProduct(BaseModel):
    product: ProductOut
    rank: int
    score: float
    reasons: list[Reason]
    impression_id: str


class RecommendationList(BaseModel):
    request_id: str
    model_version: str
    strategy: Literal["precomputed", "session_similarity", "popular"]
    variant: Literal["control", "treatment"] | None = None
    items: list[RecommendedProduct]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class DemoLoginIn(BaseModel):
    dataset_user_id: str = Field(min_length=1, max_length=64)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    display_name: str
    email: str | None
    is_demo: bool
    demo_platform: str | None


class DemoUserOut(BaseModel):
    dataset_user_id: str
    display_name: str
    platform: str | None
    reviews: int


class EventIn(BaseModel):
    event_type: EventType
    product_id: str | None = Field(default=None, max_length=20)
    query: str | None = Field(default=None, max_length=200)
    impression_id: str | None = Field(default=None, max_length=36)
    session_id: str | None = Field(default=None, max_length=64)


class EventOut(BaseModel):
    id: int
    event_type: str


class WishlistIn(BaseModel):
    product_id: str = Field(min_length=1, max_length=20)


class HistoryItem(BaseModel):
    product: ProductOut
    rating: float
    occurred_at: str


class ModelStats(BaseModel):
    model_version: str
    impressions: int
    clicks: int
    ctr: float


class VariantStats(BaseModel):
    variant: str
    units: int
    impressions: int
    clicks: int
    ctr: float
    converted_units: int
    conversion_rate: float


class ABTest(BaseModel):
    experiment: str
    enabled: bool
    control_share: float
    variants: list[VariantStats]
    ctr_lift: float | None
    ctr_p_value: float | None
    conversion_p_value: float | None


class AnalyticsOverview(BaseModel):
    events_by_type: dict[str, int]
    events_by_day: list[dict[str, Any]]
    recommendation_stats: list[ModelStats]
    active_model_version: str | None
    offline_metrics: list[dict[str, Any]]
    ab_test: ABTest
    synthetic_events_excluded: bool = True


TokenOut.model_rebuild()
