from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records
from esg_reliable_discovery.repair_controller import validate_taxonomy_boundary_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

SPECS = {
    "fact-041d636e29fb4342bca2b91f": {
        "value_literal": "EUR 0.4 billion",
        "required_phrases": ["opex denominator", "EUR 0.4 billion", "EUR 2.9 billion"],
        "resolved_role": "original 2024 OpEx denominator before retrospective revision",
        "forbidden_roles": ["eligible", "aligned"],
        "value_kind": "amount", "unit": "EUR billion", "period": "2024 original",
        "evidence_mode": "native_narrative_relation",
        "audit_status": "pending_independent_scope_review",
    },
    "fact-09588e44f1569416df2ceb81": {
        "value_literal": "2,491",
        "required_phrases": ["not assessed activities considered non-material", "2,491"],
        "resolved_role": "CapEx non-material not-assessed amount",
        "forbidden_roles": ["eligible", "aligned", "denominator"],
        "value_kind": "amount", "unit": "mDKK", "period": "2025",
        "evidence_mode": "native_table_row",
        "audit_status": "pending_independent_scope_review",
    },
    "fact-d7db285f3ff95967345c9a1c": {
        "value_literal": "5,835",
        "required_phrases": ["eligible and aligned", "5,835"],
        "resolved_role": "aligned CapEx amount",
        "forbidden_roles": ["denominator", "non-material"],
        "value_kind": "amount", "unit": "mDKK", "period": "2025",
        "evidence_mode": "frozen_graph_and_native",
        "audit_status": "pending_independent_scope_review",
    },
    "fact-3ad175a12bcb5cac8885a626": {
        "value_literal": "9.8 %",
        "required_phrases": ["eligible and aligned", "93", "9.8 %"],
        "resolved_role": "aligned OpEx percentage",
        "forbidden_roles": ["denominator", "eligible amount"],
        "value_kind": "percentage", "unit": "percent", "period": "2025",
        "evidence_mode": "frozen_graph_and_native",
        "audit_status": "explicitly_unaudited",
    },
    "fact-8d97f35c5a96186e17080497": {
        "value_literal": "CHF 1 038 million",
        "required_phrases": ["total eligible CapEx", "CHF 1 038 million"],
        "resolved_role": "eligible CapEx amount",
        "forbidden_roles": ["aligned", "denominator"],
        "value_kind": "amount", "unit": "million CHF", "period": "2025",
        "evidence_mode": "native_narrative_relation",
        "audit_status": "explicitly_unaudited",
    },
    "fact-81898576258e081fd69a2cd8": {
        "value_literal": "€7,054 million",
        "required_phrases": [
            "operating expenditure totaling €7,054 million",
            "could not be identified",
        ],
        "resolved_role": "OpEx denominator amount",
        "forbidden_roles": ["eligible", "aligned"],
        "value_kind": "amount", "unit": "million EUR", "period": "2025",
        "evidence_mode": "native_narrative_relation",
        "audit_status": "pending_independent_scope_review",
    },
    "fact-9a64a6f4c9c806d666160125": {
        "value_literal": "€284 million",
        "required_phrases": ["taxonomy-eligible capital expenditure", "€284 million"],
        "resolved_role": "eligible CapEx amount",
        "forbidden_roles": ["aligned", "denominator"],
        "value_kind": "amount", "unit": "million EUR", "period": "2025",
        "evidence_mode": "native_narrative_relation",
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
        item for item in load_jsonl(cases_path)
        if item["boundary_class"] == "taxonomy_classification_boundary"
    ]
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    bindings = {item["fact_record_id"]: item for item in load_jsonl(bindings_path)}
    records = [
        validate_taxonomy_boundary_case(
            case,
            facts[case["fact_record_id"]],
            bindings[case["fact_record_id"]],
            ROOT,
            SPECS[case["fact_record_id"]],
        )
        for case in cases
    ]
    records.sort(key=lambda item: (item["task_id"], item["predicate"]))
    schema_path = ROOT / "schemas/knowledge/taxonomy-boundary-validation-v0.1.schema.json"
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "taxonomy_boundary_validations.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    counts = Counter(item["validation_status"] for item in records)
    summary = {
        "schema_version": "0.1",
        "status": "taxonomy_boundary_validation_complete",
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
        "next_gate": (
            "validator_enabled_after_regression; five supervised candidates and two "
            "explicitly unaudited blocks"
        ),
    }
    summary_path = KB / "taxonomy_boundary_validation_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
