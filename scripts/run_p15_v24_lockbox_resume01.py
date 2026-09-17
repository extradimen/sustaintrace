from pathlib import Path

import run_p15_v24_lockbox as base

ROOT = Path(__file__).resolve().parents[1]
base.PROGRESS = ROOT / "data/manifests/p15_candidate_progress_RESUME01.json"
base.RUN_LABEL = "v24-RESUME01"


if __name__ == "__main__":
    base.main()
