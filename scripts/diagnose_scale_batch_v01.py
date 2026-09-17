from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/knowledge/scale_batch_001_RESUME01_v0.2.json"
ACQUISITION = ROOT / "data/manifests/scale_batch_001_acquisition.lock.json"
OUTPUT_DIR = ROOT / "data/interim/scale_batch_001"
SUMMARY = ROOT / "data/results/scale_batch_001_diagnostics.lock.json"

THEME_PATTERNS = {
    "ghg_emissions": (r"greenhouse gas", r"ghg emissions?", r"scope [123]"),
    "energy": (r"energy consumption", r"renewable (?:energy|electricity)", r"mwh"),
    "water": (r"water (?:withdrawal|consumption|use)", r"water stress", r"megalitres?"),
    "workforce": (r"own workforce", r"employees?", r"headcount", r"gender diversity"),
    "health_safety": (r"lost.time injur", r"fatalit", r"occupational health", r"trir"),
    "assurance": (r"limited assurance", r"reasonable assurance", r"assurance report"),
    "targets": (r"science.based target", r"net.zero", r"2030 target", r"target year"),
    "biodiversity": (r"biodiversity", r"ecosystems?", r"deforestation"),
    "circularity": (r"circular economy", r"recycl", r"waste generated"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_info(path: Path) -> dict[str, str]:
    result = subprocess.run(
        ["pdfinfo", str(path)], check=True, capture_output=True, text=True
    )
    info: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            info[key.strip()] = value.strip()
    return info


def extract_pages(path: Path, output: Path) -> list[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    subprocess.run(["pdftotext", "-layout", str(path), str(temporary)], check=True)
    temporary.replace(output)
    text = output.read_text(encoding="utf-8", errors="replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def theme_counts(text: str) -> dict[str, int]:
    lowered = text.lower()
    return {
        theme: sum(len(re.findall(pattern, lowered)) for pattern in patterns)
        for theme, patterns in THEME_PATTERNS.items()
    }


def top_pages(records: list[dict[str, Any]], theme: str) -> list[dict[str, int]]:
    ranked = sorted(
        (
            {"page": record["page"], "hits": record["theme_hits"][theme]}
            for record in records
            if record["theme_hits"][theme] > 0
        ),
        key=lambda item: (-item["hits"], item["page"]),
    )
    return ranked[:5]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--acquisition", type=Path, default=ACQUISITION)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    args = parser.parse_args()
    config_path = args.config.resolve()
    acquisition_path = args.acquisition.resolve()
    output_dir = args.output_dir.resolve()
    summary_path = args.summary.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    acquired = {item["document_id"]: item for item in acquisition["documents"]}
    document_summaries = []
    for document in config["documents"]:
        document_id = document["document_id"]
        path = ROOT / document["local_path"]
        actual_hash = sha256_file(path)
        if actual_hash != acquired[document_id]["sha256"]:
            raise ValueError(f"SHA256 mismatch before parse: {document_id}")
        info = pdf_info(path)
        expected_pages = int(info["Pages"])
        text_path = output_dir / f"{document_id}.layout.txt"
        pages = extract_pages(path, text_path)
        records = []
        aggregate = Counter()
        for page_number, text in enumerate(pages, start=1):
            hits = theme_counts(text)
            aggregate.update(hits)
            records.append(
                {
                    "document_id": document_id,
                    "page": page_number,
                    "text_characters": len(text.strip()),
                    "extractable": len(text.strip()) >= 40,
                    "theme_hits": hits,
                }
            )
        index_path = output_dir / f"{document_id}.page_index.jsonl"
        index_path.write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )
        extractable_pages = sum(record["extractable"] for record in records)
        document_summaries.append(
            {
                "document_id": document_id,
                "source_group_id": document["source_group_id"],
                "company": document["company"],
                "local_path": document["local_path"],
                "sha256": actual_hash,
                "pdfinfo_pages": expected_pages,
                "extracted_pages": len(pages),
                "page_count_consistent": len(pages) == expected_pages,
                "encrypted": info.get("Encrypted", "unknown"),
                "extractable_pages": extractable_pages,
                "extractable_ratio": round(extractable_pages / expected_pages, 6),
                "total_text_characters": sum(record["text_characters"] for record in records),
                "theme_hit_totals": dict(sorted(aggregate.items())),
                "candidate_pages_by_theme": {
                    theme: top_pages(records, theme) for theme in THEME_PATTERNS
                },
                "layout_text_path": str(text_path.relative_to(ROOT)),
                "page_index_path": str(index_path.relative_to(ROOT)),
            }
        )
        print(f"{document_id}: {extractable_pages}/{expected_pages} extractable pages")
    payload = {
        "schema_version": "0.1",
        "batch_id": config["batch_id"],
        "created_at": datetime.now(UTC).isoformat(),
        "status": "local_diagnostics_complete",
        "cloud_transmission": False,
        "documents": document_summaries,
        "totals": {
            "documents": len(document_summaries),
            "pdf_pages": sum(item["pdfinfo_pages"] for item in document_summaries),
            "extractable_pages": sum(item["extractable_pages"] for item in document_summaries),
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    main()
