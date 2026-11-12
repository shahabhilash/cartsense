"""End-to-end run of the offline steps on the tiny fixture files."""

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pandas as pd

from cartsense_ml.config import REPO_ROOT, SplitConfig, load_data_config
from cartsense_ml.data.pipeline import PipelinePaths, run


def test_pipeline_end_to_end_without_network(raw_files, tmp_path: Path):
    cfg = load_data_config(REPO_ROOT / "ml" / "configs" / "data.yaml", root=tmp_path)
    # Four interactions survive cleaning, so use wide quantiles to keep every window non-empty
    cfg = replace(cfg, split=SplitConfig(train_quantile=0.5, val_quantile=0.75))
    paths = PipelinePaths(cfg)
    paths.raw_ratings.parent.mkdir(parents=True)
    shutil.copy(raw_files["ratings"], paths.raw_ratings)
    shutil.copy(raw_files["meta"], paths.raw_meta)

    run(cfg, ["convert", "clean", "stats", "split"])

    interactions = pd.read_parquet(paths.interactions)
    products = pd.read_parquet(paths.products)
    # item C has ratings but no metadata, so its interaction is dropped
    assert set(interactions["item_id"]) == {"A", "B"}
    assert set(products["item_id"]) == {"A", "B"}

    split_rows = sum(len(pd.read_parquet(paths.splits_dir / f"{s}.parquet")) for s in ("train", "val", "test"))
    assert split_rows == len(interactions)

    stats = json.loads((paths.reports_dir / "data_stats.json").read_text())
    assert stats["clean"]["dropped_unknown_or_untitled_item"] == 1
    assert stats["stats"]["interactions"] == 4
    assert (paths.reports_dir / "data_stats.md").exists()
    assert (paths.reports_dir / "split_summary.json").exists()
