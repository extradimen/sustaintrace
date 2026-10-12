from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from collections.abc import Callable, Iterable
from math import comb
from pathlib import Path

SUPPORT_LABELS = {
    "fully_supported",
    "partially_supported",
    "unsupported",
    "cannot_assess",
    "source_defect",
}
ACTION_LABELS = {"admit", "correct_then_review", "reject", "abstain_or_conflict"}
SLOT_LABELS = {"Y", "N", "NA"}
SLOTS = (
    "Subject",
    "Predicate",
    "Value",
    "Period",
    "Unit",
    "Boundary/method",
    "Evidence coordinates",
)
CONDITIONS = {
    "plain_model_verifier",
    "ungated_pipeline_verifier",
    "sustaintrace_full",
}
COMPLETED_OUTPUT_KEYS = {
    "task_id",
    "execution_status",
    "support_label",
    "knowledge_base_action",
    "slots",
    "latency_ms",
    "usage",
    "raw_response_sha256",
}
FAILED_OUTPUT_KEYS = {
    "task_id",
    "execution_status",
    "failure_code",
    "latency_ms",
    "usage",
    "raw_response_sha256",
}
PAIRED_COMPLETED_OUTPUT_KEYS = {
    "task_id",
    "execution_status",
    "ungated_decision",
    "sustaintrace_full_decision",
    "gate_audit",
    "latency_ms",
    "usage",
    "raw_response_sha256",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def clustered_ratio(
    records: list[dict],
    scorer: Callable[[dict], tuple[int, int]],
    *,
    seed: int = 20261009,
    repetitions: int = 10_000,
) -> dict:
    reports = sorted({record["report_index"] for record in records})
    numerator = denominator = 0
    for record in records:
        add_numerator, add_denominator = scorer(record)
        numerator += add_numerator
        denominator += add_denominator
    estimate = numerator / denominator if denominator else None
    by_report = {
        report: [record for record in records if record["report_index"] == report]
        for report in reports
    }
    rng = random.Random(seed)
    bootstrap: list[float] = []
    for _ in range(repetitions):
        sampled_reports = rng.choices(reports, k=len(reports))
        sampled_numerator = sampled_denominator = 0
        for report in sampled_reports:
            for record in by_report[report]:
                add_numerator, add_denominator = scorer(record)
                sampled_numerator += add_numerator
                sampled_denominator += add_denominator
        if sampled_denominator:
            bootstrap.append(sampled_numerator / sampled_denominator)
    return {
        "numerator": numerator,
        "denominator": denominator,
        "estimate": round(estimate, 6) if estimate is not None else None,
        "report_clustered_bootstrap_95_ci": [
            round(percentile(bootstrap, 0.025), 6),
            round(percentile(bootstrap, 0.975), 6),
        ]
        if bootstrap
        else None,
        "bootstrap_repetitions": repetitions,
        "bootstrap_seed": seed,
    }


def clustered_paired_binary_difference(
    records: list[dict],
    scorer: Callable[[dict], tuple[int, int]],
    *,
    seed: int = 20261009,
    repetitions: int = 10_000,
) -> dict:
    """Estimate a paired binary-rate difference with report-cluster bootstrap CIs."""
    if not records:
        return {
            "sum_of_paired_differences": 0,
            "denominator": 0,
            "estimate": None,
            "report_clustered_bootstrap_95_ci": None,
            "bootstrap_repetitions": repetitions,
            "bootstrap_seed": seed,
        }
    reports = sorted({record["report_index"] for record in records})
    differences = []
    for record in records:
        first, second = scorer(record)
        differences.append(first - second)
    estimate = sum(differences) / len(differences)
    by_report = {
        report: [record for record in records if record["report_index"] == report]
        for report in reports
    }
    rng = random.Random(seed)
    bootstrap: list[float] = []
    for _ in range(repetitions):
        sampled_reports = rng.choices(reports, k=len(reports))
        sampled_differences: list[int] = []
        for report in sampled_reports:
            for record in by_report[report]:
                first, second = scorer(record)
                sampled_differences.append(first - second)
        if sampled_differences:
            bootstrap.append(sum(sampled_differences) / len(sampled_differences))
    return {
        "sum_of_paired_differences": sum(differences),
        "denominator": len(differences),
        "estimate": round(estimate, 6),
        "report_clustered_bootstrap_95_ci": [
            round(percentile(bootstrap, 0.025), 6),
            round(percentile(bootstrap, 0.975), 6),
        ],
        "bootstrap_repetitions": repetitions,
        "bootstrap_seed": seed,
    }


def exact_mcnemar_two_sided(discordant_b: int, discordant_c: int) -> float | None:
    """Return the exact two-sided McNemar/binomial p-value for paired outcomes."""
    discordant = discordant_b + discordant_c
    if discordant == 0:
        return None
    tail = sum(comb(discordant, k) for k in range(min(discordant_b, discordant_c) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def _validate_choice(value: object, allowed: set[str], field: str, task_id: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{task_id}: invalid {field}: {value!r}")
    return value


def validate_submission(submission: dict, task_pack: dict) -> list[dict]:
    canonical_task_pack = dict(task_pack)
    declared_task_pack_sha256 = canonical_task_pack.pop("self_sha256", None)
    if declared_task_pack_sha256 != canonical_sha256(canonical_task_pack):
        raise ValueError("Frozen task pack self_sha256 is invalid")
    if submission.get("schema_version") != "1.1":
        raise ValueError("Submission schema_version must be 1.1")
    if submission.get("benchmark_id") != task_pack.get("benchmark_id"):
        raise ValueError("Submission benchmark_id does not match the task pack")
    condition = submission.get("condition")
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown comparison condition: {condition!r}")
    if submission.get("task_pack_sha256") != task_pack.get("self_sha256"):
        raise ValueError("Submission task_pack_sha256 does not match the frozen task pack")

    expected = {task["task_id"] for task in task_pack["tasks"]}
    outputs = submission.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError("Submission outputs must be a list")
    received = [output.get("task_id") for output in outputs if isinstance(output, dict)]
    if len(received) != len(outputs) or len(received) != len(set(received)):
        raise ValueError("Submission task IDs must be present and unique")
    if set(received) != expected:
        missing = sorted(expected - set(received))
        extra = sorted(set(received) - expected)
        raise ValueError(f"Submission task inventory mismatch; missing={missing}, extra={extra}")

    validated = []
    for output in outputs:
        task_id = output["task_id"]
        execution_status = output.get("execution_status")
        expected_keys = (
            COMPLETED_OUTPUT_KEYS
            if execution_status == "completed"
            else FAILED_OUTPUT_KEYS
            if execution_status == "model_behavior_failure"
            else set()
        )
        if not expected_keys or set(output) != expected_keys:
            unexpected = sorted(set(output) - expected_keys)
            missing = sorted(expected_keys - set(output))
            raise ValueError(
                f"{task_id}: output fields must match the {execution_status!r} contract; "
                f"missing={missing}, unexpected={unexpected}"
            )
        latency_ms = output.get("latency_ms")
        if latency_ms is not None and (
            not isinstance(latency_ms, (int, float)) or latency_ms < 0
        ):
            raise ValueError(f"{task_id}: latency_ms must be null or non-negative")
        if execution_status == "completed" and latency_ms is None:
            raise ValueError(f"{task_id}: completed output requires latency_ms")
        usage = output.get("usage", {})
        if not isinstance(usage, dict):
            raise ValueError(f"{task_id}: usage must be an object")
        if set(usage) != {"input_tokens", "output_tokens", "estimated_cost_usd"}:
            raise ValueError(f"{task_id}: usage fields must match the frozen contract")
        for key in ("input_tokens", "output_tokens"):
            value = usage.get(key)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{task_id}: usage.{key} must be a non-negative integer")
        estimated_cost = usage.get("estimated_cost_usd")
        if estimated_cost is not None and (
            not isinstance(estimated_cost, (int, float)) or estimated_cost < 0
        ):
            raise ValueError(f"{task_id}: estimated_cost_usd must be null or non-negative")
        raw_response_sha256 = output.get("raw_response_sha256")
        if not isinstance(raw_response_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", raw_response_sha256
        ):
            raise ValueError(f"{task_id}: raw_response_sha256 must be lowercase SHA256")
        if execution_status == "model_behavior_failure":
            if not isinstance(output.get("failure_code"), str) or not output["failure_code"]:
                raise ValueError(f"{task_id}: model failure requires failure_code")
            validated.append(dict(output))
            continue
        slots = output.get("slots")
        if not isinstance(slots, dict) or set(slots) != set(SLOTS):
            raise ValueError(f"{task_id}: slots must contain exactly {list(SLOTS)}")
        normalized_slots = {
            slot: _validate_choice(slots[slot], SLOT_LABELS, f"slot {slot}", task_id)
            for slot in SLOTS
        }
        validated.append(
            {
                **output,
                "support_label": _validate_choice(
                    output.get("support_label"), SUPPORT_LABELS, "support_label", task_id
                ),
                "knowledge_base_action": _validate_choice(
                    output.get("knowledge_base_action"),
                    ACTION_LABELS,
                    "knowledge_base_action",
                    task_id,
                ),
                "slots": normalized_slots,
            }
        )
    return validated


def validate_paired_submission_v3(submission: dict, task_pack: dict) -> list[dict]:
    """Validate a single-candidate paired post-processing submission."""
    canonical_task_pack = dict(task_pack)
    declared_task_pack_sha256 = canonical_task_pack.pop("self_sha256", None)
    if declared_task_pack_sha256 != canonical_sha256(canonical_task_pack):
        raise ValueError("Frozen task pack self_sha256 is invalid")
    if submission.get("schema_version") != "1.0":
        raise ValueError("Paired submission schema_version must be 1.0")
    if submission.get("benchmark_id") != task_pack.get("benchmark_id"):
        raise ValueError("Paired submission benchmark_id does not match the task pack")
    if submission.get("comparison_design") != "single_candidate_paired_postprocessing":
        raise ValueError("Paired submission has the wrong comparison design")
    if submission.get("task_pack_sha256") != task_pack.get("self_sha256"):
        raise ValueError("Paired submission task_pack_sha256 does not match")

    expected = {task["task_id"] for task in task_pack["tasks"]}
    outputs = submission.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError("Paired submission outputs must be a list")
    received = [output.get("task_id") for output in outputs if isinstance(output, dict)]
    if len(received) != len(outputs) or len(received) != len(set(received)):
        raise ValueError("Paired submission task IDs must be present and unique")
    if set(received) != expected:
        raise ValueError("Paired submission task inventory mismatch")

    def validate_decision(value: object, task_id: str, field: str) -> dict:
        if not isinstance(value, dict) or set(value) != {
            "support_label",
            "knowledge_base_action",
            "slots",
        }:
            raise ValueError(f"{task_id}: invalid {field} shape")
        slots = value.get("slots")
        if not isinstance(slots, dict) or set(slots) != set(SLOTS):
            raise ValueError(f"{task_id}: invalid {field}.slots")
        return {
            "support_label": _validate_choice(
                value.get("support_label"), SUPPORT_LABELS, f"{field}.support_label", task_id
            ),
            "knowledge_base_action": _validate_choice(
                value.get("knowledge_base_action"),
                ACTION_LABELS,
                f"{field}.knowledge_base_action",
                task_id,
            ),
            "slots": {
                slot: _validate_choice(
                    slots[slot], SLOT_LABELS, f"{field}.slots.{slot}", task_id
                )
                for slot in SLOTS
            },
        }

    validated = []
    for output in outputs:
        task_id = output["task_id"]
        if output.get("execution_status") == "model_behavior_failure":
            if set(output) != FAILED_OUTPUT_KEYS:
                raise ValueError(f"{task_id}: invalid paired failure fields")
            validated.append(dict(output))
            continue
        if output.get("execution_status") != "completed":
            raise ValueError(f"{task_id}: invalid paired execution_status")
        if set(output) != PAIRED_COMPLETED_OUTPUT_KEYS:
            raise ValueError(f"{task_id}: invalid paired completed fields")
        ungated = validate_decision(output["ungated_decision"], task_id, "ungated")
        full = validate_decision(
            output["sustaintrace_full_decision"], task_id, "sustaintrace_full"
        )
        if (
            ungated["support_label"] != full["support_label"]
            or ungated["slots"] != full["slots"]
        ):
            raise ValueError(f"{task_id}: full path rewrote semantic judgements")
        audit = output.get("gate_audit")
        if (
            not isinstance(audit, dict)
            or audit.get("input_action") != ungated["knowledge_base_action"]
            or audit.get("output_action") != full["knowledge_base_action"]
        ):
            raise ValueError(f"{task_id}: gate audit does not bind paired actions")
        raw_response_sha256 = output.get("raw_response_sha256")
        if not isinstance(raw_response_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", raw_response_sha256
        ):
            raise ValueError(f"{task_id}: invalid raw_response_sha256")
        validated.append(
            {
                **output,
                "ungated_decision": ungated,
                "sustaintrace_full_decision": full,
            }
        )
    return validated


def _macro_f1(gold: Iterable[str], predicted: Iterable[str], labels: set[str]) -> float:
    gold_values = list(gold)
    predicted_values = list(predicted)
    scores = []
    for label in sorted(labels):
        true_positive = sum(
            expected == label and actual == label
            for expected, actual in zip(gold_values, predicted_values, strict=True)
        )
        false_positive = sum(
            expected != label and actual == label
            for expected, actual in zip(gold_values, predicted_values, strict=True)
        )
        false_negative = sum(
            expected == label and actual != label
            for expected, actual in zip(gold_values, predicted_values, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(2 * true_positive / denominator if denominator else 0.0)
    return round(sum(scores) / len(scores), 6)


def _distribution(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def score_condition(
    submission: dict,
    task_pack: dict,
    gold: dict,
    *,
    seed: int = 20261009,
    repetitions: int = 10_000,
) -> dict:
    outputs = validate_submission(submission, task_pack)
    tasks = {task["task_id"]: task for task in task_pack["tasks"]}
    gold_tasks = {task["task_id"]: task for task in gold["tasks"]}
    if set(tasks) != set(gold_tasks):
        raise ValueError("Gold task inventory does not match the task pack")

    records = []
    for output in outputs:
        task_id = output["task_id"]
        records.append(
            {
                "task_id": task_id,
                "report_index": tasks[task_id]["report_index"],
                "stratum": tasks[task_id]["stratum"],
                "output": output,
                "gold": gold_tasks[task_id],
            }
        )

    def predicted_support(record: dict) -> str:
        return record["output"].get("support_label", "__model_behavior_failure__")

    def predicted_action(record: dict) -> str:
        return record["output"].get(
            "knowledge_base_action", "__model_behavior_failure__"
        )

    candidate_records = [r for r in records if r["stratum"] != "abstention_audit"]
    support_accuracy = clustered_ratio(
        records,
        lambda r: (int(predicted_support(r) == r["gold"]["final_support"]), 1),
        seed=seed,
        repetitions=repetitions,
    )
    action_accuracy = clustered_ratio(
        records,
        lambda r: (
            int(predicted_action(r) == r["gold"]["final_action"]),
            1,
        ),
        seed=seed,
        repetitions=repetitions,
    )
    applicable_slot_exactness = clustered_ratio(
        candidate_records,
        lambda r: (
            sum(
                r["output"].get("slots", {}).get(slot) == r["gold"]["final_slots"][slot]
                for slot in SLOTS
                if r["gold"]["final_slots"][slot] != "NA"
            ),
            sum(r["gold"]["final_slots"][slot] != "NA" for slot in SLOTS),
        ),
        seed=seed,
        repetitions=repetitions,
    )

    predicted_admissions = [
        r for r in records if predicted_action(r) == "admit"
    ]
    human_admissible = [r for r in records if r["gold"]["final_action"] == "admit"]
    admission_precision = clustered_ratio(
        predicted_admissions,
        lambda r: (int(r["gold"]["final_action"] == "admit"), 1),
        seed=seed,
        repetitions=repetitions,
    ) if predicted_admissions else {
        "numerator": 0,
        "denominator": 0,
        "estimate": None,
        "report_clustered_bootstrap_95_ci": None,
        "bootstrap_repetitions": repetitions,
        "bootstrap_seed": seed,
    }
    admission_recall = clustered_ratio(
        human_admissible,
        lambda r: (int(predicted_action(r) == "admit"), 1),
        seed=seed,
        repetitions=repetitions,
    )
    unsafe_admission = clustered_ratio(
        predicted_admissions,
        lambda r: (
            int(
                r["gold"]["final_support"]
                in {"unsupported", "cannot_assess", "source_defect"}
            ),
            1,
        ),
        seed=seed,
        repetitions=repetitions,
    ) if predicted_admissions else {
        "numerator": 0,
        "denominator": 0,
        "estimate": None,
        "report_clustered_bootstrap_95_ci": None,
        "bootstrap_repetitions": repetitions,
        "bootstrap_seed": seed,
    }

    latencies = [
        float(r["output"]["latency_ms"])
        for r in records
        if r["output"]["latency_ms"] is not None
    ]
    costs = [r["output"]["usage"].get("estimated_cost_usd") for r in records]
    known_costs = [float(value) for value in costs if value is not None]
    return {
        "condition": submission["condition"],
        "system_id": submission["system_id"],
        "submission_sha256": submission.get("self_sha256"),
        "inventory": {
            "reports": len({record["report_index"] for record in records}),
            "tasks": len(records),
            "candidate_tasks": len(candidate_records),
            "abstention_tasks": len(records) - len(candidate_records),
            "completed_outputs": sum(
                r["output"]["execution_status"] == "completed" for r in records
            ),
            "model_behavior_failures": sum(
                r["output"]["execution_status"] == "model_behavior_failure"
                for r in records
            ),
        },
        "support": {
            "exact_accuracy": support_accuracy,
            "macro_f1": _macro_f1(
                (r["gold"]["final_support"] for r in records),
                (predicted_support(r) for r in records),
                SUPPORT_LABELS,
            ),
            "predicted_distribution": _distribution(
                predicted_support(r) for r in records
            ),
        },
        "knowledge_base_action": {
            "exact_accuracy": action_accuracy,
            "macro_f1": _macro_f1(
                (r["gold"]["final_action"] for r in records),
                (predicted_action(r) for r in records),
                ACTION_LABELS,
            ),
            "predicted_distribution": _distribution(
                predicted_action(r) for r in records
            ),
        },
        "applicable_slot_exactness": applicable_slot_exactness,
        "admission_control": {
            "predicted_admissions": len(predicted_admissions),
            "human_admissible": len(human_admissible),
            "precision": admission_precision,
            "recall": admission_recall,
            "unsafe_admission_rate": unsafe_admission,
        },
        "efficiency": {
            "total_latency_ms": round(sum(latencies), 3),
            "known_latency_tasks": len(latencies),
            "median_latency_ms": round(percentile(latencies, 0.5), 3) if latencies else None,
            "p95_latency_ms": round(percentile(latencies, 0.95), 3) if latencies else None,
            "total_input_tokens": sum(r["output"]["usage"]["input_tokens"] for r in records),
            "total_output_tokens": sum(r["output"]["usage"]["output_tokens"] for r in records),
            "known_cost_tasks": len(known_costs),
            "total_estimated_cost_usd": round(sum(known_costs), 6)
            if known_costs
            else None,
        },
    }


def score_paired_submission_v3(
    submission: dict,
    task_pack: dict,
    reference: dict,
    *,
    seed: int = 20261009,
    repetitions: int = 10_000,
) -> dict:
    """Score admission-control effects on identical frozen model candidates."""
    outputs = validate_paired_submission_v3(submission, task_pack)
    tasks = {task["task_id"]: task for task in task_pack["tasks"]}
    reference_tasks = {task["task_id"]: task for task in reference["tasks"]}
    if set(tasks) != set(reference_tasks):
        raise ValueError("Paired reference task inventory does not match the task pack")
    if any(not isinstance(task.get("admissible"), bool) for task in reference_tasks.values()):
        raise ValueError("Every paired reference task requires boolean admissible")

    records = [
        {
            "task_id": output["task_id"],
            "report_index": tasks[output["task_id"]]["report_index"],
            "output": output,
            "admissible": reference_tasks[output["task_id"]]["admissible"],
        }
        for output in outputs
    ]
    completed = [
        record
        for record in records
        if record["output"]["execution_status"] == "completed"
    ]
    nonadmissible = [record for record in completed if not record["admissible"]]
    admissible = [record for record in completed if record["admissible"]]

    def action(record: dict, path: str) -> str:
        return record["output"][path]["knowledge_base_action"]

    def ratio(records_subset: list[dict], scorer: Callable[[dict], tuple[int, int]]) -> dict:
        if not records_subset:
            return {
                "numerator": 0,
                "denominator": 0,
                "estimate": None,
                "report_clustered_bootstrap_95_ci": None,
                "bootstrap_repetitions": repetitions,
                "bootstrap_seed": seed,
            }
        return clustered_ratio(
            records_subset, scorer, seed=seed, repetitions=repetitions
        )

    unsafe_prevented = sum(
        action(record, "ungated_decision") == "admit"
        and action(record, "sustaintrace_full_decision") != "admit"
        for record in nonadmissible
    )
    unsafe_introduced = sum(
        action(record, "ungated_decision") != "admit"
        and action(record, "sustaintrace_full_decision") == "admit"
        for record in nonadmissible
    )
    gate_activations = [
        record
        for record in completed
        if record["output"]["gate_audit"]["outcome"] == "admission_blocked"
    ]
    reason_counts = Counter(
        reason
        for record in gate_activations
        for reason in record["output"]["gate_audit"].get("reason_codes", [])
    )
    return {
        "comparison_design": "single_candidate_paired_postprocessing",
        "inventory": {
            "reports": len({record["report_index"] for record in records}),
            "tasks": len(records),
            "completed_outputs": len(completed),
            "model_behavior_failures": len(records) - len(completed),
            "reference_admissible": len(admissible),
            "reference_nonadmissible": len(nonadmissible),
        },
        "machine_contract_completion_rate": ratio(
            records,
            lambda record: (
                int(record["output"]["execution_status"] == "completed"),
                1,
            ),
        ),
        "unsafe_admission_rate": {
            "ungated": ratio(
                nonadmissible,
                lambda record: (int(action(record, "ungated_decision") == "admit"), 1),
            ),
            "sustaintrace_full": ratio(
                nonadmissible,
                lambda record: (
                    int(action(record, "sustaintrace_full_decision") == "admit"),
                    1,
                ),
            ),
        },
        "paired_safety_effect": {
            "unsafe_admissions_prevented": unsafe_prevented,
            "unsafe_admissions_introduced": unsafe_introduced,
            "discordant_pairs": unsafe_prevented + unsafe_introduced,
            "absolute_risk_reduction": clustered_paired_binary_difference(
                nonadmissible,
                lambda record: (
                    int(action(record, "ungated_decision") == "admit"),
                    int(action(record, "sustaintrace_full_decision") == "admit"),
                ),
                seed=seed,
                repetitions=repetitions,
            ),
            "exact_mcnemar_two_sided_p": exact_mcnemar_two_sided(
                unsafe_prevented, unsafe_introduced
            ),
        },
        "safe_admission": {
            "ungated_rate": ratio(
                admissible,
                lambda record: (int(action(record, "ungated_decision") == "admit"), 1),
            ),
            "full_rate": ratio(
                admissible,
                lambda record: (
                    int(action(record, "sustaintrace_full_decision") == "admit"),
                    1,
                ),
            ),
            "retention_among_ungated_admissions": ratio(
                [
                    record
                    for record in admissible
                    if action(record, "ungated_decision") == "admit"
                ],
                lambda record: (
                    int(action(record, "sustaintrace_full_decision") == "admit"),
                    1,
                ),
            ),
            "absolute_rate_change_ungated_minus_full": clustered_paired_binary_difference(
                admissible,
                lambda record: (
                    int(action(record, "ungated_decision") == "admit"),
                    int(action(record, "sustaintrace_full_decision") == "admit"),
                ),
                seed=seed,
                repetitions=repetitions,
            ),
        },
        "gate": {
            "activation_rate": ratio(
                completed,
                lambda record: (
                    int(record["output"]["gate_audit"]["outcome"] == "admission_blocked"),
                    1,
                ),
            ),
            "reason_code_counts": dict(sorted(reason_counts.items())),
        },
        "efficiency": {
            "model_calls": len(records),
            "derived_condition_outputs": len(completed) * 2,
            "total_input_tokens": sum(
                record["output"]["usage"]["input_tokens"] for record in records
            ),
            "total_output_tokens": sum(
                record["output"]["usage"]["output_tokens"] for record in records
            ),
        },
    }
