from __future__ import annotations

from pathlib import Path

from esg_reliable_discovery.mineru_adapter import (
    MinerUError,
    parse_with_mineru,
)

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data/raw/p20_staging/holcim-sustainability-statement-2025.pdf"
OUTPUT_ROOT = ROOT / "artifacts/p20/mineru_targets_RESUME01"
CONFIG = ROOT / "configs/parsers/p20-mineru-3.4.0-runtime.json"
PAGES = [85, 86, 87, 111, 112, 113, 114, 120, 121, 134, 135, 136]


def main() -> None:
    for page in PAGES:
        destination = OUTPUT_ROOT / f"P20-HOLCIM-SS2025-p{page:04d}"
        record = destination / "esg_rd_mineru_run.json"
        if record.is_file():
            print(f"SKIP checkpoint page {page}", flush=True)
            continue
        if destination.exists() and any(destination.iterdir()):
            raise RuntimeError(f"uncheckpointed_output_requires_audit:{destination}")
        print(f"START page {page}", flush=True)
        try:
            parse_with_mineru(
                PDF,
                destination,
                executable=str(ROOT / ".mineru-venv/bin/mineru"),
                backend="pipeline",
                method="auto",
                start_page=page - 1,
                end_page=page - 1,
                tools_config=CONFIG,
            )
        except MinerUError as error:
            print(f"FAIL page {page}: {error}", flush=True)
            continue
        print(f"DONE page {page}", flush=True)


if __name__ == "__main__":
    main()
