from pathlib import Path

import run_p14_v23_lockbox as base

ROOT = Path(__file__).resolve().parents[1]
base.PROGRESS = ROOT / "data/manifests/p14_candidate_progress_RESUME01.json"
base.RUN_LABEL = "v23-RESUME01"
base.COMMON["layout_registry_path"] = (
    ROOT / "configs/framework/p14_layout_fallback_registry_RESUME01_v0.1.lock.json"
)


if __name__ == "__main__":
    base.main()
