from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_controller import validate_assurance_boundary_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

BOUNDARIES = {
    "incorporated_reference_pages": (
        "pages explicitly incorporated into and covered by the independent assurance "
        "engagement"
    ),
    "governing_standard": "standard governing the signed independent assurance engagement",
    "signatory": "named partner signing the independent verifier report",
    "signature_location": "location attached to the signed independent assurance report",
    "location": "location attached to the signed independent assurance report",
    "conclusion_form": (
        "limited-assurance conclusion on the stated sustainability statement, subject "
        "to explicit exclusions"
    ),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    cases_path = KB / "boundary_semantic_negative_cases.jsonl"
    facts_path = KB / "fact_records.jsonl"
    bindings_path = KB / "source_native_field_bindings.jsonl"
    resolutions_path = KB / "tier_b_blocker_resolutions.jsonl"
    cases = [
        item for item in load_jsonl(cases_path)
        if item["boundary_class"] == "assurance_scope_metadata"
    ]
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    bindings = {
        item["fact_record_id"]: item for item in load_jsonl(bindings_path)
    }
    resolutions = {
        item["fact_record_id"]: item for item in load_jsonl(resolutions_path)
    }
    records = [
        validate_assurance_boundary_case(
            case,
            facts[case["fact_record_id"]],
            bindings[case["fact_record_id"]],
            resolutions.get(case["fact_record_id"]),
            ROOT,
            BOUNDARIES[case["predicate"]],
        )
        for case in cases
    ]
    records.sort(key=lambda item: (item["task_id"], item["predicate"]))
    output_path = KB / "assurance_boundary_validations.jsonl"
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
        "status": "assurance_boundary_validation_complete",
        "records": len(records),
        "validation_status_counts": dict(sorted(counts.items())),
        "executions_performed": 0,
        "promotions_performed": 0,
        "inputs": {
            path.name: sha256_file(path)
            for path in (cases_path, facts_path, bindings_path, resolutions_path)
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "validator_enabled_after_positive_and_negative_regression; execute only as "
            "supervised candidates before any promotion"
        ),
    }
    summary_path = KB / "assurance_boundary_validation_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
