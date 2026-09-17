from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import validate

from esg_reliable_discovery.knowledge_query import query_facts

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    schema_path = ROOT / "schemas/knowledge/fact-query-response-v0.1.schema.json"
    implementation_path = ROOT / "src/esg_reliable_discovery/knowledge_query.py"
    ranking_path = KB / "repair_gap_rankings.jsonl"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    default_result = query_facts(KB)
    candidate_result = query_facts(
        KB,
        task_id="P23-GHG-CALC-001",
        include_candidates=True,
        limit=100,
    )
    validate(default_result, schema)
    validate(candidate_result, schema)
    if len(default_result["records"]) != 10:
        raise RuntimeError("default query did not expose exactly the promoted Tier B records")
    if any(item["effective_trust"] != "trusted_tier_b" for item in default_result["records"]):
        raise RuntimeError("default query exposed non-promoted records")
    if any(
        item["effective_trust"] != "candidate_not_trusted" for item in candidate_result["records"]
    ):
        raise RuntimeError("candidate query misrepresented trust")

    output = {
        "schema_version": "0.1",
        "status": "passed",
        "default_policy": "promoted_tier_b_only",
        "default_records_returned": len(default_result["records"]),
        "candidate_opt_in_task": "P23-GHG-CALC-001",
        "candidate_records_returned": len(candidate_result["records"]),
        "trusted_tier_b_inventory": default_result["inventory"]["trusted_tier_b"],
        "candidates_not_trusted_inventory": default_result["inventory"]["candidates_not_trusted"],
        "locked_experiments_modified_or_rescored": False,
        "artifacts": {
            "implementation": {
                "path": implementation_path.relative_to(ROOT).as_posix(),
                "sha256": sha256(implementation_path),
            },
            "schema": {
                "path": schema_path.relative_to(ROOT).as_posix(),
                "sha256": sha256(schema_path),
            },
            "repair_gap_rankings": {
                "path": ranking_path.relative_to(ROOT).as_posix(),
                "sha256": sha256(ranking_path),
            },
        },
        "next_gate": "audit the 53 Tier B queue items blocked by period or boundary qualification",
    }
    output_path = ROOT / "data/results/knowledge_query_v01_validation.lock.json"
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
