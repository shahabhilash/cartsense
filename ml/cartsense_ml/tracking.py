"""MLflow setup and helpers.

Tracking uses a local SQLite database (needed for the model registry in later
phases) with artifacts stored under ``mlruns/``. Both are git-ignored.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from cartsense_ml.config import REPO_ROOT


def resolve_tracking_uri(uri: str, root: Path = REPO_ROOT) -> str:
    """Make a relative ``sqlite:///file.db`` URI absolute against ``root``."""
    prefix = "sqlite:///"
    if uri.startswith(prefix):
        path = Path(uri[len(prefix) :])
        if not path.is_absolute():
            path = root / path
        return prefix + path.resolve().as_posix()
    return uri


def setup_mlflow(tracking_uri: str, artifact_dir: str | Path, experiment: str, root: Path = REPO_ROOT) -> str:
    """Point MLflow at the tracking store and return the experiment id."""
    import mlflow

    mlflow.set_tracking_uri(resolve_tracking_uri(tracking_uri, root))
    artifact_path = Path(artifact_dir)
    if not artifact_path.is_absolute():
        artifact_path = root / artifact_path
    existing = mlflow.get_experiment_by_name(experiment)
    if existing is not None:
        exp_id = existing.experiment_id
    else:
        artifact_path.mkdir(parents=True, exist_ok=True)
        exp_id = mlflow.create_experiment(experiment, artifact_location=artifact_path.resolve().as_uri())
    mlflow.set_experiment(experiment_id=exp_id)
    return exp_id


def metric_key(name: str) -> str:
    """MLflow metric names cannot contain '@'."""
    return name.replace("@", "_at_")


def flatten_metrics(result: dict[str, Any]) -> dict[str, float]:
    """Flatten an evaluation result into MLflow metrics:
    overall metrics keep their name, slices get a prefix (``warm_users.ndcg_at_10``)."""
    out: dict[str, float] = {}
    for section, prefix in (("overall", ""), ("warm_users", "warm_users."), ("cold_users", "cold_users."),
                            ("oracle_recall", "oracle.")):
        for name, value in result.get(section, {}).items():
            out[prefix + metric_key(name)] = float(value)
    for name in ("fit_seconds", "recommend_seconds"):
        if name in result:
            out[name] = float(result[name])
    return out


def git_revision(root: Path = REPO_ROOT) -> str:
    """Current commit hash, suffixed with '-dirty' if the tree has local changes."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return rev + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
