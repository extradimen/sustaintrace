from __future__ import annotations

from pathlib import Path

import run_scale_batch_mineru_v01 as runner

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    runner.REGISTRY = (
        ROOT / "data/manifests/scale_batch_002_gap_repair_pages.lock.json"
    )
    runner.OUTPUT_ROOT = (
        ROOT / "artifacts/scale_batch_002/mineru_gap_repair01_RESUME01"
    )
    runner.SUMMARY = (
        ROOT
        / "data/results/scale_batch_002_gap_repair_mineru_RESUME01_summary.lock.json"
    )
    runner.CONFIG = (
        ROOT / "configs/parsers/scale-batch-002-mineru-3.4.0-runtime.json"
    )
    runner.RESUME_FROM = (
        ROOT / "data/results/scale_batch_002_gap_repair_mineru_summary.lock.json"
    )
    runner.BATCH_ID = "KB-SCALE-BATCH-002-GAP-REPAIR01-MINERU-RESUME01"
    runner.main()


if __name__ == "__main__":
    main()
