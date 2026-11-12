"""Products, search and similar products."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Product, get_db
from app.recommend import similar_products
from app.schemas import ProductDetail, ProductOut, ProductPage

router = APIRouter(tags=["catalog"])


def _hide_images(products):
    if not get_settings().show_product_images:
        for p in products:
            p.image_url = None
    return products


@router.get("/products", response_model=ProductPage)
def list_products(
    q: str | None = Query(default=None, max_length=100, description="search in title and brand"),
    platform: str | None = Query(default=None, max_length=100),
    sort: str = Query(default="popular", pattern="^(popular|price_asc|price_desc|newest)$"),
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Product)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Product.title.ilike(like), Product.brand.ilike(like)))
    if platform:
        stmt = stmt.where(Product.platform == platform)
    order = {
        "popular": Product.popularity_rank.asc().nulls_last(),
        "price_asc": Product.price.asc().nulls_last(),
        "price_desc": Product.price.desc().nulls_last(),
        "newest": Product.release_date.desc().nulls_last(),
    }[sort]
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(order, Product.id).offset((page - 1) * page_size).limit(page_size)).all()
    db.expunge_all()  # image hiding must not be written back
    return {"items": _hide_images(rows), "total": total, "page": page, "page_size": page_size}


@router.get("/platforms", response_model=list[dict])
def platforms(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Product.platform, func.count()).where(Product.platform.is_not(None))
        .group_by(Product.platform).order_by(func.count().desc()).limit(20)
    ).all()
    return [{"platform": p, "products": n} for p, n in rows]


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, f"product {product_id} not found")
    db.expunge(product)
    return _hide_images([product])[0]


@router.get("/products/{product_id}/similar", response_model=list[ProductOut])
def get_similar(product_id: str, k: int = Query(default=8, ge=1, le=20), db: Session = Depends(get_db)):
    if db.get(Product, product_id) is None:
        raise HTTPException(404, f"product {product_id} not found")
    items = [p for p, _ in similar_products(db, product_id, k)]
    db.expunge_all()
    return _hide_images(items)
