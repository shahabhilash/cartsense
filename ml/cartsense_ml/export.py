"""Train the production recommender on all data and export what the API serves.

    python -m cartsense_ml.export --out artifacts/export --demo-users 2000

Outputs (Parquet + JSON, consumed by services/api/app/load_data.py):
* ``products.parquet``         catalogue shown in the store
* ``recommendations.parquet``  top-N per demo user, with score and reasons
* ``similar_items.parquet``    top-K text-similar products for every product
* ``popular.parquet``          recent-popularity ranking (cold start, trending)
* ``demo_users.parquet``       dataset users the store can log in as
* ``model_version.json``       version id, config, git revision, timestamp

The model is fitted on every real interaction (train + val + test), because
at serving time all history is in the past. Offline metrics come from the
evaluation runs, not from this model.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from cartsense_ml.config import REPO_ROOT, load_data_config
from cartsense_ml.data.dataset import build_dataset
from cartsense_ml.data.stats import platform_of
from cartsense_ml.explain import Explainer
from cartsense_ml.models.hybrid import HybridRanker
from cartsense_ml.models.popularity import recency_weighted_counts
from cartsense_ml.tracking import git_revision, setup_mlflow

log = logging.getLogger("cartsense_ml.export")


def explain_hybrid(model: HybridRanker, user_idx: int, items: np.ndarray, explainers: dict) -> list[list[dict]]:
    """Reasons for hybrid recommendations: each item is explained by the
    candidate model that ranked it highest for this user."""
    labels = [lbl for lbl in model.gens if lbl in explainers]
    ranks = {}
    for lbl in labels:
        row = model.gens[lbl].score(np.array([user_idx]))[0]
        order = np.argsort(-row)
        rank = np.empty_like(order)
        rank[order] = np.arange(len(order))
        ranks[lbl] = rank[items]
    out = []
    for j, item in enumerate(items):
        best = min(labels, key=lambda lbl: ranks[lbl][j]) if labels else None
        reasons = explainers[best].explain(user_idx, int(item)) if best else []
        out.append([{**r.to_dict(), "source": best} for r in reasons])
    return out


def similar_items_table(content, ds, k: int, chunk: int = 2000) -> pd.DataFrame:
    vectors, vectors_t = content.item_vectors, content.item_vectors_t
    rows = []
    for s in range(0, ds.n_items, chunk):
        sims = (vectors[s : s + chunk] @ vectors_t).toarray()
        idx = np.arange(s, min(s + chunk, ds.n_items))
        sims[np.arange(len(idx)), idx] = -1  # not similar to itself
        top = np.argpartition(-sims, k, axis=1)[:, :k]
        top_s = np.take_along_axis(sims, top, axis=1)
        order = np.argsort(-top_s, axis=1)
        top, top_s = np.take_along_axis(top, order, 1), np.take_along_axis(top_s, order, 1)
        for r, i in enumerate(idx):
            for rank, (j, sc) in enumerate(zip(top[r], top_s[r]), start=1):
                if sc > 0:
                    rows.append((ds.item_ids[i], ds.item_ids[j], rank, float(sc)))
    return pd.DataFrame(rows, columns=["product_id", "similar_id", "rank", "score"])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "ml" / "configs" / "data.yaml")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "artifacts" / "export")
    parser.add_argument("--demo-users", type=int, default=2000)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--similar-k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = load_data_config(args.config)
    interactions = pd.read_parquet(cfg.paths.processed_dir / "interactions.parquet")
    products = pd.read_parquet(cfg.paths.processed_dir / "products.parquet")
    ds = build_dataset(interactions, products)
    log.info("fitting production hybrid on %d interactions", len(interactions))

    start = time.perf_counter()
    model = HybridRanker(n_candidates=100, seed=args.seed).fit(ds)
    fit_seconds = time.perf_counter() - start

    # Demo users: the most active dataset users (richest histories to show)
    counts = np.diff(ds.matrix.indptr)
    demo = np.argsort(-counts, kind="stable")[: args.demo_users]
    recs = model.recommend(demo, k=args.top_n)
    scores = model.score(demo)
    explainers = {lbl: Explainer(g) for lbl, g in model.gens.items() if lbl in ("als", "knn", "content")}
    rec_rows = []
    for r, u in enumerate(demo):
        reasons = explain_hybrid(model, int(u), recs[r], explainers)
        for rank, (item, why) in enumerate(zip(recs[r], reasons), start=1):
            rec_rows.append((ds.user_ids[u], ds.item_ids[item], rank, float(scores[r, item]), json.dumps(why)))
    recs_df = pd.DataFrame(rec_rows, columns=["user_id", "product_id", "rank", "score", "reasons_json"])

    platforms = [platform_of(c) for c in ds.products["categories"]]
    demo_rows = []
    for u in demo:
        hist = ds.matrix[u].indices
        top_platform = Counter(platforms[i] for i in hist if platforms[i]).most_common(1)
        demo_rows.append((ds.user_ids[u], int(counts[u]), top_platform[0][0] if top_platform else None))
    demo_df = pd.DataFrame(demo_rows, columns=["user_id", "n_interactions", "top_platform"])

    history_df = pd.DataFrame(
        {"user_id": ds.user_ids[ds.history["user_idx"]], "product_id": ds.item_ids[ds.history["item_idx"]],
         "rating": ds.history["rating"], "timestamp": ds.history["timestamp"]}
    )
    history_df = history_df[history_df["user_id"].isin(set(demo_df["user_id"]))]

    pop = recency_weighted_counts(ds, 180.0)
    order = np.argsort(-pop, kind="stable")
    popular_df = pd.DataFrame({"product_id": ds.item_ids[order], "rank": np.arange(1, len(order) + 1),
                               "score": pop[order]})

    similar_df = similar_items_table(model.gens["content"], ds, args.similar_k)

    catalogue = ds.products[["item_id", "title", "brand", "main_category", "categories", "features",
                             "description", "price", "image_url", "date_first_available"]].copy()
    catalogue["platform"] = platforms
    catalogue["review_count"] = np.bincount(ds.history["item_idx"], minlength=ds.n_items)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    catalogue.to_parquet(out / "products.parquet", index=False)
    recs_df.to_parquet(out / "recommendations.parquet", index=False)
    similar_df.to_parquet(out / "similar_items.parquet", index=False)
    popular_df.to_parquet(out / "popular.parquet", index=False)
    demo_df.to_parquet(out / "demo_users.parquet", index=False)
    history_df.to_parquet(out / "demo_history.parquet", index=False)

    revision = git_revision()
    version = {
        "version": "hybrid-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M"),
        "model": "hybrid",
        "params": model.params(),
        "git_revision": revision,
        "trained_on_interactions": int(len(interactions)),
        "fit_seconds": round(fit_seconds, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "diagnostics": {k: v for k, v in model.diagnostics().items() if k != "feature_gain"},
    }
    (out / "model_version.json").write_text(json.dumps(version, indent=2, default=str), encoding="utf-8")

    import mlflow

    setup_mlflow("sqlite:///mlruns.db", "mlruns", "cartsense-production")
    with mlflow.start_run(run_name=version["version"]):
        mlflow.set_tags({"model": "hybrid", "git_revision": revision, "kind": "production-export"})
        mlflow.log_params({k: str(v)[:500] for k, v in model.params().items()})
        mlflow.log_metric("fit_seconds", fit_seconds)
        mlflow.log_artifact(str(out / "model_version.json"))
    log.info("export written to %s (version %s)", out, version["version"])


if __name__ == "__main__":
    main()
