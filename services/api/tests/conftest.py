"""Test app on an in-memory SQLite database, loaded from a tiny export."""

import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

os.environ["CARTSENSE_DATABASE_URL"] = "sqlite://"
os.environ["CARTSENSE_JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.load_data import create_api_key, load_export  # noqa: E402
from app.main import app  # noqa: E402

PRODUCTS = [
    ("P1", "Zelda Breath of the Wild", "Nintendo", "Nintendo Switch", 59.99),
    ("P2", "Zelda Tears of the Kingdom", "Nintendo", "Nintendo Switch", 69.99),
    ("P3", "Forza Horizon", "Microsoft", "PC", None),
    ("P4", "Racing Wheel Pro", "Logitech", "PC", 199.0),
    ("P5", "Mario Kart", "Nintendo", "Nintendo Switch", 49.99),
]


def write_export(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "item_id": [p[0] for p in PRODUCTS],
            "title": [p[1] for p in PRODUCTS],
            "brand": [p[2] for p in PRODUCTS],
            "main_category": ["Video Games"] * 5,
            "categories": [["Video Games", p[3]] for p in PRODUCTS],
            "features": [["feature"]] * 5,
            "description": ["desc"] * 5,
            "price": [p[4] for p in PRODUCTS],
            "image_url": ["https://example.com/img.jpg"] * 5,
            "date_first_available": [date(2020, 1, 1)] * 5,
            "platform": [p[3] for p in PRODUCTS],
            "review_count": [50, 40, 30, 20, 10],
        }
    ).to_parquet(path / "products.parquet")
    pd.DataFrame({"product_id": ["P5", "P1", "P3", "P2", "P4"], "rank": [1, 2, 3, 4, 5],
                  "score": [5.0, 4.0, 3.0, 2.0, 1.0]}).to_parquet(path / "popular.parquet")
    pd.DataFrame({"product_id": ["P1", "P1", "P3"], "similar_id": ["P2", "P5", "P4"], "rank": [1, 2, 1],
                  "score": [0.9, 0.4, 0.7]}).to_parquet(path / "similar_items.parquet")
    reasons = json.dumps([{"type": "also_reviewed_with", "text": "People who reviewed X also reviewed this",
                           "item_id": "P1", "source": "knn"}])
    pd.DataFrame({"user_id": ["AUSER1", "AUSER1"], "product_id": ["P2", "P5"], "rank": [1, 2],
                  "score": [0.8, 0.5], "reasons_json": [reasons, reasons]}).to_parquet(path / "recommendations.parquet")
    pd.DataFrame({"user_id": ["AUSER1"], "n_interactions": [1], "top_platform": ["Nintendo Switch"]}).to_parquet(
        path / "demo_users.parquet")
    pd.DataFrame({"user_id": ["AUSER1"], "product_id": ["P1"], "rating": [5.0],
                  "timestamp": [1_600_000_000_000]}).to_parquet(path / "demo_history.parquet")
    (path / "model_version.json").write_text(json.dumps({"version": "hybrid-test", "model": "hybrid"}))
    return path


def write_results(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "hybrid.json").write_text(json.dumps({"label": "hybrid", "stage": "test",
                                                  "overall": {"ndcg@10": 0.0182, "recall@10": 0.0287, "ndcg@20": 0.02}}))
    return path


@pytest.fixture()
def client(tmp_path):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        load_export(db, write_export(tmp_path / "export"), results_dir=write_results(tmp_path / "results"))
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def api_key():
    with SessionLocal() as db:
        return create_api_key(db, "partner")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
