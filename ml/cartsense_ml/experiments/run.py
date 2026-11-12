"""Fit and evaluate the models listed in an experiment config.

    python -m cartsense_ml.experiments.run --config ml/configs/baselines.yaml --stage val
    python -m cartsense_ml.experiments.run --config ml/configs/baselines.yaml --stage test

For each model this writes ``reports/results/<stage>/<model>.json`` and logs
the same numbers to MLflow, then regenerates ``reports/results_<stage>.md``
from every result file of that stage, so models trained in different phases
end up in one comparison table.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from cartsense_ml.config import REPO_ROOT, load_data_config
from cartsense_ml.data.dataset import STAGES, load_stage
from cartsense_ml.eval.harness import build_target, evaluate
from cartsense_ml.experiments.report import write_results_table
from cartsense_ml.models.registry import build_model
from cartsense_ml.tracking import flatten_metrics, git_revision, setup_mlflow

log = logging.getLogger("cartsense_ml.experiments")


@dataclass
class ModelSpec:
    name: str
    params: dict[str, Any]
    label: str  # file / run name; defaults to the model name


@dataclass
class ExperimentConfig:
    data_config: Path
    seed: int
    k_values: list[int]
    batch_size: int
    mlflow: dict[str, str] | None
    models: list[ModelSpec]
    # Results of a named group (e.g. hyperparameter tuning) are kept apart from
    # the main comparison table: reports/results/<group>/<stage>/
    report_group: str | None = None


def load_experiment_config(path: Path, root: Path = REPO_ROOT) -> ExperimentConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    data_config = Path(raw["data_config"])
    models = [
        ModelSpec(name=m["name"], params=m.get("params") or {}, label=m.get("label", m["name"]))
        for m in raw["models"]
    ]
    labels = [m.label for m in models]
    if len(set(labels)) != len(labels):
        raise ValueError(f"model labels must be unique, got {labels}")
    return ExperimentConfig(
        data_config=data_config if data_config.is_absolute() else root / data_config,
        seed=int(raw.get("seed", 42)),
        k_values=sorted(int(k) for k in raw["k_values"]),
        batch_size=int(raw.get("batch_size", 2048)),
        mlflow=raw.get("mlflow"),
        models=models,
        report_group=raw.get("report_group"),
    )


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def run_experiment(
    cfg: ExperimentConfig,
    stage: str,
    root: Path = REPO_ROOT,
    use_mlflow: bool = True,
    only: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    if stage not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}")
    data_cfg = load_data_config(cfg.data_config, root=root)
    ds, target_df = load_stage(data_cfg, stage)
    target = build_target(ds, target_df)
    log.info(
        "stage=%s users=%d (warm %d, cold %d) recommendable items=%d",
        stage, len(target), int(target.warm.sum()), int((~target.warm).sum()), int(ds.available.sum()),
    )

    reports = data_cfg.paths.reports_dir
    if cfg.report_group:
        results_dir = reports / "results" / cfg.report_group / stage
        table_path = reports / f"{cfg.report_group}_{stage}.md"
    else:
        results_dir = reports / "results" / stage
        table_path = reports / f"results_{stage}.md"
    results_dir.mkdir(parents=True, exist_ok=True)
    revision = git_revision(root)

    mlflow = None
    if use_mlflow and cfg.mlflow:
        import mlflow  # noqa: F811  (imported lazily: heavy and optional for tests)

        setup_mlflow(cfg.mlflow["tracking_uri"], cfg.mlflow["artifact_dir"], cfg.mlflow["experiment"], root)

    results: dict[str, dict[str, Any]] = {}
    for spec in cfg.models:
        if only and spec.label not in only:
            continue
        seed_everything(cfg.seed)
        model = build_model(spec.name, spec.params, seed=cfg.seed)

        start = time.perf_counter()
        model.fit(ds)
        fit_seconds = time.perf_counter() - start

        result = evaluate(model, ds, target, cfg.k_values, batch_size=cfg.batch_size)
        result = {
            "model": spec.name,
            "label": spec.label,
            "stage": stage,
            "params": model.params(),
            "git_revision": revision,
            "cutoff_ms": ds.cutoff_ms,
            "fit_seconds": round(fit_seconds, 3),
            **result,
            "diagnostics": model.diagnostics(),
        }
        (results_dir / f"{spec.label}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        results[spec.label] = result
        k0 = cfg.k_values[0]
        log.info(
            "%-18s ndcg@%d=%.4f recall@%d=%.4f fit=%.1fs",
            spec.label, k0, result["overall"][f"ndcg@{k0}"], k0, result["overall"][f"recall@{k0}"], fit_seconds,
        )

        if mlflow is not None:
            with mlflow.start_run(run_name=f"{spec.label}-{stage}"):
                mlflow.set_tags({"model": spec.name, "label": spec.label, "stage": stage,
                                 "git_revision": revision, "report_group": cfg.report_group or "main"})
                mlflow.log_params({**model.params(), "k_values": cfg.k_values, "cutoff_ms": ds.cutoff_ms})
                mlflow.log_metrics(flatten_metrics(result))
                mlflow.log_artifact(str(results_dir / f"{spec.label}.json"))

    write_results_table(results_dir, table_path, cfg.k_values)
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--stage", choices=STAGES, default="val")
    parser.add_argument("--only", nargs="+", help="run only these model labels")
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_experiment_config(args.config)
    run_experiment(cfg, args.stage, use_mlflow=not args.no_mlflow, only=args.only)


if __name__ == "__main__":
    main()
