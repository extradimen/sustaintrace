from pathlib import Path

import run_p18_mineru_targets as runner
from run_p18_mineru_targets import main

runner.OUTPUT_ROOT = (
    Path(__file__).resolve().parents[1] / "artifacts/p18/mineru_targets_RESUME01"
)


if __name__ == "__main__":
    main()
