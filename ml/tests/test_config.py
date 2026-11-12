from pathlib import Path

import pytest

from cartsense_ml.config import REPO_ROOT, SplitConfig, load_data_config

CONFIG = REPO_ROOT / "ml" / "configs" / "data.yaml"


def test_load_default_config_resolves_paths():
    cfg = load_data_config(CONFIG)
    assert cfg.category == "Video_Games"
    assert cfg.paths.raw_dir == REPO_ROOT / "data" / "raw"
    assert cfg.ratings_url().endswith("/benchmark/5core/rating_only/Video_Games.csv.gz")
    assert cfg.metadata_url().endswith("/raw/meta_categories/meta_Video_Games.jsonl.gz")


def test_custom_root(tmp_path: Path):
    cfg = load_data_config(CONFIG, root=tmp_path)
    assert cfg.paths.processed_dir == tmp_path / "data" / "processed"


@pytest.mark.parametrize("train_q,val_q", [(0.9, 0.8), (0.0, 0.5), (0.5, 1.0), (0.7, 0.7)])
def test_invalid_split_quantiles_rejected(train_q, val_q):
    with pytest.raises(ValueError):
        SplitConfig(train_quantile=train_q, val_quantile=val_q)
