from pathlib import Path

import run_p15_mineru_targets_resume01 as runner
from run_p15_mineru_targets_resume01 import main

runner.OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "artifacts/p15/mineru_targets_RESUME02"


if __name__ == "__main__":
    main()
