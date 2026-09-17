from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_controller import plan_boundary_repair

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    cases_path = KB / "boundary_semantic_negative_cases.jsonl"
    ontology_path = ROOT / "configs/knowledge/boundary_semantic_ontology_v0.1.json"
    validators_path = ROOT / "configs/knowledge/boundary_validator_catalog_v0.1.json"
    assurance_validations_path = KB / "assurance_boundary_validations.jsonl"
    metric_validations_path = KB / "metric_component_boundary_validations.jsonl"
    taxonomy_validations_path = KB / "taxonomy_boundary_validations.jsonl"
    population_validations_path = KB / "organizational_population_boundary_validations.jsonl"
    target_validations_path = KB / "target_performance_boundary_validations.jsonl"
    ontology = json.loads(ontology_path.read_text())
    validators = json.loads(validators_path.read_text())
    assurance_validations = {
        item["case_id"]: item for item in load_jsonl(assurance_validations_path)
    }
    validations = {
        **assurance_validations,
        **{item["case_id"]: item for item in load_jsonl(metric_validations_path)},
        **{item["case_id"]: item for item in load_jsonl(taxonomy_validations_path)},
        **{item["case_id"]: item for item in load_jsonl(population_validations_path)},
        **{item["case_id"]: item for item in load_jsonl(target_validations_path)},
    }
    records = [
        plan_boundary_repair(
            case, ontology, validators, validations.get(case["case_id"])
        )
        for case in load_jsonl(cases_path)
    ]
    records.sort(key=lambda r: (r["boundary_class"], r["fact_record_id"]))
    output_path = KB / "boundary_repair_controller_dry_run.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for r in records
        ),
        encoding="utf-8",
    )
    decisions = Counter(r["decision"] for r in records)
    summary = {
        "schema_version": "0.1",
        "status": "semantic_boundary_controller_dry_run_fail_closed",
        "plans": len(records),
        "decision_counts": dict(sorted(decisions.items())),
        "executions_performed": 0,
        "promotions_performed": 0,
        "inputs": {
            "negative_cases_sha256": sha256_file(cases_path),
            "ontology_sha256": sha256_file(ontology_path),
            "validator_catalog_sha256": sha256_file(validators_path),
            "assurance_validations_sha256": sha256_file(assurance_validations_path),
            "metric_validations_sha256": sha256_file(metric_validations_path),
            "taxonomy_validations_sha256": sha256_file(taxonomy_validations_path),
            "population_validations_sha256": sha256_file(population_validations_path),
            "target_validations_sha256": sha256_file(target_validations_path),
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "execute only validated candidates under supervision; "
            "keep all unvalidated classes blocked"
        ),
    }
    summary_path = KB / "boundary_repair_controller_dry_run_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
