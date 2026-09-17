from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


def _canonical_text(value: Any) -> str | None:
    if value is None:
        return None
    return " ".join(re.findall(r"[a-z0-9.%]+", str(value).lower()))


def _numeric_match(candidate: Any, reference: Any, tolerance: float) -> bool | None:
    if candidate is None or reference is None:
        return candidate is reference
    def coerce(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.fullmatch(r"\s*([-+]?\d[\d,]*(?:\.\d+)?)\s*%?\s*", value)
            if match:
                return float(match.group(1).replace(",", ""))
        return None

    candidate_number = coerce(candidate)
    reference_number = coerce(reference)
    if candidate_number is None or reference_number is None:
        return None
    return math.isclose(
        candidate_number, reference_number, rel_tol=tolerance, abs_tol=tolerance
    )


def _text_overlap(candidate: Any, reference: Any) -> float | None:
    left = _canonical_text(candidate)
    right = _canonical_text(reference)
    if left is None or right is None:
        return 1.0 if left == right else 0.0
    left_tokens, right_tokens = set(left.split()), set(right.split())
    if not left_tokens and not right_tokens:
        return 1.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def score_candidate_against_synthetic_reference(
    candidate: dict[str, Any], reference: dict[str, Any], *, numeric_tolerance: float = 1e-6
) -> dict[str, Any]:
    """Return dimension-wise diagnostics; deliberately produces no aggregate score."""
    if reference.get("reference_status") != "verified":
        raise ValueError("Scoring requires a verified synthetic reference")
    status_match = candidate.get("answer_status") == reference.get("answer_status")
    is_abstention = reference["answer_status"] == "insufficient_information"
    is_conflict = reference["answer_status"] == "conflict"
    has_single_value_target = not is_abstention and not is_conflict
    numeric_match = (
        None
        if not has_single_value_target
        else _numeric_match(
            candidate.get("normalized_value"),
            reference.get("normalized_value"),
            numeric_tolerance,
        )
    )
    reference_evidence = {
        (item["document_id"], item["pdf_page"]) for item in reference.get("evidence", [])
    }
    if intervention_id := reference.get("controlled_intervention_id"):
        reference_evidence.add((intervention_id, 1))
    candidate_evidence = {
        (item["source_id"], item["page"]) for item in candidate.get("evidence", [])
    }
    evidence_recall = (
        len(reference_evidence & candidate_evidence) / len(reference_evidence)
        if reference_evidence
        else (1.0 if not candidate_evidence else 0.0)
    )
    evidence_precision = (
        len(reference_evidence & candidate_evidence) / len(candidate_evidence)
        if candidate_evidence
        else (1.0 if not reference_evidence else 0.0)
    )
    abstention_correct = None
    if reference["answer_status"] == "insufficient_information":
        abstention_correct = (
            candidate.get("answer_status") == "insufficient_information"
            and candidate.get("answer") is None
            and candidate.get("normalized_value") is None
        )
    conflict_correct = None
    if reference["answer_status"] == "conflict":
        conflict_correct = candidate.get("answer_status") == "conflict"
    return {
        "schema_version": "1.0",
        "task_id": reference["task_id"],
        "reference_type": "ai_simulated_synthetic_reference",
        "human_gold_standard": False,
        "dimensions": {
            "answer_status_exact": status_match,
            "normalized_value_match": numeric_match,
            "normalized_unit_exact": (
                None
                if not has_single_value_target
                else _canonical_text(candidate.get("normalized_unit"))
                == _canonical_text(reference.get("normalized_unit"))
            ),
            "subject_token_jaccard": _text_overlap(
                candidate.get("subject"), reference.get("subject")
            ),
            "scope_boundary_token_jaccard": _text_overlap(
                candidate.get("scope_boundary"), reference.get("scope_boundary")
            ),
            "period_token_jaccard": _text_overlap(
                candidate.get("period"), reference.get("period")
            ),
            "evidence_locator_precision": evidence_precision,
            "evidence_locator_recall": evidence_recall,
            "abstention_correct": abstention_correct,
            "conflict_detection_correct": conflict_correct,
        },
        "aggregate_score": None,
        "selection_eligible": status_match and numeric_match is not False,
    }


def score_archived_run(run_directory: str | Path, reference_path: str | Path) -> dict[str, Any]:
    run_directory = Path(run_directory)
    validation = json.loads((run_directory / "validation.json").read_text(encoding="utf-8"))
    if validation.get("status") != "passed":
        raise ValueError("Only structurally valid archived runs can be scored")
    candidate = json.loads(
        (run_directory / "normalized_output.json").read_text(encoding="utf-8")
    )
    reference = json.loads(Path(reference_path).read_text(encoding="utf-8"))
    if candidate.get("task_id") != reference.get("task_id"):
        raise ValueError("Candidate/reference task mismatch")
    return score_candidate_against_synthetic_reference(candidate, reference)


def score_v04_finalized_output(
    finalized: dict[str, Any], reference: dict[str, Any], *, numeric_tolerance: float = 1e-6
) -> dict[str, Any]:
    model_output = dict(finalized["model_output"])
    model_output["evidence"] = [
        {"source_id": item["source_id"], "page": item["page"]}
        for item in finalized["resolved_evidence"]
    ]
    model_dimensions = score_candidate_against_synthetic_reference(
        model_output, reference, numeric_tolerance=numeric_tolerance
    )["dimensions"]
    calculation = finalized.get("deterministic_calculation")
    framework_value_match = None
    if calculation is not None and reference.get("normalized_value") is not None:
        framework_value_match = _numeric_match(
            calculation["result"], reference["normalized_value"], 0.005
        )
    return {
        "schema_version": "1.0",
        "task_id": reference["task_id"],
        "reference_type": "ai_simulated_synthetic_reference",
        "human_gold_standard": False,
        "model_dimensions": model_dimensions,
        "framework_dimensions": {
            "evidence_resolved_deterministically": bool(finalized["resolved_evidence"]),
            "calculation_executed_deterministically": calculation is not None,
            "deterministic_calculation_value_match": framework_value_match,
            "model_output_modified": finalized["model_output_modified"],
            "posthoc_semantic_repair_applied": finalized[
                "posthoc_semantic_repair_applied"
            ],
        },
        "aggregate_score": None,
    }
