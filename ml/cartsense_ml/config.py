"""Typed access to the YAML configuration files under ml/configs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Sources:
    base_url: str
    ratings: str
    metadata: str


@dataclass(frozen=True)
class Paths:
    raw_dir: Path
    interim_dir: Path
    processed_dir: Path
    reports_dir: Path


@dataclass(frozen=True)
class Processing:
    chunk_size: int
    require_title: bool


@dataclass(frozen=True)
class SplitConfig:
    train_quantile: float
    val_quantile: float

    def __post_init__(self) -> None:
        if not 0.0 < self.train_quantile < self.val_quantile < 1.0:
            raise ValueError(
                "split quantiles must satisfy 0 < train_quantile < val_quantile < 1, "
                f"got {self.train_quantile} and {self.val_quantile}"
            )


@dataclass(frozen=True)
class DataConfig:
    category: str
    seed: int
    sources: Sources
    paths: Paths
    processing: Processing
    split: SplitConfig

    def ratings_url(self) -> str:
        return f"{self.sources.base_url}/{self.sources.ratings.format(category=self.category)}"

    def metadata_url(self) -> str:
        return f"{self.sources.base_url}/{self.sources.metadata.format(category=self.category)}"


def _resolve(path: str, root: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else root / p


def load_data_config(path: str | Path, root: Path | None = None) -> DataConfig:
    """Load the data pipeline config. Relative paths resolve against ``root``
    (the repository root by default)."""
    root = root or REPO_ROOT
    with open(path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    paths = raw["paths"]
    return DataConfig(
        category=raw["category"],
        seed=int(raw.get("seed", 42)),
        sources=Sources(**raw["sources"]),
        paths=Paths(**{k: _resolve(v, root) for k, v in paths.items()}),
        processing=Processing(
            chunk_size=int(raw["processing"]["chunk_size"]),
            require_title=bool(raw["processing"]["require_title"]),
        ),
        split=SplitConfig(
            train_quantile=float(raw["split"]["train_quantile"]),
            val_quantile=float(raw["split"]["val_quantile"]),
        ),
    )
