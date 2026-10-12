from __future__ import annotations

import pytest

from esg_reliable_discovery.softwarex_comparative import (
    SLOTS,
    canonical_sha256,
    exact_mcnemar_two_sided,
    score_condition,
    score_paired_submission_v3,
    validate_paired_submission_v3,
    validate_submission,
)


def test_exact_mcnemar_two_sided_extreme_discordance() -> None:
    assert exact_mcnemar_two_sided(26, 0) == pytest.approx(2.9802322387695312e-08)
    assert exact_mcnemar_two_sided(23, 0) == pytest.approx(2.384185791015625e-07)
    assert exact_mcnemar_two_sided(0, 0) is None


def task_pack() -> dict:
    pack = {
        "benchmark_id": "test-benchmark",
        "tasks": [
            {"task_id": "T1", "report_index": 1, "stratum": "direct_claim"},
            {"task_id": "T2", "report_index": 2, "stratum": "abstention_audit"},
        ],
    }
    pack["self_sha256"] = canonical_sha256(pack)
    return pack


def output(task_id: str, support: str, action: str, slot: str = "Y") -> dict:
    return {
        "task_id": task_id,
        "execution_status": "completed",
        "support_label": support,
        "knowledge_base_action": action,
        "slots": {name: slot for name in SLOTS},
        "latency_ms": 10,
        "usage": {"input_tokens": 20, "output_tokens": 5, "estimated_cost_usd": 0.01},
        "raw_response_sha256": "0" * 64,
    }


def submission() -> dict:
    pack = task_pack()
    return {
        "schema_version": "1.1",
        "benchmark_id": "test-benchmark",
        "condition": "plain_model_verifier",
        "system_id": "test-system",
        "task_pack_sha256": pack["self_sha256"],
        "outputs": [
            output("T1", "fully_supported", "admit"),
            output("T2", "unsupported", "abstain_or_conflict", "NA"),
        ],
    }


def gold() -> dict:
    return {
        "tasks": [
            {
                "task_id": "T1",
                "final_support": "fully_supported",
                "final_action": "admit",
                "final_slots": {name: "Y" for name in SLOTS},
            },
            {
                "task_id": "T2",
                "final_support": "unsupported",
                "final_action": "abstain_or_conflict",
                "final_slots": {name: "NA" for name in SLOTS},
            },
        ]
    }


def test_submission_contract_requires_complete_unique_inventory() -> None:
    validated = validate_submission(submission(), task_pack())
    assert len(validated) == 2
    broken = submission()
    broken["outputs"] = [broken["outputs"][0], broken["outputs"][0]]
    with pytest.raises(ValueError, match="unique"):
        validate_submission(broken, task_pack())


def test_condition_scoring_uses_sealed_candidate_specific_gold() -> None:
    metrics = score_condition(submission(), task_pack(), gold(), repetitions=100)
    assert metrics["support"]["exact_accuracy"]["estimate"] == 1.0
    assert metrics["knowledge_base_action"]["exact_accuracy"]["estimate"] == 1.0
    assert metrics["applicable_slot_exactness"]["estimate"] == 1.0
    assert metrics["admission_control"]["precision"]["estimate"] == 1.0
    assert metrics["admission_control"]["recall"]["estimate"] == 1.0
    assert metrics["efficiency"]["total_input_tokens"] == 40
    assert metrics["efficiency"]["total_estimated_cost_usd"] == 0.02


def test_invalid_label_and_negative_latency_fail_closed() -> None:
    bad_label = submission()
    bad_label["outputs"][0]["support_label"] = "looks_good"
    with pytest.raises(ValueError, match="support_label"):
        validate_submission(bad_label, task_pack())
    bad_latency = submission()
    bad_latency["outputs"][0]["latency_ms"] = -1
    with pytest.raises(ValueError, match="latency_ms"):
        validate_submission(bad_latency, task_pack())


def test_model_behavior_failure_counts_as_wrong_without_semantic_repair() -> None:
    failed = submission()
    failed["outputs"][0] = {
        "task_id": "T1",
        "execution_status": "model_behavior_failure",
        "failure_code": "ModelBehaviorError",
        "latency_ms": None,
        "usage": {"input_tokens": 20, "output_tokens": 7, "estimated_cost_usd": None},
        "raw_response_sha256": "1" * 64,
    }
    metrics = score_condition(failed, task_pack(), gold(), repetitions=100)
    assert metrics["inventory"]["model_behavior_failures"] == 1
    assert metrics["support"]["exact_accuracy"]["estimate"] == 0.5
    assert metrics["knowledge_base_action"]["exact_accuracy"]["estimate"] == 0.5
    assert metrics["applicable_slot_exactness"]["estimate"] == 0.0


def test_validate_paired_submission_preserves_one_semantic_decision() -> None:
    pack = task_pack()
    pack["comparison_design"] = "single_candidate_paired_postprocessing"
    pack.pop("self_sha256")
    pack["self_sha256"] = canonical_sha256(pack)
    paired_outputs = []
    for base in submission()["outputs"]:
        decision = {
            "support_label": base["support_label"],
            "knowledge_base_action": base["knowledge_base_action"],
            "slots": base["slots"],
        }
        paired_outputs.append(
            {
                "task_id": base["task_id"],
                "execution_status": "completed",
                "ungated_decision": decision,
                "sustaintrace_full_decision": decision,
                "gate_audit": {
                    "input_action": decision["knowledge_base_action"],
                    "output_action": decision["knowledge_base_action"],
                },
                "latency_ms": base["latency_ms"],
                "usage": base["usage"],
                "raw_response_sha256": base["raw_response_sha256"],
            }
        )
    paired = {
        "schema_version": "1.0",
        "benchmark_id": pack["benchmark_id"],
        "comparison_design": "single_candidate_paired_postprocessing",
        "system_id": "test::paired-v3",
        "task_pack_sha256": pack["self_sha256"],
        "outputs": paired_outputs,
    }
    assert len(validate_paired_submission_v3(paired, pack)) == 2


def test_validate_paired_submission_rejects_semantic_rewrite() -> None:
    pack = task_pack()
    pack["comparison_design"] = "single_candidate_paired_postprocessing"
    pack.pop("self_sha256")
    pack["self_sha256"] = canonical_sha256(pack)
    base = output("T1", "fully_supported", "admit")
    second = output("T2", "unsupported", "abstain_or_conflict", "NA")
    outputs = []
    for item in (base, second):
        raw = {
            "support_label": item["support_label"],
            "knowledge_base_action": item["knowledge_base_action"],
            "slots": item["slots"],
        }
        full = {**raw, "slots": dict(raw["slots"])}
        outputs.append(
            {
                "task_id": item["task_id"],
                "execution_status": "completed",
                "ungated_decision": raw,
                "sustaintrace_full_decision": full,
                "gate_audit": {
                    "input_action": raw["knowledge_base_action"],
                    "output_action": full["knowledge_base_action"],
                },
                "latency_ms": item["latency_ms"],
                "usage": item["usage"],
                "raw_response_sha256": item["raw_response_sha256"],
            }
        )
    outputs[0]["sustaintrace_full_decision"]["slots"]["Unit"] = "N"
    paired = {
        "schema_version": "1.0",
        "benchmark_id": pack["benchmark_id"],
        "comparison_design": "single_candidate_paired_postprocessing",
        "system_id": "test::paired-v3",
        "task_pack_sha256": pack["self_sha256"],
        "outputs": outputs,
    }
    with pytest.raises(ValueError, match="rewrote semantic"):
        validate_paired_submission_v3(paired, pack)


def test_score_paired_submission_measures_prevention_and_retention() -> None:
    pack = task_pack()
    pack["comparison_design"] = "single_candidate_paired_postprocessing"
    pack.pop("self_sha256")
    pack["self_sha256"] = canonical_sha256(pack)

    def paired_output(task_id: str, full_action: str) -> dict:
        slots = {name: "Y" for name in SLOTS}
        raw = {
            "support_label": "fully_supported",
            "knowledge_base_action": "admit",
            "slots": slots,
        }
        full = {**raw, "knowledge_base_action": full_action, "slots": dict(slots)}
        return {
            "task_id": task_id,
            "execution_status": "completed",
            "ungated_decision": raw,
            "sustaintrace_full_decision": full,
            "gate_audit": {
                "outcome": (
                    "admission_preserved" if full_action == "admit" else "admission_blocked"
                ),
                "input_action": "admit",
                "output_action": full_action,
                "reason_codes": [] if full_action == "admit" else ["evidence_quote_is_grounded"],
            },
            "latency_ms": 10,
            "usage": {
                "input_tokens": 20,
                "output_tokens": 5,
                "estimated_cost_usd": None,
            },
            "raw_response_sha256": "2" * 64,
        }

    paired = {
        "schema_version": "1.0",
        "benchmark_id": pack["benchmark_id"],
        "comparison_design": "single_candidate_paired_postprocessing",
        "system_id": "test::paired-v3",
        "task_pack_sha256": pack["self_sha256"],
        "outputs": [paired_output("T1", "admit"), paired_output("T2", "reject")],
    }
    reference = {
        "tasks": [
            {"task_id": "T1", "admissible": True},
            {"task_id": "T2", "admissible": False},
        ]
    }
    metrics = score_paired_submission_v3(
        paired, pack, reference, repetitions=100
    )
    assert metrics["unsafe_admission_rate"]["ungated"]["estimate"] == 1.0
    assert metrics["unsafe_admission_rate"]["sustaintrace_full"]["estimate"] == 0.0
    assert metrics["paired_safety_effect"]["unsafe_admissions_prevented"] == 1
    assert metrics["paired_safety_effect"]["absolute_risk_reduction"][
        "estimate"
    ] == 1.0
    assert metrics["paired_safety_effect"]["exact_mcnemar_two_sided_p"] == 1.0
    assert metrics["safe_admission"]["retention_among_ungated_admissions"][
        "estimate"
    ] == 1.0
    assert metrics["safe_admission"]["absolute_rate_change_ungated_minus_full"][
        "estimate"
    ] == 0.0
    assert metrics["efficiency"]["model_calls"] == 2
    assert metrics["efficiency"]["derived_condition_outputs"] == 4
