from __future__ import annotations

from pathlib import Path

import finalize_scale_batch_005_mineru_v01 as finalizer

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    finalizer.TARGETS = ROOT / "data/manifests/scale_batch_008_target_pages.lock.json"
    finalizer.ATTEMPTS = (
        ROOT / "data/results/scale_batch_008_mineru_summary.lock.json",
        ROOT / "data/results/scale_batch_008_mineru_RESUME01_summary.lock.json",
        ROOT / "data/results/scale_batch_008_mineru_RESUME02_summary.lock.json",
    )
    finalizer.ATTEMPT_LABELS = ("INITIAL", "RESUME01", "RESUME02")
    finalizer.OUTPUT = ROOT / "data/results/scale_batch_008_mineru_FINAL_summary.lock.json"
    finalizer.BATCH_ID = "KB-SCALE-BATCH-008-MINERU-FINAL"
    finalizer.main()


if __name__ == "__main__":
    main()
