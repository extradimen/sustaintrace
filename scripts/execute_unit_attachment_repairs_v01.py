from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import (
    sha256_file,
    stable_id,
    unit_marker_present,
    validate_records,
)

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def native_page(path: Path, page: int) -> str | None:
    result = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 and result.stdout.strip() else None


def main() -> None:
    fact_path = KB / "fact_records.jsonl"
    binding_path = KB / "field_evidence_bindings.jsonl"
    gap_path = KB / "knowledge_gap_records.jsonl"
    facts = {item["record_id"]: item for item in load(fact_path)}
    bindings = {item["fact_record_id"]: item for item in load(binding_path)}
    parents = {
        path.relative_to(ROOT).as_posix(): sha256_file(path)
        for path in (fact_path, binding_path, gap_path)
    }
    cache: dict[tuple[str, int], str | None] = {}
    records = []
    for gap in load(gap_path):
        if gap["gap_signature"] != "UNIT_ATTACHMENT_INCOMPLETE":
            continue
        fact = facts[gap["fact_record_id"]]
        unit = fact.get("qualifiers", {}).get("normalized_unit")
        if not isinstance(unit, str) or unit.casefold() == "mixed":
            continue
        binding = bindings[fact["record_id"]]
        indices = binding.get("matched_evidence_indices", [])
        if binding.get("binding_status") != "unique_literal" or len(indices) != 1:
            continue
        evidence = fact["evidence"][indices[0]]
        if not unit_marker_present(unit, evidence["quote"]):
            continue
        local_path = next(
            (
                item.get("local_path")
                for item in fact["subject"].get("document_metadata", [])
                if item.get("local_path")
            ),
            None,
        )
        if not local_path:
            continue
        pdf = ROOT / local_path
        page = evidence["pdf_page"]
        key = (local_path, page)
        if key not in cache:
            cache[key] = native_page(pdf, page) if pdf.is_file() else None
        if cache[key] is None or not unit_marker_present(unit, cache[key]):
            continue
        identity = {"fact_record_id": fact["record_id"], "unit": unit}
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "unit_attachment_repair",
                "attachment_id": stable_id("unit", identity),
                "fact_record_id": fact["record_id"],
                "task_id": gap["task_id"],
                "attached_unit": unit,
                "pdf_page": page,
                "validation": {
                    "unique_field_quote": True,
                    "marker_in_bound_quote": True,
                    "marker_in_native_pdf_page": True,
                    "parent_hashes_valid": True,
                },
                "parent_artifacts": [
                    {"path": path, "sha256": digest} for path, digest in sorted(parents.items())
                ],
                "execution_mode": "derived_layer_only",
                "rollback": {
                    "action": "delete_derived_attachment_record",
                    "source_restoration_required": False,
                },
                "fact_source_modified": False,
                "promotion_performed": False,
            }
        )
    schema = json.loads(
        (ROOT / "schemas/knowledge/unit-attachment-repair-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output = KB / "unit_attachment_repairs.jsonl"
    output.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )
    summary = {
        "schema_version": "0.1",
        "status": "derived_unit_repairs_executed_no_fact_promotion",
        "attachments_created": len(records),
        "native_pages_checked": len(cache),
        "fact_sources_modified": 0,
        "promotions_performed": 0,
        "rollback_ledgers": len(records),
        "parent_artifacts": [
            {"path": path, "sha256": digest} for path, digest in sorted(parents.items())
        ],
        "output": {
            "path": output.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output),
        },
        "next_gate": "re-audit remaining gaps after validated period and unit attachments",
    }
    summary_path = KB / "unit_attachment_repair_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"attachments": len(records), "native_pages_checked": len(cache)}))


if __name__ == "__main__":
    main()
