from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import (
    bind_fact_field_to_evidence,
    sha256_file,
    validate_records,
)

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    kb_dir = ROOT / "data/knowledge_bases/v0.1"
    fact_path = kb_dir / "fact_records.jsonl"
    audit_path = kb_dir / "fact_promotion_audits.jsonl"
    facts = load_jsonl(fact_path)
    audits = {item["fact_record_id"]: item for item in load_jsonl(audit_path)}
    bindings = [bind_fact_field_to_evidence(fact, audits[fact["record_id"]]) for fact in facts]
    schema = json.loads(
        (ROOT / "schemas/knowledge/field-evidence-binding-v0.1.schema.json").read_text()
    )
    validate_records(bindings, schema)

    binding_path = kb_dir / "field_evidence_bindings.jsonl"
    binding_path.write_text(
        "".join(
            json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for binding in bindings
        ),
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    for binding in bindings:
        status = binding["binding_status"]
        counts[status] = counts.get(status, 0) + 1
    summary = {
        "schema_version": "0.1",
        "status": "field_binding_inventory_complete_no_fact_promotion",
        "fact_records": len(facts),
        "binding_status_counts": counts,
        "promoted_to_tier_b": 0,
        "interpretation": (
            "unique_literal means one task-level evidence quote contains the exact scalar. It does "
            "not yet prove unit, period, boundary, calculation lineage, or cell-level uniqueness."
        ),
        "inputs": {
            "facts_sha256": sha256_file(fact_path),
            "source_audits_sha256": sha256_file(audit_path),
        },
        "output": {
            "path": "data/knowledge_bases/v0.1/field_evidence_bindings.jsonl",
            "sha256": sha256_file(binding_path),
        },
        "next_gate": "qualifier and cell-level validation for unique literal bindings",
    }
    summary_path = kb_dir / "field_evidence_binding_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
