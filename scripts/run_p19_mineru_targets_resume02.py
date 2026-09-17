from __future__ import annotations

from pathlib import Path

from esg_reliable_discovery.mineru_adapter import parse_with_mineru

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data/raw/p19_staging/novo-nordisk-annual-report-2025.pdf"
OUTPUT_ROOT = ROOT / "artifacts/p19/mineru_targets_RESUME02"
CONFIG = ROOT / "configs/parsers/p19-mineru-3.4.0-runtime.json"


def main() -> None:
    page = 65
    destination = OUTPUT_ROOT / f"P19-NOVO-NORDISK-AR2025-p{page:04d}"
    record = destination / "esg_rd_mineru_run.json"
    if record.is_file():
        print(f"SKIP checkpoint page {page}", flush=True)
        return
    if destination.exists() and any(destination.iterdir()):
        raise RuntimeError(f"uncheckpointed_output_requires_audit:{destination}")
    print(f"START page {page}", flush=True)
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
    print(f"DONE page {page}", flush=True)


if __name__ == "__main__":
    main()
