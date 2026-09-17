# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from esg_reliable_discovery.archive import verify_run_checksums
from esg_reliable_discovery.v28_integrity import compare_text_slot_v28

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P23-V32-UNSEEN-LOCKBOX-V01"
PROGRESS = ROOT / "data/manifests/p23_candidate_progress.json"
PACK = ROOT / "data/tasks/p23_local_execution_task_pack_v0.1.lock.json"
CONTRACTS = ROOT / "configs/framework/p23_slot_contracts_v0.1.lock.json"
GOLD = ROOT / "data/annotations/p23_simulated/p23_atomic_slot_gold_v0.1.lock.json"
OUTPUT = ROOT / "data/results/p23_v32_dimension_scores_v0.1.lock.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def projected_values(record: dict[str, object], requires_stage_b: bool) -> dict[str, object]:
    if requires_stage_b:
        run = Path(record["stage_b_result"]["archive_directory"])
        normalized = json.loads((run / "normalized_output.json").read_text())
        claims = normalized["validated_claims"]
    else:
        run = Path(record["stage_a_result"]["archive_directory"])
        normalized = json.loads((run / "normalized_output.json").read_text())
        claims = normalized.get("v31_calculation_slot_projection", {}).get("validated_claims", [])
    return {claim["slot_id"]: claim["value"] for claim in claims}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
    records = {item["task_id"]: item for item in progress["records"]}
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    contracts = json.loads(CONTRACTS.read_text(encoding="utf-8"))["contracts"]
    gold = json.loads(GOLD.read_text(encoding="utf-8"))["values"]
    runs_root = ROOT / "research_archive" / EXPERIMENT / "runs"
    runs = sorted(path for path in runs_root.iterdir() if path.is_dir())
    for run in runs:
        verify_run_checksums(run)

    task_scores: dict[str, object] = {}
    exact_total = credited_total = required_total = 0
    literal_total = normalized_total = numeric_total = 0
    literal_exact = normalized_exact = numeric_exact = 0
    for task in pack["tasks"]:
        task_id = task["task_id"]
        record, required, expected = records[task_id], contracts[task_id], gold[task_id]
        stage_a_valid = record["stage_a"] == "passed"
        requires_stage_b = task["task_type"] != "deterministic_calculation"
        stage_b_status = record.get("stage_b", "not_reached")
        final_valid = stage_a_valid and (stage_b_status == "passed" if requires_stage_b else True)
        values = projected_values(record, requires_stage_b) if final_valid else {}
        dimensions = []
        for contract in required:
            slot_id, reference = contract["slot_id"], expected[contract["slot_id"]]
            present, candidate = slot_id in values, values.get(slot_id)
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
        failure = record.get("stage_b_failure_taxonomy") or record.get("stage_a_failure_taxonomy")
        task_scores[task_id] = {"stage_a_valid": stage_a_valid, "stage_b_status": stage_b_status, "final_pipeline_valid": final_valid, "failure_taxonomy": failure, "required_slot_count": len(required), "credited_valid_slot_count": sum(x["candidate_present_in_valid_final_output"] for x in dimensions), "literal_or_numeric_exact_slot_count": sum(x["exact_value_match"] for x in dimensions), "dimensions": dimensions}

    summary = {"stage_a_valid_tasks": sum(x["stage_a_valid"] for x in task_scores.values()), "stage_a_total_tasks": len(task_scores), "final_pipeline_valid_tasks": sum(x["final_pipeline_valid"] for x in task_scores.values()), "final_pipeline_total_tasks": len(task_scores), "framework_failed_tasks": sum((x["failure_taxonomy"] or {}).get("owner") == "framework" for x in task_scores.values()), "model_behavior_failed_tasks": sum((x["failure_taxonomy"] or {}).get("owner") == "candidate_model" for x in task_scores.values()), "credited_valid_slots": credited_total, "required_slots": required_total, "literal_or_numeric_exact_slots": exact_total, "numeric_exact_slots": numeric_exact, "numeric_reference_slots": numeric_total, "text_literal_exact_slots": literal_exact, "text_literal_reference_slots": literal_total, "text_normalized_exact_slots": normalized_exact, "text_normalized_reference_slots": normalized_total, "verified_all_run_archives": len(runs)}
    payload = {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "dimension_scoring_completed_with_framework_and_model_failures", "reference_type": "simulated_expert_reference_not_independent_human_gold", "candidate_model": "qwen3.5:397b-cloud", "aggregate_score": None, "task_dimensions": task_scores, "summary_dimensions": summary, "protocol": {"invalid_or_framework_blocked_outputs_receive_no_slot_credit": True, "partial_projection_credit_allowed": True, "calculation_tasks_credit_only_frozen_deterministic_slot_projection": True, "framework_failure_not_attributed_to_candidate_model": True, "no_candidate_retry": True, "no_posthoc_semantic_repair": True, "failed_raw_outputs_preserved": True}, "inputs": {"progress": str(PROGRESS.relative_to(ROOT)), "progress_sha256": digest(PROGRESS), "task_pack": str(PACK.relative_to(ROOT)), "task_pack_sha256": digest(PACK), "slot_contracts": str(CONTRACTS.relative_to(ROOT)), "slot_contracts_sha256": digest(CONTRACTS), "atomic_gold": str(GOLD.relative_to(ROOT)), "atomic_gold_sha256": digest(GOLD)}}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
