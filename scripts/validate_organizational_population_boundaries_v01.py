from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records
from esg_reliable_discovery.repair_controller import validate_organizational_population_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

SPECS = {
    "fact-6062d3c7c5e37b393ab17a6f": {
        "global_headcount": 46055,
        "covered_headcount": 43875,
        "excluded_headcount": 2180,
        "permanent_employees": 40590,
        "temporary_employees": 3285,
        "scope_role": "hr_system_covered_employee_population_gap",
        "audit_status": "pending_independent_scope_review",
    },
    "fact-e006f9b4f707f3abf5c2059c": {
        "global_headcount": 46055,
        "covered_headcount": 43875,
        "excluded_headcount": 2180,
        "permanent_employees": 40590,
        "temporary_employees": 3285,
        "scope_role": "global_group_employee_population",
        "audit_status": "pending_independent_scope_review",
    },
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    cases_path = KB / "boundary_semantic_negative_cases.jsonl"
    facts_path = KB / "fact_records.jsonl"
    bindings_path = KB / "source_native_field_bindings.jsonl"
    cases = [
        item
        for item in load_jsonl(cases_path)
        if item["boundary_class"] == "organizational_population_boundary"
    ]
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    bindings = {item["fact_record_id"]: item for item in load_jsonl(bindings_path)}
    supporting_context = "\n".join(
        candidate.get("context", "")
        for binding in bindings.values()
        if binding.get("task_id") == "P20-WORKFORCE-001"
        for candidate in binding.get("candidates", [])
    )
    specs = {
        fact_id: {**spec, "supporting_context": supporting_context}
        for fact_id, spec in SPECS.items()
    }
    records = [
        validate_organizational_population_case(
            case,
            facts[case["fact_record_id"]],
            bindings[case["fact_record_id"]],
            ROOT,
            specs[case["fact_record_id"]],
        )
        for case in cases
    ]
    records.sort(key=lambda item: (item["task_id"], item["predicate"]))
    schema_path = (
        ROOT / "schemas/knowledge/organizational-population-boundary-validation-v0.1.schema.json"
    )
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "organizational_population_boundary_validations.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    counts = Counter(item["validation_status"] for item in records)
    summary = {
        "schema_version": "0.1",
        "status": "organizational_population_boundary_validation_complete",
        "records": len(records),
        "validation_status_counts": dict(sorted(counts.items())),
        "executions_performed": 0,
        "promotions_performed": 0,
        "inputs": {
            "cases_sha256": sha256_file(cases_path),
            "facts_sha256": sha256_file(facts_path),
            "bindings_sha256": sha256_file(bindings_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": "enable only after positive and destructive-negative regression",
    }
    summary_path = KB / "organizational_population_boundary_validation_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
