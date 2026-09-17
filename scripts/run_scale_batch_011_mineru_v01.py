from __future__ import annotations

from pathlib import Path

import run_scale_batch_mineru_v01 as runner

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    runner.REGISTRY = ROOT / "data/manifests/scale_batch_011_target_pages.lock.json"
    runner.OUTPUT_ROOT = ROOT / "artifacts/scale_batch_011/mineru_targets"
    runner.SUMMARY = ROOT / "data/results/scale_batch_011_mineru_summary.lock.json"
    runner.CONFIG = ROOT / "configs/parsers/scale-batch-011-mineru-3.4.0-runtime.json"
    runner.RESUME_FROM = None
    runner.BATCH_ID = "KB-SCALE-BATCH-011"
    runner.main()


if __name__ == "__main__":
    main()
