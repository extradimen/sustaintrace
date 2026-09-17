from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records
from esg_reliable_discovery.repair_controller import validate_target_performance_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

SPECS = {
    "fact-f216f8cbb3e2c3cc919d7b20": {
        "expected_value": 80,
        "claim_role": "target",
        "metric": "absolute greenhouse gas emissions reduction",
        "unit": "percent",
        "target_year": 2030,
        "performance_year": None,
        "baseline_or_comparator": 2020,
        "baseline_relation": "from a 2020 baseline",
        "scope_boundary": "all scopes; remaining 20% addressed through nature-based solutions",
        "resolved_relation": (
            "80% absolute reduction by 2030 from a 2020 baseline across all scopes"
        ),
        "required_phrases": [
            "80% absolute reduction",
            "2020 baseline",
            "all scopes",
            "remaining 20%",
            "by 2030",
        ],
        "metric_scope_markers": ["greenhouse gas emissions", "all scopes"],
        "forbidden_relation_phrases": ["2045", "14% compared with 2024"],
        "audit_status": "pending_independent_scope_review",
    },
    "fact-c55b9e3044693eae5b62d18e": {
        "expected_value": 90,
        "claim_role": "target",
        "metric": "absolute greenhouse gas emissions reduction",
        "unit": "percent",
        "target_year": 2045,
        "performance_year": None,
        "baseline_or_comparator": 2020,
        "baseline_relation": "from a 2020 baseline",
        "scope_boundary": "full value chain; all scopes; residual emissions neutralised",
        "resolved_relation": (
            "90% absolute reduction by 2045 from a 2020 baseline across all scopes"
        ),
        "required_phrases": [
            "by 2045",
            "90% absolute reduction",
            "2020 baseline",
            "all scopes",
            "residual",
            "neutralised",
        ],
        "metric_scope_markers": ["emissions", "all scopes"],
        "forbidden_relation_phrases": ["2030", "14% compared with 2024"],
        "audit_status": "pending_independent_scope_review",
    },
    "fact-13f596f084681dd4cdf45571": {
        "expected_value": 14,
        "claim_role": "achieved_performance",
        "metric": "Scope 1 and 2 carbon emissions reduction",
        "unit": "percent",
        "target_year": None,
        "performance_year": 2025,
        "baseline_or_comparator": 2024,
        "baseline_relation": "compared with 2024",
        "scope_boundary": "Scope 1 and Scope 2 carbon emissions",
        "resolved_relation": "2025 Scope 1 and 2 emissions were 14% lower than 2024",
        "required_phrases": ["in 2025", "scope 1 & 2", "by 14%", "compared with 2024"],
        "metric_scope_markers": ["scope 1 & 2", "carbon emissions"],
        "forbidden_relation_phrases": ["45%", "2020 baseline", "target"],
        "audit_status": "pending_independent_scope_review",
    },
    "fact-613133ef28d2d55bb47991eb": {
        "expected_value": 30,
        "claim_role": "achieved_performance",
        "metric": "overall operational water-use reduction",
        "unit": "percent",
        "target_year": None,
        "performance_year": 2025,
        "baseline_or_comparator": 2020,
        "baseline_relation": "from our 2020 baseline",
        "scope_boundary": "overall water use in GSK operations",
        "resolved_relation": "2025 overall operational water use was 30% below the 2020 baseline",
        "required_phrases": ["in 2025", "overall water use", "decrease of 30%", "2020 baseline"],
        "metric_scope_markers": ["water use", "operations"],
        "forbidden_relation_phrases": ["additional 3%", "compared with 2024", "target"],
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
        if item["boundary_class"] == "target_and_performance_boundary"
    ]
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    bindings = {item["fact_record_id"]: item for item in load_jsonl(bindings_path)}
    supporting_context = "\n".join(
        candidate.get("context", "")
        for binding in bindings.values()
        if binding.get("task_id", "").startswith("P23-")
        for candidate in binding.get("candidates", [])
    )
    specs = {
        key: {**value, "supporting_context": supporting_context} for key, value in SPECS.items()
    }
    records = [
        validate_target_performance_case(
            case,
            facts[case["fact_record_id"]],
            bindings[case["fact_record_id"]],
            ROOT,
            specs[case["fact_record_id"]],
        )
        for case in cases
    ]
    records.sort(key=lambda item: (item["task_id"], item["predicate"]))
    schema_path = ROOT / "schemas/knowledge/target-performance-boundary-validation-v0.1.schema.json"
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "target_performance_boundary_validations.jsonl"
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
        "status": "target_performance_boundary_validation_complete",
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
    summary_path = KB / "target_performance_boundary_validation_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
