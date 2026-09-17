#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _venv_python() -> Path:
    if os.name == "nt":
        return ROOT / ".venv/Scripts/python.exe"
    return ROOT / ".venv/bin/python"


def main() -> None:
    python = _venv_python()
    if python.exists() and Path(sys.executable).resolve() != python.resolve():
        os.execv(str(python), [str(python), "-m", "esg_reliable_discovery.launcher", *sys.argv[1:]])
    sys.path.insert(0, str(ROOT / "src"))
    from esg_reliable_discovery.launcher import main as launch

    launch()


if __name__ == "__main__":
    main()
