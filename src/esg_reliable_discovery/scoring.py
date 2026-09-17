from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _normalized(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).casefold().split())


def _numbers(value: Any) -> list[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    return [float(item) for item in re.findall(r"[-+]?\d+(?:\.\d+)?", str(value))]


def _same_reported_value(candidate: Any, gold: Any) -> bool:
    gold_numbers = _numbers(gold)
    candidate_numbers = _numbers(candidate)
    if gold_numbers or candidate_numbers:
        return len(gold_numbers) == len(candidate_numbers) and all(
            math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-6)
            for left, right in zip(candidate_numbers, gold_numbers, strict=True)
        )
    return _normalized(candidate) == _normalized(gold)


def _evidence_keys(items: list[dict[str, Any]]) -> set[tuple[str, str, int]]:
    return {
        (item.get("document_id", ""), item.get("document_sha256", ""), item.get("page", 0))
        for item in items
    }


def score_finding_card(
    candidate: dict[str, Any], gold: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(candidate), key=lambda error: list(error.path)
    )
    candidate_metric = candidate.get("metric") or {}
    gold_metric = gold.get("metric") or {}
    gold_calculation = gold.get("calculation")
    candidate_calculation = candidate.get("calculation")

    evidence_accuracy = _evidence_keys(candidate.get("supporting_evidence", [])) == _evidence_keys(
        gold.get("supporting_evidence", [])
    ) and _evidence_keys(candidate.get("contrary_evidence", [])) == _evidence_keys(
        gold.get("contrary_evidence", [])
    )
    boundary_fields = ("unit", "subject", "boundary", "period")
    boundary_accuracy = all(
        _normalized(candidate_metric.get(field)) == _normalized(gold_metric.get(field))
        for field in boundary_fields
    )
    if gold_calculation is None:
        calculation_accuracy: int | None = None
    else:
        try:
            calculation_accuracy = int(
                math.isclose(
                    float(candidate_calculation["result"]),
                    float(gold_calculation["result"]),
                    rel_tol=1e-4,
                    abs_tol=1e-4,
                )
                and _normalized(candidate_calculation.get("unit"))
                == _normalized(gold_calculation.get("unit"))
            )
        except (KeyError, TypeError, ValueError):
            calculation_accuracy = 0

    abstention_statuses = {
        "insufficient_information",
        "extraction_failure",
        "not_applicable",
    }
    abstention_accuracy = (
        int(candidate.get("status") == gold.get("status"))
        if gold.get("status") in abstention_statuses
        else None
    )
    answer_correctness = (
        int(candidate.get("status") == gold.get("status"))
        if not gold_metric
        else int(
            _normalized(candidate_metric.get("name")) == _normalized(gold_metric.get("name"))
            and _same_reported_value(
                candidate_metric.get("reported_value"), gold_metric.get("reported_value")
            )
        )
    )

    return {
        "task_id": gold.get("task_id"),
        "dimensions": {
            "schema_validity": int(not errors),
            "status_accuracy": int(candidate.get("status") == gold.get("status")),
            "classification_accuracy": int(
                candidate.get("finding_type") == gold.get("finding_type")
                and candidate.get("claim_level") == gold.get("claim_level")
                and set(candidate.get("anomaly_codes", [])) == set(gold.get("anomaly_codes", []))
            ),
            "answer_correctness": answer_correctness,
            "evidence_accuracy": int(evidence_accuracy),
            "boundary_accuracy": int(boundary_accuracy),
            "calculation_accuracy": calculation_accuracy,
            "abstention_accuracy": abstention_accuracy,
        },
        "schema_errors": [error.message for error in errors],
        "aggregate_score": None,
    }


def score_finding_card_paths(
    candidate_path: str | Path, gold_path: str | Path, schema_path: str | Path
) -> dict[str, Any]:
    candidate = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
    gold = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    return score_finding_card(candidate, gold, schema)
