from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class P1AnnotationError(ValueError):
    pass


CRITICAL_FIELDS = (
    "question",
    "answer_status",
    "answer",
    "normalized_value",
    "normalized_unit",
    "reported_unit",
    "subject",
    "scope_boundary",
    "period",
    "calculation",
    "evidence",
    "search_record",
    "controlled_intervention_id",
)


def _load_and_validate(path: str | Path, schema: dict[str, Any]) -> dict[str, Any]:
    annotation = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(annotation),
        key=lambda item: list(item.path),
    )
    if errors:
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise P1AnnotationError(f"Invalid annotation {path}: {detail}")
    if annotation["annotation_status"] != "complete":
        raise P1AnnotationError(f"Annotation is not complete: {path}")
    return annotation


def compare_p1_annotation_paths(
    annotation_a_path: str | Path,
    annotation_b_path: str | Path,
    schema_path: str | Path,
) -> dict[str, Any]:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    annotation_a = _load_and_validate(annotation_a_path, schema)
    annotation_b = _load_and_validate(annotation_b_path, schema)
    if annotation_a["task_id"] != annotation_b["task_id"]:
        raise P1AnnotationError("Annotations refer to different task IDs")
    if annotation_a["annotator_id"] == annotation_b["annotator_id"]:
        raise P1AnnotationError("Independent annotations require distinct annotator IDs")

    comparisons = []
    for field in CRITICAL_FIELDS:
        value_a = annotation_a.get(field)
        value_b = annotation_b.get(field)
        comparisons.append({
            "field": field,
            "agreement": value_a == value_b,
            "value_a": value_a,
            "value_b": value_b,
        })
    disagreements = [item["field"] for item in comparisons if not item["agreement"]]
    return {
        "schema_version": "1.0",
        "task_id": annotation_a["task_id"],
        "annotator_a": annotation_a["annotator_id"],
        "annotator_b": annotation_b["annotator_id"],
        "comparisons": comparisons,
        "disagreement_fields": disagreements,
        "adjudication_required": bool(disagreements),
        "automatic_winner_selected": False,
    }
