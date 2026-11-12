"""Load the ML export into the database.

    python -m app.load_data --export-dir ../../artifacts/export --results-dir ../../reports/results/test
    python -m app.load_data --create-api-key "partner-store"

Loading is idempotent: catalogue, similar items and demo users are replaced,
and the exported model version becomes the active one. Store accounts,
events and wishlists are left untouched.
"""

from __future__ import annotations

import argparse
import json
import math
import secrets
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import (
    ApiClient,
    Interaction,
    ModelVersion,
    Product,
    Recommendation,
    SessionLocal,
    SimilarItem,
    User,
    init_db,
)
from app.security import hash_api_key

CHUNK = 5000


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _bulk(db: Session, table, rows: list[dict]) -> None:
    for s in range(0, len(rows), CHUNK):
        db.execute(insert(table), rows[s : s + CHUNK])


def load_export(db: Session, export_dir: Path, results_dir: Path | None = None) -> dict[str, int]:
    products = pd.read_parquet(export_dir / "products.parquet")
    popular = pd.read_parquet(export_dir / "popular.parquet").set_index("product_id")["rank"]
    similar = pd.read_parquet(export_dir / "similar_items.parquet")
    recs = pd.read_parquet(export_dir / "recommendations.parquet")
    demo = pd.read_parquet(export_dir / "demo_users.parquet")
    history = pd.read_parquet(export_dir / "demo_history.parquet")
    version = json.loads((export_dir / "model_version.json").read_text(encoding="utf-8"))
    # Offline metrics travel with the model version, so a deployment needs no files
    version["offline_metrics"] = _offline_metrics(results_dir)

    # Replace derived tables (children first)
    demo_ids = select(User.id).where(User.is_demo.is_(True))
    db.execute(delete(Recommendation))
    db.execute(delete(Interaction).where(Interaction.user_id.in_(demo_ids)))
    db.execute(delete(SimilarItem))
    db.execute(delete(User).where(User.is_demo.is_(True)))
    db.execute(delete(Product).where(~Product.id.in_(products["item_id"].tolist())))
    db.flush()

    existing = set(db.scalars(select(Product.id)))
    rows = []
    for p in products.itertuples(index=False):
        rows.append({
            "id": p.item_id, "title": p.title, "brand": _clean(p.brand), "platform": _clean(p.platform),
            "categories": _clean(p.categories) or [], "features": _clean(p.features) or [],
            "description": _clean(p.description), "price": _clean(p.price), "image_url": _clean(p.image_url),
            "release_date": _clean(p.date_first_available), "review_count": int(p.review_count),
            "popularity_rank": int(popular.get(p.item_id)) if p.item_id in popular.index else None,
        })
    _bulk(db, Product, [r for r in rows if r["id"] not in existing])
    for r in (r for r in rows if r["id"] in existing):
        db.execute(update(Product).where(Product.id == r["id"]).values(**r))

    _bulk(db, SimilarItem, similar.rename(columns={})[["product_id", "rank", "similar_id", "score"]].to_dict("records"))

    _bulk(db, User, [
        {"display_name": f"Shopper {i + 1}" + (f" ({d.top_platform})" if d.top_platform else ""),
         "dataset_user_id": d.user_id, "is_demo": True, "demo_platform": d.top_platform}
        for i, d in enumerate(demo.itertuples(index=False))
    ])
    user_ids = dict(db.execute(select(User.dataset_user_id, User.id).where(User.is_demo.is_(True))).all())

    _bulk(db, Interaction, [
        {"user_id": user_ids[h.user_id], "product_id": h.product_id, "rating": float(h.rating),
         "occurred_at": datetime.fromtimestamp(h.timestamp / 1000, tz=timezone.utc), "source": "amazon_review"}
        for h in history.itertuples(index=False)
    ])

    db.execute(update(ModelVersion).values(is_active=False))
    if db.get(ModelVersion, version["version"]) is None:
        db.add(ModelVersion(id=version["version"], model=version["model"], details=version, is_active=True))
    else:
        db.execute(update(ModelVersion).where(ModelVersion.id == version["version"])
                   .values(is_active=True, details=version))
    db.flush()
    _bulk(db, Recommendation, [
        {"user_id": user_ids[r.user_id], "model_version_id": version["version"], "rank": int(r.rank),
         "product_id": r.product_id, "score": float(r.score), "reasons": json.loads(r.reasons_json)}
        for r in recs.itertuples(index=False)
    ])
    db.commit()
    return {"products": len(rows), "similar_items": len(similar), "demo_users": len(demo),
            "history_rows": len(history), "recommendations": len(recs)}


def _offline_metrics(results_dir: Path | None) -> list[dict]:
    """Compact K=10 metrics from the evaluation result files (reports/results/test)."""
    if results_dir is None or not results_dir.exists():
        return []
    offline = []
    for f in sorted(results_dir.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        offline.append({"model": r["label"], "stage": r["stage"],
                        **{k: round(v, 5) for k, v in r["overall"].items() if k.endswith("@10")}})
    return offline


def create_api_key(db: Session, name: str) -> str:
    key = "cs_" + secrets.token_urlsafe(32)
    db.add(ApiClient(name=name, key_hash=hash_api_key(key)))
    db.commit()
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export-dir", type=Path, default=get_settings().export_dir)
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--create-api-key", metavar="CLIENT_NAME")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        if args.create_api_key:
            key = create_api_key(db, args.create_api_key)
            print(f"API key for {args.create_api_key} (shown once, store it safely): {key}")
            return
        print(load_export(db, args.export_dir, args.results_dir))


if __name__ == "__main__":
    main()
