from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    plans_path = KB / "boundary_repair_controller_dry_run.jsonl"
    validations_path = KB / "metric_component_boundary_validations.jsonl"
    facts_path = KB / "fact_records.jsonl"
    bindings_path = KB / "source_native_field_bindings.jsonl"
    cases_path = KB / "boundary_semantic_negative_cases.jsonl"
    metric_case_ids = {
        item["case_id"] for item in load_jsonl(cases_path)
        if item["boundary_class"] == "metric_component_boundary"
    }
    plans = {
        item["fact_record_id"]: item for item in load_jsonl(plans_path)
        if item["case_id"] in metric_case_ids and item["decision"] == "supervised_candidate"
    }
    validations = {
        item["fact_record_id"]: item for item in load_jsonl(validations_path)
    }
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    bindings = {
        item["fact_record_id"]: item for item in load_jsonl(bindings_path)
    }
    records = []
    for fact_id, plan in plans.items():
        validation = validations[fact_id]
        fact = facts[fact_id]
        binding = bindings[fact_id]
        coordinate = validation["table_coordinate"]
        document = fact["subject"]["document_metadata"][0]
        if plan["validation_id"] != validation["validation_id"]:
            raise ValueError(f"validation lineage mismatch: {fact_id}")
        if sha256_file(ROOT / document["local_path"]) != document["sha256"]:
            raise ValueError(f"source hash mismatch: {fact_id}")
        resolved_boundary = (
            f"table={coordinate['graph_id']}; row={coordinate['row']}; "
            f"column={coordinate['column']}; role={coordinate['component_role']}; "
            f"method={coordinate['method_role']}; footnote={coordinate['footnote']}"
        )
        identity = {
            "fact_record_id": fact_id,
            "plan_id": plan["plan_id"],
            "validation_id": validation["validation_id"],
        }
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "metric_component_boundary_adjudication",
                "adjudication_id": stable_id("metric-boundary-adj", identity),
                "plan_id": plan["plan_id"],
                "validation_id": validation["validation_id"],
                "fact_record_id": fact_id,
                "task_id": fact["subject"]["task_id"],
                "predicate": fact["predicate"]["canonical_key"],
                "value": fact["value"],
                "resolved_boundary": resolved_boundary,
                "table_coordinate": coordinate,
                "source_artifact": document["local_path"],
                "source_artifact_sha256": document["sha256"],
                "source_page": binding["pdf_page"],
                "source_text": binding["candidates"][0]["context"],
                "resolved_signature": "BOUNDARY_ATTACHMENT_INCOMPLETE",
                "effective_blockers": [],
                "effective_status": "ready_for_independent_source_review",
                "execution_mode": "derived_layer_only",
                "rollback": "delete_metric_component_boundary_adjudication",
                "source_fact_modified": False,
                "promotion_performed": False,
            }
        )
    records.sort(key=lambda item: (item["task_id"], item["predicate"]))
    schema_path = (
        ROOT / "schemas/knowledge/metric-component-boundary-adjudication-v0.1.schema.json"
    )
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "metric_component_boundary_adjudications.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    summary = {
        "schema_version": "0.1",
        "status": "metric_component_boundaries_adjudicated_in_derived_layer",
        "adjudications": len(records),
        "ready_for_independent_source_review": len(records),
        "source_fact_records_modified": 0,
        "promotions_performed": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "plans_sha256": sha256_file(plans_path),
            "validations_sha256": sha256_file(validations_path),
            "facts_sha256": sha256_file(facts_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": "independent_six_dimension_review_before_tier_b_promotion",
    }
    summary_path = KB / "metric_component_boundary_adjudication_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
