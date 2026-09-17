from pathlib import Path

import run_p17_mineru_targets as runner
from run_p17_mineru_targets import main

runner.OUTPUT_ROOT = (
    Path(__file__).resolve().parents[1] / "artifacts/p17/mineru_targets_RESUME02"
)
runner.PAGES = [127]


if __name__ == "__main__":
    main()
