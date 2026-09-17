# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from esg_reliable_discovery.archive import verify_run_checksums
from esg_reliable_discovery.v28_integrity import compare_text_slot_v28

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P22-V31-UNSEEN-LOCKBOX-V01"
PROGRESS = ROOT / "data/manifests/p22_candidate_progress.json"
PACK = ROOT / "data/tasks/p22_local_execution_task_pack_v0.1.lock.json"
CONTRACTS = ROOT / "configs/framework/p22_slot_contracts_v0.1.lock.json"
GOLD = ROOT / "data/annotations/p22_simulated/p22_atomic_slot_gold_v0.1.lock.json"
OUTPUT = ROOT / "data/results/p22_v31_dimension_scores_v0.1.lock.json"
FRAMEWORK_FAILED = {"P22-ENERGY-CALC-001", "P22-GHG-CALC-001", "P22-WATER-CALC-001", "P22-SAFETY-CALC-001"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    records = {item["task_id"]: item for item in progress["records"]}
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    contracts = json.loads(CONTRACTS.read_text(encoding="utf-8"))["contracts"]
    gold = json.loads(GOLD.read_text(encoding="utf-8"))["values"]
    runs_root = ROOT / "research_archive" / EXPERIMENT / "runs"
    verified_runs = 0
    for run in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        verify_run_checksums(run)
        verified_runs += 1
    task_scores: dict[str, object] = {}
    exact_total = credited_total = required_total = 0
    literal_total = normalized_total = numeric_total = 0
    literal_exact = normalized_exact = numeric_exact = 0
    for task in pack["tasks"]:
        task_id = task["task_id"]
        record, required, expected = records[task_id], contracts[task_id], gold[task_id]
        framework_failure = task_id in FRAMEWORK_FAILED
        stage_a_valid = record["stage_a"] == "passed" and not framework_failure
        requires_stage_b = task["task_type"] != "deterministic_calculation"
        stage_b_status = record.get("stage_b", "not_reached")
        final_valid = stage_a_valid and (stage_b_status == "passed" if requires_stage_b else True)
        values: dict[str, object] = {}
        if final_valid and requires_stage_b:
            run = Path(record["stage_b_result"]["archive_directory"])
            normalized = json.loads((run / "normalized_output.json").read_text())
            values = {claim["slot_id"]: claim["value"] for claim in normalized["validated_claims"]}
        dimensions = []
        for contract in required:
            slot_id, reference = contract["slot_id"], expected[contract["slot_id"]]
            present, candidate = final_valid and slot_id in values, values.get(slot_id)
            numeric = isinstance(reference, (int, float)) and not isinstance(reference, bool)
            text_comparison = None
            if numeric:
                exact = present and isinstance(candidate, (int, float)) and math.isclose(float(candidate), float(reference), rel_tol=0.0, abs_tol=0.0)
                numeric_total += 1
                numeric_exact += int(exact)
            else:
                text_comparison = compare_text_slot_v28(str(candidate), str(reference)) if present else {"literal_exact": False, "normalized_exact": False, "token_jaccard": 0.0, "candidate_original": None, "reference_original": reference, "semantic_rewrite_applied": False}
                exact = text_comparison["literal_exact"]
                literal_total += 1
                normalized_total += 1
                literal_exact += int(text_comparison["literal_exact"])
                normalized_exact += int(text_comparison["normalized_exact"])
            required_total += 1
            credited_total += int(present)
            exact_total += int(exact)
            dimensions.append({"slot_id": slot_id, "value_type": contract["value_type"], "candidate_present_in_valid_final_output": bool(present), "exact_value_match": bool(exact), "text_comparison_v28": text_comparison})
        task_scores[task_id] = {"stage_a_recorded_status": record["stage_a"], "stage_a_valid_for_scoring": stage_a_valid, "stage_b_status": stage_b_status, "final_pipeline_valid": final_valid, "recorded_failure_taxonomy": record.get("stage_a_failure_taxonomy"), "integrity_audit_failure_taxonomy": ({"category": "framework_validation_order_bug", "owner": "framework", "score_as_model_failure": False, "details": "v31 alias decoding and outer canonical handle audit passed, then a downstream adapter revalidated decoded canonical handles against the alias handle set"} if framework_failure else None), "required_slot_count": len(required), "credited_valid_slot_count": sum(x["candidate_present_in_valid_final_output"] for x in dimensions), "literal_or_numeric_exact_slot_count": sum(x["exact_value_match"] for x in dimensions), "dimensions": dimensions}
    summary = {"stage_a_recorded_passed_tasks": sum(records[t["task_id"]]["stage_a"] == "passed" for t in pack["tasks"]), "stage_a_total_tasks": len(task_scores), "final_pipeline_valid_tasks": sum(x["final_pipeline_valid"] for x in task_scores.values()), "final_pipeline_total_tasks": len(task_scores), "framework_failed_tasks": len(FRAMEWORK_FAILED), "model_behavior_failed_tasks": 0, "credited_valid_slots": credited_total, "required_slots": required_total, "literal_or_numeric_exact_slots": exact_total, "numeric_exact_slots": numeric_exact, "numeric_reference_slots": numeric_total, "text_literal_exact_slots": literal_exact, "text_literal_reference_slots": literal_total, "text_normalized_exact_slots": normalized_exact, "text_normalized_reference_slots": normalized_total, "verified_all_run_archives": verified_runs}
    payload = {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "dimension_scoring_completed_with_framework_integrity_failure", "reference_type": "simulated_expert_reference_not_independent_human_gold", "candidate_model": "qwen3.5:397b-cloud", "aggregate_score": None, "task_dimensions": task_scores, "summary_dimensions": summary, "protocol": {"framework_failed_outputs_receive_no_slot_credit": True, "framework_failure_not_attributed_to_candidate_model": True, "no_candidate_retry": True, "no_posthoc_semantic_repair": True, "failed_raw_outputs_preserved": True}, "inputs": {"progress": str(PROGRESS.relative_to(ROOT)), "progress_sha256": digest(PROGRESS), "task_pack": str(PACK.relative_to(ROOT)), "task_pack_sha256": digest(PACK), "slot_contracts": str(CONTRACTS.relative_to(ROOT)), "slot_contracts_sha256": digest(CONTRACTS), "atomic_gold": str(GOLD.relative_to(ROOT)), "atomic_gold_sha256": digest(GOLD)}}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
