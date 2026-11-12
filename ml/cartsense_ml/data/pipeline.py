"""Phase 1 data pipeline: download -> convert -> clean -> stats -> split.

Usage (from the repository root):

    python -m cartsense_ml.data.pipeline --config ml/configs/data.yaml
    python -m cartsense_ml.data.pipeline --steps clean stats split

Each step reads only the outputs of earlier steps, so any suffix of the
pipeline can be re-run on its own.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

import numpy as np
import pandas as pd

from cartsense_ml.config import REPO_ROOT, DataConfig, load_data_config
from cartsense_ml.data.clean import run_clean
from cartsense_ml.data.convert import metadata_to_parquet, ratings_to_parquet, unique_item_ids
from cartsense_ml.data.download import download_file
from cartsense_ml.data.split import run_split
from cartsense_ml.data.stats import compute_stats, write_report

log = logging.getLogger("cartsense_ml.pipeline")

STEPS = ("download", "convert", "clean", "stats", "split")
DEFAULT_CONFIG = REPO_ROOT / "ml" / "configs" / "data.yaml"


class PipelinePaths:
    def __init__(self, cfg: DataConfig):
        p = cfg.paths
        self.raw_ratings = p.raw_dir / Path(cfg.ratings_url()).name
        self.raw_meta = p.raw_dir / Path(cfg.metadata_url()).name
        self.interim_ratings = p.interim_dir / "ratings.parquet"
        self.interim_products = p.interim_dir / "products.parquet"
        self.interactions = p.processed_dir / "interactions.parquet"
        self.products = p.processed_dir / "products.parquet"
        self.splits_dir = p.processed_dir / "splits"
        self.reports_dir = p.reports_dir


def run(cfg: DataConfig, steps: list[str], force_download: bool = False) -> None:
    random.seed(cfg.seed)
    np.random.seed(cfg.seed)
    paths = PipelinePaths(cfg)

    if "download" in steps:
        download_file(cfg.ratings_url(), paths.raw_ratings, force=force_download)
        download_file(cfg.metadata_url(), paths.raw_meta, force=force_download)

    if "convert" in steps:
        n = ratings_to_parquet(paths.raw_ratings, paths.interim_ratings)
        item_ids = unique_item_ids(paths.interim_ratings)
        log.info("ratings: %d rows, %d distinct products", n, len(item_ids))
        metadata_to_parquet(
            paths.raw_meta, paths.interim_products, cfg.processing.chunk_size, keep_ids=item_ids
        )

    if "clean" in steps:
        report = run_clean(
            paths.interim_ratings,
            paths.interim_products,
            paths.interactions.parent,
            require_title=cfg.processing.require_title,
        )
        paths.reports_dir.mkdir(parents=True, exist_ok=True)
        (paths.reports_dir / "clean_report.json").write_text(
            json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    if "stats" in steps:
        clean_report = json.loads((paths.reports_dir / "clean_report.json").read_text(encoding="utf-8"))
        stats = compute_stats(pd.read_parquet(paths.interactions), pd.read_parquet(paths.products))
        json_path, md_path = write_report(stats, clean_report, cfg.category, paths.reports_dir)
        log.info("stats written to %s and %s", json_path, md_path)

    if "split" in steps:
        run_split(
            paths.interactions,
            paths.splits_dir,
            paths.reports_dir,
            cfg.split.train_quantile,
            cfg.split.val_quantile,
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--steps", nargs="+", choices=STEPS, default=list(STEPS))
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(load_data_config(args.config), args.steps, force_download=args.force_download)


if __name__ == "__main__":
    main()
