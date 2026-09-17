from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import (
    audit_native_page_corroboration,
    sha256_file,
    validate_records,
)

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def extract_page(path: Path, page: int) -> str | None:
    result = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 and result.stdout.strip() else None


def main() -> None:
    kb_dir = ROOT / "data/knowledge_bases/v0.1"
    fact_path = kb_dir / "fact_records.jsonl"
    binding_path = kb_dir / "field_evidence_bindings.jsonl"
    qualification_path = kb_dir / "joint_fact_qualifications.jsonl"
    facts = {item["record_id"]: item for item in load_jsonl(fact_path)}
    bindings = {item["fact_record_id"]: item for item in load_jsonl(binding_path)}
    qualifications = [
        item
        for item in load_jsonl(qualification_path)
        if item["qualification_status"] == "jointly_qualified_candidate"
    ]
    page_cache: dict[tuple[str, int], str | None] = {}
    records = []
    pdf_inventory: dict[str, str] = {}
    for qualification in qualifications:
        fact = facts[qualification["fact_record_id"]]
        metadata = fact["subject"].get("document_metadata", [])
        local_path = next(
            (item.get("local_path") for item in metadata if item.get("local_path")), None
        )
        binding = bindings[fact["record_id"]]
        evidence_indices = binding.get("matched_evidence_indices", [])
        page = fact["evidence"][evidence_indices[0]]["pdf_page"] if evidence_indices else None
        native_text = None
        if local_path and isinstance(page, int):
            pdf = ROOT / local_path
            if pdf.is_file():
                pdf_inventory[local_path] = sha256_file(pdf)
                cache_key = (local_path, page)
                if cache_key not in page_cache:
                    page_cache[cache_key] = extract_page(pdf, page)
                native_text = page_cache[cache_key]
        records.append(
            audit_native_page_corroboration(fact, qualification, native_text, local_path, page)
        )

    schema = json.loads(
        (ROOT / "schemas/knowledge/native-pdf-corroboration-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output_path = kb_dir / "native_pdf_corroborations.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        )
    )
    counts = Counter(item["status"] for item in records)
    summary = {
        "schema_version": "0.1",
        "status": "native_pdf_corroboration_complete_no_promotion",
        "candidate_records": len(records),
        "counts": dict(sorted(counts.items())),
        "pdf_pages_extracted": len(page_cache),
        "pdf_inventory": [
            {"path": path, "sha256": digest} for path, digest in sorted(pdf_inventory.items())
        ],
        "inputs": {
            "facts_sha256": sha256_file(fact_path),
            "field_bindings_sha256": sha256_file(binding_path),
            "joint_qualifications_sha256": sha256_file(qualification_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "promotion_count": 0,
        "next_gate": "adjudicate boundary and unit attachment before any Tier B promotion",
    }
    summary_path = kb_dir / "native_pdf_corroboration_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
