from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def classify(task_id: str) -> str:
    if "ASSURE" in task_id:
        return "assurance_scope_metadata"
    if "TAXONOMY" in task_id:
        return "taxonomy_classification_boundary"
    if "WORKFORCE" in task_id:
        return "organizational_population_boundary"
    if task_id.startswith("P23-"):
        return "target_and_performance_boundary"
    return "metric_component_boundary"


UNSAFE = {
    "assurance_scope_metadata": (
        "The literal may be correct while its engagement subject, assurance level or exclusion "
        "boundary remains unbound."
    ),
    "metric_component_boundary": (
        "A nearby scalar cannot establish its category, total/component status or control method."
    ),
    "taxonomy_classification_boundary": (
        "Eligibility, alignment, denominator and materiality are not interchangeable "
        "Taxonomy roles."
    ),
    "organizational_population_boundary": (
        "A workforce scalar cannot establish consolidation, acquisition or HR-system coverage."
    ),
    "target_and_performance_boundary": (
        "A percentage cannot select target year, baseline, scopes or comparison relation by "
        "proximity."
    ),
}

REQUIRED = {
    "assurance_scope_metadata": (
        "Signed assurance text that jointly binds the literal to engagement subject, assurance "
        "level and applicable inclusion/exclusion clauses."
    ),
    "metric_component_boundary": (
        "Source-local row, column, category and method coordinates, including applicable footnotes."
    ),
    "taxonomy_classification_boundary": (
        "Source-local Taxonomy role, denominator, activity class, materiality and audit-status "
        "evidence."
    ),
    "organizational_population_boundary": (
        "Explicit included/excluded population statement or deterministic population "
        "reconciliation."
    ),
    "target_and_performance_boundary": (
        "One source-local relation binding percentage, period roles, scope coverage and baseline."
    ),
}


def main() -> None:
    matrix_path = KB / "tier_b_blocker_matrix.jsonl"
    explicit_path = KB / "boundary_coordinate_adjudications.jsonl"
    ontology_path = ROOT / "configs/knowledge/boundary_semantic_ontology_v0.1.json"
    explicit_ids = {r["fact_record_id"] for r in load_jsonl(explicit_path)}
    unresolved = [
        r
        for r in load_jsonl(matrix_path)
        if "BOUNDARY_ATTACHMENT_INCOMPLETE" in r["blocking_signatures"]
        and r["fact_record_id"] not in explicit_ids
    ]
    records = []
    for item in unresolved:
        boundary_class = classify(item["task_id"])
        identity = {
            "fact_record_id": item["fact_record_id"],
            "boundary_class": boundary_class,
        }
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "boundary_semantic_negative_case",
                "case_id": stable_id("boundary-case", identity),
                "fact_record_id": item["fact_record_id"],
                "task_id": item["task_id"],
                "predicate": item["predicate"],
                "boundary_class": boundary_class,
                "current_status": "supervised_block",
                "unsafe_inference": UNSAFE[boundary_class],
                "required_evidence": REQUIRED[boundary_class],
                "automatic_action": "report_unresolved_and_do_not_promote",
                "source_fact_modified": False,
                "promotion_performed": False,
            }
        )
    records.sort(key=lambda r: (r["boundary_class"], r["task_id"], r["fact_record_id"]))
    schema_path = ROOT / "schemas/knowledge/boundary-semantic-negative-case-v0.1.schema.json"
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "boundary_semantic_negative_cases.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for r in records
        ),
        encoding="utf-8",
    )
    counts = Counter(r["boundary_class"] for r in records)
    summary = {
        "schema_version": "0.1",
        "status": "semantic_boundary_control_set_complete_fail_closed",
        "negative_cases": len(records),
        "class_counts": dict(sorted(counts.items())),
        "automatic_repairs_executed": 0,
        "promotions_performed": 0,
        "source_fact_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "blocker_matrix_sha256": sha256_file(matrix_path),
            "explicit_boundary_adjudications_sha256": sha256_file(explicit_path),
            "ontology_sha256": sha256_file(ontology_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "connect ontology classes to controller policies and permit execution only when a "
            "class-specific source-local validator is available"
        ),
    }
    summary_path = KB / "boundary_semantic_control_set_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
