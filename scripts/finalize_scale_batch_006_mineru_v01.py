from __future__ import annotations

from pathlib import Path

import finalize_scale_batch_005_mineru_v01 as finalizer

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    finalizer.TARGETS = ROOT / "data/manifests/scale_batch_006_target_pages.lock.json"
    finalizer.ATTEMPTS = tuple(
        ROOT / f"data/results/scale_batch_006_mineru_RESUME0{index}_summary.lock.json"
        for index in (1, 2, 3)
    )
    finalizer.ATTEMPT_LABELS = ("RESUME01", "RESUME02", "RESUME03")
    finalizer.OUTPUT = ROOT / "data/results/scale_batch_006_mineru_FINAL_summary.lock.json"
    finalizer.BATCH_ID = "KB-SCALE-BATCH-006-MINERU-FINAL"
    finalizer.main()


if __name__ == "__main__":
    main()
