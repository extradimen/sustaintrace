from __future__ import annotations

import re
from typing import Any

from jsonschema import Draft202012Validator

from .scoring import _evidence_keys, _same_reported_value

UNIT_ALIASES = {
    "megawatt": "mw",
    "megawatts": "mw",
    "mw": "mw",
    "percent": "%",
    "percentage": "%",
    "%": "%",
    "number": "no.",
    "no": "no.",
    "no.": "no.",
}


def _tokens(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _token_jaccard(candidate: Any, gold: Any) -> float:
    left = _tokens(candidate)
    right = _tokens(gold)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _canonical_unit(value: Any) -> str:
    normalized = " ".join(str(value or "").casefold().split())
    return UNIT_ALIASES.get(normalized, normalized)


def score_finding_card_v2(
    candidate: dict[str, Any], gold: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(candidate), key=lambda error: list(error.path)
    )
    candidate_metric = candidate.get("metric") or {}
    gold_metric = gold.get("metric") or {}
    gold_calculation = gold.get("calculation")
    candidate_calculation = candidate.get("calculation")
    calculation_result_accuracy: int | None = None
    if gold_calculation is not None:
        try:
            calculation_result_accuracy = int(
                _same_reported_value(
                    candidate_calculation["result"], gold_calculation["result"]
                )
                and _canonical_unit(candidate_calculation.get("unit"))
                == _canonical_unit(gold_calculation.get("unit"))
            )
        except (KeyError, TypeError):
            calculation_result_accuracy = 0
    gold_is_abstention = gold.get("status") in {
        "insufficient_information",
        "extraction_failure",
        "not_applicable",
    }
    return {
        "task_id": gold.get("task_id"),
        "score_version": "2.0-development",
        "dimensions": {
            "schema_validity": int(not errors),
            "status_accuracy": int(candidate.get("status") == gold.get("status")),
            "finding_type_accuracy": int(
                candidate.get("finding_type") == gold.get("finding_type")
            ),
            "claim_level_accuracy": int(candidate.get("claim_level") == gold.get("claim_level")),
            "reported_value_accuracy": (
                int(
                    _same_reported_value(
                        candidate_metric.get("reported_value"),
                        gold_metric.get("reported_value"),
                    )
                )
                if gold_metric
                else None
            ),
            "unit_canonical_accuracy": (
                int(
                    _canonical_unit(candidate_metric.get("unit"))
                    == _canonical_unit(gold_metric.get("unit"))
                )
                if gold_metric
                else None
            ),
            "metric_name_token_jaccard": (
                _token_jaccard(candidate_metric.get("name"), gold_metric.get("name"))
                if gold_metric
                else None
            ),
            "subject_token_jaccard": (
                _token_jaccard(candidate_metric.get("subject"), gold_metric.get("subject"))
                if gold_metric
                else None
            ),
            "boundary_token_jaccard": (
                _token_jaccard(candidate_metric.get("boundary"), gold_metric.get("boundary"))
                if gold_metric
                else None
            ),
            "period_token_jaccard": (
                _token_jaccard(candidate_metric.get("period"), gold_metric.get("period"))
                if gold_metric
                else None
            ),
            "supporting_evidence_locator_accuracy": int(
                _evidence_keys(candidate.get("supporting_evidence", []))
                == _evidence_keys(gold.get("supporting_evidence", []))
            ),
            "contrary_evidence_locator_accuracy": int(
                _evidence_keys(candidate.get("contrary_evidence", []))
                == _evidence_keys(gold.get("contrary_evidence", []))
            ),
            "calculation_result_accuracy": calculation_result_accuracy,
            "abstention_status_accuracy": (
                int(candidate.get("status") == gold.get("status"))
                if gold_is_abstention
                else None
            ),
        },
        "schema_errors": [error.message for error in errors],
        "aggregate_score": None,
    }
