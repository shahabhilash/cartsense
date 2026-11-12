"""Clean the converted interactions and products.

The 5-core interaction table is small enough to hold in memory (about 0.8M
rows x 4 columns for Video Games); the large file, the metadata, has already
been streamed and filtered in :mod:`cartsense_ml.data.convert`.

Every rule that drops rows is counted, so the report shows exactly how the
raw files became the processed tables.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

INTERACTION_COLUMNS = ["user_id", "item_id", "rating", "timestamp"]


@dataclass
class CleanReport:
    raw_interactions: int = 0
    dropped_missing_fields: int = 0
    dropped_invalid_rating: int = 0
    dropped_duplicate_pairs: int = 0
    dropped_unknown_or_untitled_item: int = 0
    interactions: int = 0
    raw_products: int = 0
    dropped_duplicate_products: int = 0
    dropped_untitled_products: int = 0
    dropped_products_without_interactions: int = 0
    products: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def clean_interactions(
    ratings: pd.DataFrame,
    valid_item_ids: set[str],
    report: CleanReport,
) -> pd.DataFrame:
    df = ratings.rename(columns={"parent_asin": "item_id"})[INTERACTION_COLUMNS]
    report.raw_interactions = len(df)

    before = len(df)
    df = df.dropna(subset=["user_id", "item_id", "rating", "timestamp"])
    report.dropped_missing_fields = before - len(df)

    before = len(df)
    df = df[df["rating"].between(1, 5)]
    report.dropped_invalid_rating = before - len(df)

    # A user can review the same product more than once; keep the latest review
    # so each (user, item) pair is a single implicit-feedback signal.
    before = len(df)
    df = df.sort_values(["user_id", "item_id", "timestamp"]).drop_duplicates(
        ["user_id", "item_id"], keep="last"
    )
    report.dropped_duplicate_pairs = before - len(df)

    before = len(df)
    df = df[df["item_id"].isin(valid_item_ids)]
    report.dropped_unknown_or_untitled_item = before - len(df)

    df = df.sort_values(["timestamp", "user_id", "item_id"], kind="mergesort").reset_index(drop=True)
    df["rating"] = df["rating"].astype("float32")
    df["timestamp"] = df["timestamp"].astype("int64")
    report.interactions = len(df)
    return df


def clean_products(products: pd.DataFrame, require_title: bool, report: CleanReport) -> pd.DataFrame:
    """Deduplicate products and drop those without a title (they cannot be shown in the store)."""
    report.raw_products = len(products)
    before = len(products)
    products = products.drop_duplicates("item_id", keep="first")
    report.dropped_duplicate_products = before - len(products)
    if require_title:
        before = len(products)
        products = products[products["title"].notna() & (products["title"].str.len() > 0)]
        report.dropped_untitled_products = before - len(products)
    return products.reset_index(drop=True)


def run_clean(
    ratings_path: Path,
    products_path: Path,
    out_dir: Path,
    require_title: bool = True,
) -> CleanReport:
    """Read the interim Parquet files, clean them and write processed tables."""
    report = CleanReport()
    products = clean_products(pd.read_parquet(products_path), require_title, report)
    interactions = clean_interactions(
        pd.read_parquet(ratings_path), set(products["item_id"]), report
    )

    # Only products that still have interactions belong to the catalogue
    rated = set(interactions["item_id"])
    before = len(products)
    products = products[products["item_id"].isin(rated)].reset_index(drop=True)
    report.dropped_products_without_interactions = before - len(products)
    report.products = len(products)

    out_dir.mkdir(parents=True, exist_ok=True)
    interactions.to_parquet(out_dir / "interactions.parquet", index=False)
    products.to_parquet(out_dir / "products.parquet", index=False)
    log.info("clean: %s", report.to_dict())
    return report
