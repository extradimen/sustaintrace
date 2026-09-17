from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def spec(boundary: str, method: str, text: str, coordinate: str) -> dict[str, str]:
    return {
        "boundary": boundary,
        "method": method,
        "text": text,
        "coordinate": coordinate,
    }


SPECS = {
    "fact-62234554a98221e8c3ce2772": spec(
        "all work-related fatalities stated for BMW Group sites; employees and external workers",
        "enumerated_total",
        "There were a total of 4 fatalities due to work-related accidents",
        (
            "The disclosed total is exhaustively decomposed into one BMW Group employee and "
            "three workers of external companies at BMW Group sites."
        ),
    ),
    "fact-1f8cdc4d2a7d244d7ce169be": spec(
        "total energy consumption reported by Deutsche Telekom Group",
        "metric_total_row",
        "Total energy consumption | 11,956,990 | 11,990,733",
        (
            "The selected value is in the table's Total energy consumption row rather than a "
            "fuel or renewable-energy component row."
        ),
    ),
    "fact-6ae0e913c820700806916dc9": spec(
        "Deutsche Telekom employees outside Germany, measured in FTEs",
        "geography_row",
        "International | 127,327 | 123,644",
        "The value is selected from the International geography row and the FTE table unit.",
    ),
    "fact-8da460bee64eb4ecb292f56f": spec(
        "Deutsche Telekom employees in Germany, measured in FTEs",
        "geography_row",
        "Germany | 70,751 | 74,550",
        "The value is selected from the Germany geography row and the FTE table unit.",
    ),
    "fact-b1ce8eff559dad748d0d183d": spec(
        "Deutsche Telekom employees in Germany, measured in FTEs",
        "geography_row",
        "Germany | 70,751 | 74,550",
        "The value is selected from the Germany geography row and the FTE table unit.",
    ),
    "fact-f4607bdd70e350a4cc5a322a": spec(
        "Deutsche Telekom employees outside Germany, measured in FTEs",
        "geography_row",
        "International | 127,327 | 123,644",
        "The value is selected from the International geography row and the FTE table unit.",
    ),
    "fact-5c9806380a1237336b292178": spec(
        "Novo Nordisk total energy consumption related to own operations",
        "own_operations_row",
        "Total energy consumption related to own operations | 1,726 | 1,400 | 1,051",
        (
            "The row label explicitly restricts the total to energy consumption related to "
            "own operations."
        ),
    ),
    "fact-78f2df4d250210c3cd7fe53e": spec(
        "Novo Nordisk total energy consumption related to own operations",
        "own_operations_row",
        "Total energy consumption related to own operations | 1,726 | 1,400 | 1,051",
        (
            "The row label explicitly restricts the total to energy consumption related to "
            "own operations."
        ),
    ),
    "fact-896053181b213daa2d759c9d": spec(
        "Novo Nordisk energy consumption from renewable sources in own operations",
        "own_operations_row",
        "Total energy consumption from renewable sources | 984 | 924",
        (
            "The value is selected from the renewable-sources row within the own-operations "
            "energy table."
        ),
    ),
    "fact-e42fb7592c311e4e31456c72": spec(
        "Novo Nordisk total CapEx denominator in the adjusted EU Taxonomy overview",
        "taxonomy_denominator_row",
        "Total Turnover and CapEx | 309,064 | 100 | 94,249 | 100",
        (
            "The 94,249 mDKK cell is the 100% total CapEx denominator, not the eligible or "
            "aligned subset."
        ),
    ),
    "fact-801e0154afff454f20f6cda2": spec(
        "Novo Nordisk own-workforce employees with permanent employment contracts",
        "employment_type_clause",
        "By end of 2025, Novo Nordisk employed 64,974 permanent and 4,531 temporary employees",
        (
            "The sentence explicitly labels 64,974 as permanent employees in Novo Nordisk's "
            "own workforce disclosure."
        ),
    ),
    "fact-be7af8998b7c2d573d35fc01": spec(
        "Novo Nordisk own-workforce employees with temporary employment contracts",
        "employment_type_clause",
        "By end of 2025, Novo Nordisk employed 64,974 permanent and 4,531 temporary employees",
        (
            "The sentence explicitly labels 4,531 as temporary employees in Novo Nordisk's "
            "own workforce disclosure."
        ),
    ),
    "fact-cea0a41e87c27cadecde5fcc": spec(
        "Novo Nordisk own-workforce employees with temporary employment contracts",
        "employment_type_clause",
        "similar to the 2024 split (68,669 permanent and 5,487 temporary)",
        "The parenthetical comparison explicitly labels 5,487 as temporary employees.",
    ),
    "fact-ec25d92c731e09bd196ea6f7": spec(
        "Novo Nordisk own-workforce employees with permanent employment contracts",
        "employment_type_clause",
        "similar to the 2024 split (68,669 permanent and 5,487 temporary)",
        "The parenthetical comparison explicitly labels 68,669 as permanent employees.",
    ),
    "fact-9340e325ddeec5f8b83b6b93": spec(
        "Holcim total operating expenditure under the EU Taxonomy definition",
        "taxonomy_denominator_row",
        "Total | 949 | 100% | Operating expenditure based on EU Taxonomy definition",
        (
            "The 949 mCHF cell is the 100% total OpEx denominator; the source also marks the "
            "taxonomy disclosures unaudited, so boundary resolution alone does not permit "
            "promotion."
        ),
    ),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    matrix_path = KB / "tier_b_blocker_matrix.jsonl"
    facts_path = KB / "fact_records.jsonl"
    period_simple_path = KB / "tier_b_blocker_resolutions.jsonl"
    period_coordinate_path = KB / "period_coordinate_adjudications.jsonl"
    matrix = {r["fact_record_id"]: r for r in load_jsonl(matrix_path)}
    facts = {r["record_id"]: r for r in load_jsonl(facts_path)}
    resolved_period_ids = {
        r["fact_record_id"] for r in load_jsonl(period_simple_path)
    } | {r["fact_record_id"] for r in load_jsonl(period_coordinate_path)}
    records = []
    for fact_id, candidate in SPECS.items():
        item = matrix[fact_id]
        fact = facts[fact_id]
        if item["boundary_plan"] != "explicit_label_candidate":
            raise ValueError(f"unexpected boundary plan: {fact_id}")
        if "BOUNDARY_ATTACHMENT_INCOMPLETE" not in item["blocking_signatures"]:
            raise ValueError(f"missing boundary blocker: {fact_id}")
        document = fact["subject"]["document_metadata"][0]
        artifact = ROOT / document["local_path"]
        if sha256_file(artifact) != document["sha256"]:
            raise ValueError(f"source artifact hash mismatch: {fact_id}")
        effective = [
            blocker
            for blocker in item["blocking_signatures"]
            if blocker != "BOUNDARY_ATTACHMENT_INCOMPLETE"
            and not (
                blocker == "PERIOD_ATTACHMENT_INCOMPLETE" and fact_id in resolved_period_ids
            )
        ]
        identity = {
            "fact_record_id": fact_id,
            "resolved_boundary": candidate["boundary"],
            "coordinate_method": candidate["method"],
        }
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "boundary_coordinate_adjudication",
                "adjudication_id": stable_id("boundary-adj", identity),
                "fact_record_id": fact_id,
                "task_id": item["task_id"],
                "predicate": item["predicate"],
                "value": fact["value"],
                "resolved_boundary": candidate["boundary"],
                "coordinate_method": candidate["method"],
                "source_artifact": document["local_path"],
                "source_artifact_sha256": document["sha256"],
                "source_page": item["source_native_page"],
                "source_text": candidate["text"],
                "coordinate_description": candidate["coordinate"],
                "resolved_signature": "BOUNDARY_ATTACHMENT_INCOMPLETE",
                "effective_blockers": effective,
                "effective_status": (
                    "ready_for_independent_source_review"
                    if not effective
                    else "blocked_additional_qualification"
                ),
                "execution_mode": "derived_layer_only",
                "rollback": "delete_boundary_coordinate_adjudication",
                "source_fact_modified": False,
                "promotion_performed": False,
            }
        )
    records.sort(key=lambda r: (r["task_id"], r["fact_record_id"]))
    schema_path = ROOT / "schemas/knowledge/boundary-coordinate-adjudication-v0.1.schema.json"
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "boundary_coordinate_adjudications.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for r in records
        ),
        encoding="utf-8",
    )
    status_counts = Counter(r["effective_status"] for r in records)
    summary = {
        "schema_version": "0.1",
        "status": "explicit_boundary_coordinates_adjudicated_in_derived_layer",
        "adjudications": len(records),
        "coordinate_method_counts": dict(
            sorted(Counter(r["coordinate_method"] for r in records).items())
        ),
        "newly_ready_for_independent_source_review": status_counts[
            "ready_for_independent_source_review"
        ],
        "remaining_boundary_blockers": sum(
            "BOUNDARY_ATTACHMENT_INCOMPLETE" in r["blocking_signatures"]
            and r["fact_record_id"] not in SPECS
            for r in matrix.values()
        ),
        "remaining_boundary_plan": "semantic_supervision_required",
        "source_fact_records_modified": 0,
        "promotions_performed": 0,
        "rollback_ledgers": len(records),
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "blocker_matrix_sha256": sha256_file(matrix_path),
            "fact_records_sha256": sha256_file(facts_path),
            "simple_period_resolutions_sha256": sha256_file(period_simple_path),
            "period_coordinate_adjudications_sha256": sha256_file(period_coordinate_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": "independent-source review without treating boundary resolution as promotion",
    }
    summary_path = KB / "boundary_coordinate_adjudication_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
