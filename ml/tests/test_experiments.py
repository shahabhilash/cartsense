"""Experiment runner on a small synthetic split (no network, temporary MLflow store)."""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from cartsense_ml.experiments.report import render_table
from cartsense_ml.experiments.run import load_experiment_config, run_experiment
from cartsense_ml.models.registry import build_model
from cartsense_ml.tracking import flatten_metrics, metric_key, resolve_tracking_uri

DATA_YAML = Path(__file__).resolve().parents[1] / "configs" / "data.yaml"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Write processed splits + split summary the way the Phase 1 pipeline does."""
    rng = np.random.default_rng(0)
    n_items, n_users = 40, 60
    items = [f"I{i:02d}" for i in range(n_items)]
    products = pd.DataFrame(
        {
            "item_id": items,
            "title": items,
            "categories": [["Video Games", "PC" if i % 2 else "Nintendo Switch"] for i in range(n_items)],
            "date_first_available": [date(2000, 1, 1)] * n_items,
        }
    )
    rows = []
    for u in range(n_users):
        for i in rng.choice(n_items, size=6, replace=False):
            rows.append((f"U{u:02d}", items[i], 5.0, int(rng.integers(1_600_000_000_000, 1_700_000_000_000))))
    inter = pd.DataFrame(rows, columns=["user_id", "item_id", "rating", "timestamp"]).sort_values("timestamp")
    t1, t2 = inter["timestamp"].quantile([0.8, 0.9], interpolation="lower").astype(int)

    processed = tmp_path / "data" / "processed"
    (processed / "splits").mkdir(parents=True)
    products.to_parquet(processed / "products.parquet")
    inter[inter.timestamp <= t1].to_parquet(processed / "splits" / "train.parquet")
    inter[(inter.timestamp > t1) & (inter.timestamp <= t2)].to_parquet(processed / "splits" / "val.parquet")
    inter[inter.timestamp > t2].to_parquet(processed / "splits" / "test.parquet")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "split_summary.json").write_text(
        json.dumps({"cutoffs": {"train_end_ms": int(t1), "val_end_ms": int(t2)}})
    )

    cfg = {
        "data_config": str(DATA_YAML),
        "seed": 1,
        "k_values": [5, 10],
        "mlflow": {"tracking_uri": "sqlite:///mlruns.db", "artifact_dir": "mlruns", "experiment": "test"},
        "models": [
            {"name": "random"},
            {"name": "most_popular"},
            {"name": "category_popular", "params": {"half_life_days": 30}},
        ],
    }
    (tmp_path / "exp.yaml").write_text(yaml.safe_dump(cfg))
    return tmp_path


def test_run_writes_results_and_table(workspace: Path):
    cfg = load_experiment_config(workspace / "exp.yaml", root=workspace)
    results = run_experiment(cfg, "val", root=workspace, use_mlflow=False)

    assert set(results) == {"random", "most_popular", "category_popular"}
    for label in results:
        saved = json.loads((workspace / "reports" / "results" / "val" / f"{label}.json").read_text())
        assert saved["stage"] == "val" and "ndcg@10" in saved["overall"]
    table = (workspace / "reports" / "results_val.md").read_text()
    assert "| category_popular |" in table and "## All users, K = 5" in table


def test_run_is_reproducible(workspace: Path):
    cfg = load_experiment_config(workspace / "exp.yaml", root=workspace)
    a = run_experiment(cfg, "test", root=workspace, use_mlflow=False, only=["random"])
    b = run_experiment(cfg, "test", root=workspace, use_mlflow=False, only=["random"])
    assert a["random"]["overall"] == b["random"]["overall"]


def test_run_logs_to_mlflow(workspace: Path):
    import mlflow

    cfg = load_experiment_config(workspace / "exp.yaml", root=workspace)
    run_experiment(cfg, "val", root=workspace, use_mlflow=True, only=["most_popular"])
    runs = mlflow.search_runs(experiment_names=["test"])
    assert len(runs) == 1
    assert runs.loc[0, "tags.model"] == "most_popular"
    assert "metrics.ndcg_at_10" in runs.columns
    assert "metrics.warm_users.recall_at_5" in runs.columns


def test_duplicate_labels_rejected(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump({"data_config": "x.yaml", "k_values": [10],
                                    "models": [{"name": "random"}, {"name": "random"}]}))
    with pytest.raises(ValueError):
        load_experiment_config(path)


def test_registry_rejects_unknown_model():
    with pytest.raises(KeyError):
        build_model("does_not_exist")


def test_tracking_helpers(tmp_path: Path):
    assert metric_key("ndcg@10") == "ndcg_at_10"
    assert resolve_tracking_uri("sqlite:///mlruns.db", tmp_path) == "sqlite:///" + (tmp_path / "mlruns.db").as_posix()
    assert resolve_tracking_uri("http://server:5000") == "http://server:5000"
    flat = flatten_metrics({"overall": {"ndcg@10": 0.5}, "cold_users": {"recall@10": 0.1}, "fit_seconds": 2})
    assert flat == {"ndcg_at_10": 0.5, "cold_users.recall_at_10": 0.1, "fit_seconds": 2.0}


def test_render_table_handles_empty():
    assert "No results" in render_table([], [10])
