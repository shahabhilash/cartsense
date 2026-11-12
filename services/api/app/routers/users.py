"""Auth (email + password, or a demo persona), wishlist and history."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Event, Interaction, Product, User, WishlistItem, get_db
from app.routers.catalog import _hide_images
from app.schemas import (
    DemoLoginIn,
    DemoUserOut,
    HistoryItem,
    LoginIn,
    ProductOut,
    RegisterIn,
    TokenOut,
    UserOut,
    WishlistIn,
)
from app.security import create_token, current_user, hash_password, verify_password

router = APIRouter(tags=["users"])


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), display_name=body.display_name)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "an account with this email already exists")
    return {"access_token": create_token(user.id), "user": user}


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong email or password")
    return {"access_token": create_token(user.id), "user": user}


@router.get("/auth/demo-users", response_model=list[DemoUserOut])
def demo_users(limit: int = 12, db: Session = Depends(get_db)):
    """A few dataset shoppers to browse as, one or two per platform."""
    rows = db.scalars(select(User).where(User.is_demo.is_(True)).order_by(User.id).limit(500)).all()
    picked, per_platform = [], {}
    for u in rows:
        if per_platform.get(u.demo_platform, 0) >= 2:
            continue
        per_platform[u.demo_platform] = per_platform.get(u.demo_platform, 0) + 1
        n = db.query(Interaction).filter_by(user_id=u.id).count()
        picked.append({"dataset_user_id": u.dataset_user_id, "display_name": u.display_name,
                       "platform": u.demo_platform, "reviews": n})
        if len(picked) == min(limit, 24):
            break
    return picked


@router.post("/auth/demo", response_model=TokenOut)
def demo_login(body: DemoLoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.dataset_user_id == body.dataset_user_id, User.is_demo.is_(True))).first()
    if user is None:
        raise HTTPException(404, "unknown demo user")
    return {"access_token": create_token(user.id), "user": user}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.get("/me/history", response_model=list[HistoryItem])
def history(limit: int = 20, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Interaction, Product).join(Product, Product.id == Interaction.product_id)
        .where(Interaction.user_id == user.id).order_by(Interaction.occurred_at.desc()).limit(min(limit, 100))
    ).all()
    db.expunge_all()
    return [{"product": _hide_images([p])[0], "rating": i.rating, "occurred_at": i.occurred_at.isoformat()}
            for i, p in rows]


@router.get("/me/wishlist", response_model=list[ProductOut])
def get_wishlist(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Product).join(WishlistItem, WishlistItem.product_id == Product.id)
        .where(WishlistItem.user_id == user.id).order_by(WishlistItem.added_at.desc())
    ).all()
    db.expunge_all()
    return _hide_images(rows)


@router.post("/me/wishlist", status_code=status.HTTP_201_CREATED)
def add_wishlist(body: WishlistIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Product, body.product_id) is None:
        raise HTTPException(404, f"product {body.product_id} not found")
    if db.get(WishlistItem, (user.id, body.product_id)) is None:
        db.add(WishlistItem(user_id=user.id, product_id=body.product_id))
        db.add(Event(user_id=user.id, event_type="wishlist_add", product_id=body.product_id))
        db.commit()
    return {"product_id": body.product_id, "wishlisted": True}


@router.delete("/me/wishlist/{product_id}")
def remove_wishlist(product_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(WishlistItem, (user.id, product_id))
    if item is None:
        raise HTTPException(404, "product is not in the wishlist")
    db.delete(item)
    db.add(Event(user_id=user.id, event_type="wishlist_remove", product_id=product_id))
    db.commit()
    return {"product_id": product_id, "wishlisted": False}
