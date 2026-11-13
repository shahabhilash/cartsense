"""Retrain the recommender on the dataset plus real store behaviour, in one command.

    # PowerShell
    $env:CARTSENSE_DATABASE_URL = "<database URL>"
    python scripts/retrain.py

    # bash
    CARTSENSE_DATABASE_URL="<database URL>" python scripts/retrain.py

Steps
    1. feedback: read real store events from the database
       -> data/processed/site_interactions.parquet
    2. export:   retrain the hybrid on dataset + store interactions and
                 precompute recommendations -> artifacts/export
    3. load:     load the new model version into the database (it becomes the
                 active version; earlier versions stay for CTR comparison)

The database URL is read from the environment and passed to each step through
the environment only, so it never appears in a command line or log.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(step: str, args: list[str], cwd: Path) -> None:
    print(f"\n=== {step} ===", flush=True)
    start = time.perf_counter()
    subprocess.run([sys.executable, *args], cwd=cwd, check=True, env=os.environ.copy())
    print(f"=== {step} done in {time.perf_counter() - start:.0f}s ===", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo-users", type=int, default=2000)
    parser.add_argument("--skip-load", action="store_true", help="retrain and export only; do not touch the database")
    args = parser.parse_args()
    if not os.environ.get("CARTSENSE_DATABASE_URL"):
        parser.error("set CARTSENSE_DATABASE_URL to the store database first")

    site = ROOT / "data" / "processed" / "site_interactions.parquet"
    export_dir = ROOT / "artifacts" / "export"

    run("1/3 collect store feedback", ["-m", "cartsense_ml.feedback", "--out", str(site)], ROOT)
    run("2/3 retrain and export",
        ["-m", "cartsense_ml.export", "--out", str(export_dir), "--demo-users", str(args.demo_users),
         "--site-interactions", str(site)], ROOT)
    if args.skip_load:
        print("\nSkipped loading. Run app.load_data when ready.")
        return
    run("3/3 load new model version",
        ["-m", "app.load_data", "--export-dir", str(export_dir), "--results-dir", str(ROOT / "reports" / "results" / "test")],
        ROOT / "services" / "api")
    print("\nRetrain complete: the new model version is active.")


if __name__ == "__main__":
    main()
