from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from esg_reliable_discovery.archive import verify_run_checksums

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P15-V24-UNSEEN-LOCKBOX-V01"
PROGRESS = ROOT / "data/manifests/p15_candidate_progress_RESUME01.json"
PACK = ROOT / "data/tasks/p15_execution_task_pack_v0.1.lock.json"
CONTRACTS = ROOT / "configs/framework/p15_slot_contracts_v0.1.lock.json"
OUTPUT = ROOT / "data/results/p15_v24_dimension_scores_v0.1.lock.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tokens(value: object) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value).casefold()))


def text_jaccard(left: object, right: object) -> float:
    left_tokens, right_tokens = tokens(left), tokens(right)
    if not left_tokens and not right_tokens:
        return 1.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def same_value(left: object, right: object) -> bool:
    if isinstance(right, (int, float)) and not isinstance(right, bool):
        return isinstance(left, (int, float)) and math.isclose(
            float(left), float(right), rel_tol=1e-9, abs_tol=1e-9
        )
    return " ".join(str(left).casefold().split()) == " ".join(
        str(right).casefold().split()
    )


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing_to_overwrite:{OUTPUT}")
    progress = json.loads(PROGRESS.read_text())
    pack = json.loads(PACK.read_text())
    contracts = json.loads(CONTRACTS.read_text())["contracts"]
    indexed = {item["task_id"]: item for item in progress["records"]}
    task_scores: dict[str, Any] = {}
    verified_runs = 0
    verified_all_runs = 0
    exact_slots = 0
    numeric_exact = 0
    numeric_total = 0
    string_exact = 0
    string_total = 0
    credited_slots = 0
    required_slots = 0

    runs_root = ROOT / "research_archive" / EXPERIMENT / "runs"
    for run in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        verify_run_checksums(run)
        verified_all_runs += 1

    for task in pack["tasks"]:
        task_id = task["task_id"]
        record = indexed[task_id]
        reference_path = ROOT / task["reference_file"]
        reference = json.loads(reference_path.read_text())
        if reference["reference_status"] != "verified_against_frozen_pages":
            raise ValueError(f"unverified_reference:{task_id}")
        expected = reference["normalized_value"]
        required = contracts[task_id]
        required_slots += len(required)
        final_valid = record["stage_a"] == "passed" and record.get("stage_b") in {
            "passed",
            "not_required",
        }
        candidate_values: dict[str, object] = {}
        final_run: Path | None = None
        if record.get("stage_b") == "passed":
            final_run = Path(record["stage_b_result"]["archive_directory"])
            normalized = json.loads((final_run / "normalized_output.json").read_text())
            candidate_values = {
                claim["slot_id"]: claim["value"]
                for claim in normalized["validated_claims"]
            }
        elif record["stage_a"] == "passed" and record.get("stage_b") == "not_required":
            final_run = Path(record["stage_a_result"]["archive_directory"])
        if final_run is not None:
            verify_run_checksums(final_run)
            verified_runs += 1

        slot_dimensions = []
        for contract in required:
            slot_id = contract["slot_id"]
            reference_value = expected[slot_id]
            candidate_present = final_valid and slot_id in candidate_values
            candidate_value = candidate_values.get(slot_id)
            exact = candidate_present and same_value(candidate_value, reference_value)
            if isinstance(reference_value, (int, float)) and not isinstance(
                reference_value, bool
            ):
                numeric_total += 1
                numeric_exact += int(exact)
                overlap = None
            else:
                string_total += 1
                string_exact += int(exact)
                overlap = (
                    text_jaccard(candidate_value, reference_value)
                    if candidate_present
                    else 0.0
                )
            exact_slots += int(exact)
            credited_slots += int(candidate_present)
            slot_dimensions.append(
                {
                    "slot_id": slot_id,
                    "value_type": contract["value_type"],
                    "candidate_present_in_valid_final_output": candidate_present,
                    "exact_value_match": bool(exact),
                    "string_token_jaccard": overlap,
                }
            )
        task_scores[task_id] = {
            "stage_a_valid": record["stage_a"] == "passed",
            "stage_b_status": record.get("stage_b", "not_reached"),
            "final_pipeline_valid": final_valid,
            "failure_taxonomy": record.get("stage_b_failure_taxonomy")
            or record.get("stage_a_failure_taxonomy"),
            "required_slot_count": len(required),
            "credited_valid_slot_count": sum(
                item["candidate_present_in_valid_final_output"]
                for item in slot_dimensions
            ),
            "exact_slot_count": sum(
                item["exact_value_match"] for item in slot_dimensions
            ),
            "dimensions": slot_dimensions,
            "reference_path": str(reference_path.relative_to(ROOT)),
            "reference_sha256": digest(reference_path),
        }

    payload = {
        "schema_version": "2.4",
        "experiment_id": EXPERIMENT,
        "status": "dimension_scoring_completed_against_frozen_simulated_references",
        "reference_type": "simulated_expert_reference_not_independent_human_gold",
        "candidate_model": "qwen3.5:397b-cloud",
        "aggregate_score": None,
        "task_dimensions": task_scores,
        "summary_dimensions": {
            "stage_a_valid_tasks": sum(
                score["stage_a_valid"] for score in task_scores.values()
            ),
            "stage_a_total_tasks": len(task_scores),
            "final_pipeline_valid_tasks": sum(
                score["final_pipeline_valid"] for score in task_scores.values()
            ),
            "final_pipeline_total_tasks": len(task_scores),
            "credited_valid_slots": credited_slots,
            "required_slots": required_slots,
            "exact_slots": exact_slots,
            "numeric_exact_slots": numeric_exact,
            "numeric_reference_slots": numeric_total,
            "string_exact_slots": string_exact,
            "string_reference_slots": string_total,
            "verified_final_run_archives": verified_runs,
            "verified_all_run_archives": verified_all_runs,
        },
        "protocol": {
            "invalid_model_outputs_receive_no_slot_credit": True,
            "no_posthoc_semantic_repair": True,
            "no_silent_retry": True,
            "failed_raw_outputs_preserved": True,
        },
        "inputs": {
            "progress": str(PROGRESS.relative_to(ROOT)),
            "progress_sha256": digest(PROGRESS),
            "task_pack": str(PACK.relative_to(ROOT)),
            "task_pack_sha256": digest(PACK),
            "slot_contracts": str(CONTRACTS.relative_to(ROOT)),
            "slot_contracts_sha256": digest(CONTRACTS),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(payload["summary_dimensions"], sort_keys=True))


if __name__ == "__main__":
    main()
