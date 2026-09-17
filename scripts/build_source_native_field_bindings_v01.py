from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records
from esg_reliable_discovery.source_native_binding import bind_source_native_field

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


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
    fact_path = KB / "fact_records.jsonl"
    qualification_path = KB / "joint_fact_qualifications.jsonl"
    native_path = KB / "native_pdf_corroborations.jsonl"
    facts = {item["record_id"]: item for item in load_jsonl(fact_path)}
    qualifications = {
        item["fact_record_id"]: item
        for item in load_jsonl(qualification_path)
        if item["qualification_status"] == "jointly_qualified_candidate"
    }
    native = {item["fact_record_id"]: item for item in load_jsonl(native_path)}
    cache: dict[tuple[str, int], str | None] = {}
    records = []
    for fact_id, qualification in qualifications.items():
        fact = facts[fact_id]
        native_record = native.get(fact_id, {})
        pdf_path = native_record.get("pdf_path")
        pdf_page = native_record.get("pdf_page")
        native_text = None
        if pdf_path and isinstance(pdf_page, int):
            path = ROOT / pdf_path
            key = (pdf_path, pdf_page)
            if path.is_file() and key not in cache:
                cache[key] = extract_page(path, pdf_page)
            native_text = cache.get(key)
        records.append(
            bind_source_native_field(
                fact,
                qualification,
                native_text,
                pdf_path=pdf_path,
                pdf_page=pdf_page,
            )
        )

    schema = json.loads(
        (ROOT / "schemas/knowledge/source-native-field-binding-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output_path = KB / "source_native_field_bindings.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    counts = Counter(item["status"] for item in records)
    summary = {
        "schema_version": "0.1",
        "status": "source_native_field_binding_diagnostic_complete_no_promotion",
        "records": len(records),
        "counts": dict(sorted(counts.items())),
        "native_pages_extracted": len(cache),
        "promotion_count": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "facts_sha256": sha256_file(fact_path),
            "qualifications_sha256": sha256_file(qualification_path),
            "native_corroborations_sha256": sha256_file(native_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": "review unique native bindings; boundary semantics remain blocked",
    }
    summary_path = KB / "source_native_field_binding_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
