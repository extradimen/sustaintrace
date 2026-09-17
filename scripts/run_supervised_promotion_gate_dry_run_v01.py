from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.promotion_gate import evaluate_promotion_dry_run

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/supervised_promotion_gate_dry_run_v0.1.lock.json"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
TRUSTED = ROOT / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
OUTPUT = ROOT / "artifacts/supervised_promotion_gate_dry_run_v0.1"


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    summary_path = OUTPUT / "dry_run_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_supervised_promotion_gate_dry_run")
    manifest = json.loads(MANIFEST.read_text())
    expected_hashes = manifest["parent_hashes"]
    for path, key in (
        (FACTS, "fact_records"),
        (TRUSTED, "trusted_fact_records"),
        (GAPS, "knowledge_gap_records"),
    ):
        if sha256_file(path) != expected_hashes[key]:
            raise ValueError(f"parent_hash_mismatch:{key}")

    candidate_facts = {item["record_id"]: item for item in _jsonl(FACTS)}
    trusted_facts = {item["record_id"]: item for item in _jsonl(TRUSTED)}
    gaps = defaultdict(list)
    for item in _jsonl(GAPS):
        gaps[item["fact_record_id"]].append(item["gap_signature"])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    for case in manifest["cases"]:
        fact_id = case["fact_record_id"]
        facts = trusted_facts if case["layer"] == "trusted_positive_control" else candidate_facts
        result = evaluate_promotion_dry_run(facts[fact_id], gaps[fact_id], ROOT)
        result["sample_layer"] = case["layer"]
        result["expected_decision_matched"] = (
            result["decision"] == case["expected_decision"]
        )
        path = OUTPUT / f"{fact_id}.dry-run.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        records.append(
            {
                "fact_record_id": fact_id,
                "layer": case["layer"],
                "decision": result["decision"],
                "expected_decision_matched": result["expected_decision_matched"],
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )

    summary = {
        "schema_version": "0.1",
        "status": "supervised_promotion_gate_dry_run_complete",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256_file(MANIFEST),
        "records": records,
        "eligible": sum(item["decision"] == "eligible" for item in records),
        "blocked": sum(item["decision"] == "blocked" for item in records),
        "expected_decisions_matched": sum(
            item["expected_decision_matched"] for item in records
        ),
        "promotion_performed": False,
        "fact_write_performed": False,
        "trusted_layer_modified": False,
        "cloud_transmission_performed": False,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "eligible": summary["eligible"],
                "blocked": summary["blocked"],
                "matched": summary["expected_decisions_matched"],
            }
        )
    )


if __name__ == "__main__":
    main()
