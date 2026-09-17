from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

FATAL_FIELDS = (
    "claim_correctness",
    "evidence_entailment",
    "evidence_locator_valid",
)
DIMENSION_FIELDS = (
    "boundary_fidelity",
    "novelty",
    "decision_relevance",
    "falsifiability",
    "non_redundancy",
)


def _cohen_kappa(left: list[Any], right: list[Any]) -> float | None:
    if len(left) != len(right):
        raise ValueError("Reviewer vectors must have equal length")
    if not left:
        return None
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_counts = Counter(left)
    right_counts = Counter(right)
    labels = set(left_counts) | set(right_counts)
    expected = sum(
        (left_counts[label] / len(left)) * (right_counts[label] / len(right)) for label in labels
    )
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def _validate(review: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(review), key=lambda error: list(error.path)
    )
    return [error.message for error in errors]


def compare_independent_reviews(
    reviews_a: list[dict[str, Any]],
    reviews_b: list[dict[str, Any]],
    schema: dict[str, Any],
) -> dict[str, Any]:
    by_hash_a = {review.get("candidate_sha256"): review for review in reviews_a}
    by_hash_b = {review.get("candidate_sha256"): review for review in reviews_b}
    common = sorted(set(by_hash_a) & set(by_hash_b))
    only_a = sorted(set(by_hash_a) - set(by_hash_b))
    only_b = sorted(set(by_hash_b) - set(by_hash_a))

    schema_errors = {
        "A": {
            review.get("review_id", f"index-{index}"): _validate(review, schema)
            for index, review in enumerate(reviews_a)
            if _validate(review, schema)
        },
        "B": {
            review.get("review_id", f"index-{index}"): _validate(review, schema)
            for index, review in enumerate(reviews_b)
            if _validate(review, schema)
        },
    }

    agreement: dict[str, dict[str, float | int | None]] = {}
    paths = {
        **{field: ("fatal_checks", field) for field in FATAL_FIELDS},
        **{field: ("dimensions", field) for field in DIMENSION_FIELDS},
        "disposition": ("disposition",),
    }
    for name, path in paths.items():
        left: list[Any] = []
        right: list[Any] = []
        for candidate_hash in common:
            value_a: Any = by_hash_a[candidate_hash]
            value_b: Any = by_hash_b[candidate_hash]
            for part in path:
                value_a = value_a[part]
                value_b = value_b[part]
            if isinstance(value_a, dict):
                value_a = value_a["rating"]
                value_b = value_b["rating"]
            left.append(value_a)
            right.append(value_b)
        exact = sum(a == b for a, b in zip(left, right, strict=True)) if common else 0
        agreement[name] = {
            "paired_count": len(common),
            "exact_agreement": exact / len(common) if common else None,
            "cohen_kappa": _cohen_kappa(left, right),
        }

    disagreements = []
    for candidate_hash in common:
        differing = [
            name
            for name, path in paths.items()
            if _path_rating(by_hash_a[candidate_hash], path)
            != _path_rating(by_hash_b[candidate_hash], path)
        ]
        if differing:
            disagreements.append({"candidate_sha256": candidate_hash, "disputed_fields": differing})

    return {
        "paired_candidate_count": len(common),
        "unpaired_candidate_hashes": {"A_only": only_a, "B_only": only_b},
        "schema_errors": schema_errors,
        "dimension_agreement": agreement,
        "adjudication_queue": disagreements,
        "aggregate_score": None,
    }


def _path_rating(review: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = review
    for part in path:
        value = value[part]
    return value.get("rating") if isinstance(value, dict) else value


def compare_review_paths(
    reviews_a_path: str | Path,
    reviews_b_path: str | Path,
    schema_path: str | Path,
) -> dict[str, Any]:
    reviews_a = json.loads(Path(reviews_a_path).read_text(encoding="utf-8"))
    reviews_b = json.loads(Path(reviews_b_path).read_text(encoding="utf-8"))
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    return compare_independent_reviews(reviews_a, reviews_b, schema)
