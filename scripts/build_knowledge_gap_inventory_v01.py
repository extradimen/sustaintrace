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


def add_gap(
    records: list[dict[str, Any]],
    qualification: dict[str, Any],
    signature: str,
    current: str,
    required: str,
    repair: str,
    policy: str,
    sources: list[str],
) -> None:
    fact_id = qualification["fact_record_id"]
    identity = {"fact_record_id": fact_id, "gap_signature": signature}
    records.append(
        {
            "schema_version": "0.1",
            "record_kind": "knowledge_gap",
            "gap_id": stable_id("gap", identity),
            "fact_record_id": fact_id,
            "task_id": qualification["task_id"],
            "gap_signature": signature,
            "severity": "blocking" if policy == "blocked" else "qualification",
            "current_state": current,
            "required_state": required,
            "recommended_repair": repair,
            "execution_policy": policy,
            "source_artifacts": sources,
        }
    )


def main() -> None:
    joint_path = KB / "joint_fact_qualifications.jsonl"
    native_path = KB / "native_pdf_corroborations.jsonl"
    replay_path = KB / "calculation_replay_audits.jsonl"
    joints = load_jsonl(joint_path)
    native = {item["fact_record_id"]: item for item in load_jsonl(native_path)}
    records: list[dict[str, Any]] = []
    joint_source = [joint_path.relative_to(ROOT).as_posix()]
    for item in joints:
        if item["field_binding_status"] != "unique_literal":
            add_gap(
                records,
                item,
                "FIELD_EVIDENCE_BINDING_INCOMPLETE",
                item["field_binding_status"],
                "unique field-to-evidence binding",
                "run structural collection binding or isolate a unique source cell",
                "supervised",
                joint_source,
            )
        for field, signature, required, repair in (
            (
                "period_binding",
                "PERIOD_ATTACHMENT_INCOMPLETE",
                "field or cell-level period",
                "bind the field to a frozen period header",
            ),
            (
                "unit_binding",
                "UNIT_ATTACHMENT_INCOMPLETE",
                "field or cell-level unit",
                "capture and bind the table or narrative unit header",
            ),
            (
                "boundary_binding",
                "BOUNDARY_ATTACHMENT_INCOMPLETE",
                "field-level scope boundary",
                "bind a caption, note, or boundary clause to the field",
            ),
        ):
            status = item[field]["status"]
            if status in {"not_declared", "reference_task_level", "semantic_task_level"}:
                add_gap(
                    records,
                    item,
                    signature,
                    status,
                    required,
                    repair,
                    "supervised" if field == "boundary_binding" else "deterministic_candidate",
                    joint_source,
                )
        table_status = item["table_cell_binding"]["status"]
        if table_status in {"ambiguous_selected_cells", "graph_present_cell_unbound"}:
            add_gap(
                records,
                item,
                "TABLE_CELL_BINDING_INCOMPLETE",
                table_status,
                "one frozen row-column-value coordinate",
                "rebuild the selected-cell graph from frozen layout evidence",
                "supervised",
                joint_source,
            )
        if item["calculation_lineage"]["status"] in {
            "legacy_expression_only",
            "frozen_plan_output",
        }:
            add_gap(
                records,
                item,
                "CALCULATION_LINEAGE_INCOMPLETE",
                item["calculation_lineage"]["status"],
                "successful deterministic replay",
                "materialize all input cells and replay the frozen operation graph",
                "deterministic_candidate",
                joint_source,
            )
        native_item = native.get(item["fact_record_id"])
        if native_item and not native_item["status"].startswith("passed_"):
            add_gap(
                records,
                item,
                "NATIVE_PDF_CORROBORATION_INCOMPLETE",
                native_item["status"],
                "native parser corroboration",
                "recover source path or reconcile native text and layout extraction",
                "supervised",
                [*joint_source, native_path.relative_to(ROOT).as_posix()],
            )

    task_to_fact = {}
    for item in joints:
        task_to_fact.setdefault(item["task_id"], item)
    for replay in load_jsonl(replay_path):
        if replay["status"] == "passed":
            continue
        qualification = task_to_fact[replay["task_id"]]
        add_gap(
            records,
            qualification,
            "CALCULATION_INPUT_CELL_MISSING",
            replay["status"],
            "all frozen calculation input cells available",
            "extend the selected-cell graph without reading expected outputs",
            "supervised",
            [replay_path.relative_to(ROOT).as_posix()],
        )

    deduplicated = {item["gap_id"]: item for item in records}
    records = [deduplicated[key] for key in sorted(deduplicated)]
    schema = json.loads((ROOT / "schemas/knowledge/knowledge-gap-v0.1.schema.json").read_text())
    validate_records(records, schema)
    output_path = KB / "knowledge_gap_records.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )
    signatures = Counter(item["gap_signature"] for item in records)
    policies = Counter(item["execution_policy"] for item in records)
    summary = {
        "schema_version": "0.1",
        "status": "knowledge_gap_inventory_complete_no_repairs_executed",
        "gap_records": len(records),
        "signature_counts": dict(sorted(signatures.items())),
        "execution_policy_counts": dict(sorted(policies.items())),
        "repairs_executed": 0,
        "inputs": {
            "joint_qualifications_sha256": sha256_file(joint_path),
            "native_corroborations_sha256": sha256_file(native_path),
            "calculation_replays_sha256": sha256_file(replay_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "rank deterministic candidates by expected promotion yield and validate rollback"
        ),
    }
    summary_path = KB / "knowledge_gap_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"gaps": len(records), "signatures": dict(signatures)}, sort_keys=True))


if __name__ == "__main__":
    main()
