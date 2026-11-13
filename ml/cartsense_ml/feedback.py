"""Turn real store behaviour into training interactions for the next retrain.

    python -m cartsense_ml.feedback --out data/processed/site_interactions.parquet

The database URL is read from ``CARTSENSE_DATABASE_URL`` (or ``--database-url``).

Which events count
    Only real events (``is_synthetic = false``) about a product: add to bag,
    wishlist, click and view. Their strength becomes the interaction rating,
    so the strongest signal a shopper gave for a product wins:
    add_to_cart / wishlist_add = 5, click = 4, view = 3.

Whose events
    * demo shoppers map back to their dataset user id, so their new activity
      joins their real review history;
    * store accounts become ``site:<account id>``;
    * guest sessions become ``session:<id>`` and are kept only if they touched
      at least ``min_session_items`` different products (a single page view
      says little and would add noise).

Time
    The catalogue and reviews end in 2023, while the store runs today. If store
    events kept their real timestamps, recency weighting would treat them as
    years newer than everything else and let a handful of clicks dominate
    popularity. ``merge_site_interactions`` therefore places store activity
    immediately after the last dataset interaction, keeping its order: it is
    the most recent behaviour, but on the dataset's timeline.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import pandas as pd

from cartsense_ml.config import REPO_ROOT

log = logging.getLogger("cartsense_ml.feedback")

EVENT_STRENGTH = {"add_to_cart": 5.0, "wishlist_add": 5.0, "click": 4.0, "view": 3.0}
COLUMNS = ["user_id", "item_id", "rating", "timestamp", "source"]


def normalize_url(url: str) -> str:
    url = url.strip().strip("'\"")
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def load_site_events(database_url: str) -> pd.DataFrame:
    """Real product events from the store database, with the dataset id of demo shoppers."""
    from sqlalchemy import create_engine, text

    engine = create_engine(normalize_url(database_url))
    types = ", ".join(f"'{t}'" for t in EVENT_STRENGTH)
    query = text(
        f"""
        SELECT e.user_id, e.session_id, e.event_type, e.product_id, e.created_at, u.dataset_user_id
        FROM events e LEFT JOIN users u ON u.id = e.user_id
        WHERE e.is_synthetic = :synthetic AND e.product_id IS NOT NULL AND e.event_type IN ({types})
        """
    )
    with engine.connect() as conn:
        events = pd.read_sql(query, conn, params={"synthetic": False})
    engine.dispose()
    return events


def to_interactions(events: pd.DataFrame, catalogue: set[str], min_session_items: int = 2) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(columns=COLUMNS)
    df = events.copy()

    def owner(row) -> str | None:
        if isinstance(row.dataset_user_id, str) and row.dataset_user_id:
            return row.dataset_user_id
        if pd.notna(row.user_id):
            return f"site:{int(row.user_id)}"
        if isinstance(row.session_id, str) and row.session_id:
            return f"session:{row.session_id}"
        return None

    df["user_id"] = [owner(r) for r in df.itertuples(index=False)]
    df = df[df["user_id"].notna() & df["product_id"].isin(catalogue)]
    df["rating"] = df["event_type"].map(EVENT_STRENGTH).astype("float32")
    df["timestamp"] = (pd.to_datetime(df["created_at"], utc=True).astype("int64") // 1_000_000).astype("int64")
    df = df.rename(columns={"product_id": "item_id"})

    # Strongest signal per (user, item); its time is the latest event for that pair
    out = (
        df.groupby(["user_id", "item_id"], as_index=False)
        .agg(rating=("rating", "max"), timestamp=("timestamp", "max"))
    )
    sessions = out["user_id"].str.startswith("session:")
    items_per_session = out[sessions].groupby("user_id")["item_id"].nunique()
    keep_sessions = set(items_per_session[items_per_session >= min_session_items].index)
    out = out[~sessions | out["user_id"].isin(keep_sessions)]
    out["source"] = "store"
    return out[COLUMNS].sort_values("timestamp").reset_index(drop=True)


def merge_site_interactions(interactions: pd.DataFrame, site: pd.DataFrame) -> pd.DataFrame:
    """Append store interactions after the dataset's last timestamp (order kept)
    and keep the latest interaction per (user, item)."""
    base = interactions.assign(source="dataset") if "source" not in interactions else interactions
    if site is None or site.empty:
        return base.reset_index(drop=True)
    last = int(base["timestamp"].max())
    site = site.sort_values("timestamp", kind="mergesort").copy()
    site["timestamp"] = last + 1 + pd.RangeIndex(len(site)).to_numpy()
    merged = pd.concat([base, site[base.columns.intersection(site.columns)]], ignore_index=True)
    merged = merged.sort_values(["user_id", "item_id", "timestamp"]).drop_duplicates(["user_id", "item_id"], keep="last")
    return merged.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", default=os.environ.get("CARTSENSE_DATABASE_URL"))
    parser.add_argument("--products", type=Path, default=REPO_ROOT / "data" / "processed" / "products.parquet")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "processed" / "site_interactions.parquet")
    parser.add_argument("--min-session-items", type=int, default=2)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not args.database_url:
        parser.error("set CARTSENSE_DATABASE_URL or pass --database-url")

    catalogue = set(pd.read_parquet(args.products, columns=["item_id"])["item_id"])
    events = load_site_events(args.database_url)
    site = to_interactions(events, catalogue, args.min_session_items)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    site.to_parquet(args.out, index=False)
    kinds = site["user_id"].str.split(":").str[0].where(site["user_id"].str.contains(":"), "demo")
    summary = {
        "events_read": int(len(events)),
        "interactions": int(len(site)),
        "by_shopper_type": {k: int(v) for k, v in kinds.value_counts().items()},
        "out": str(args.out),
    }
    log.info("store feedback: %s", summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
