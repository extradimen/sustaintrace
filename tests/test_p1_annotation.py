import json

import pytest

from esg_reliable_discovery.p1_annotation import (
    P1AnnotationError,
    compare_p1_annotation_paths,
)


def _annotation(annotator_id, answer="42"):
    return {
        "schema_version": "1.0",
        "task_id": "P1-01-1",
        "annotator_id": annotator_id,
        "annotation_status": "complete",
        "question": "What value did the company report for this metric?",
        "answer_status": "verified_fact",
        "answer": answer,
        "evidence": [{
            "document_id": "DOC-1",
            "pdf_page": 20,
            "printed_page": "18",
            "verbatim_excerpt": "The reported value was 42 units.",
            "role": "claim_support",
        }],
        "search_record": {"pages_reviewed": [20], "terms_used": ["reported value"]},
        "independence_attestation": {
            "worked_independently": True,
            "did_not_view_other_annotation": True,
            "is_human": True,
        },
    }


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_compare_reports_dimension_disagreement_without_selecting_winner(tmp_path):
    schema = "templates/p1_annotation.schema.json"
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    _write(path_a, _annotation("human-a"))
    _write(path_b, _annotation("human-b", answer="43"))
    result = compare_p1_annotation_paths(path_a, path_b, schema)
    assert result["adjudication_required"] is True
    assert "answer" in result["disagreement_fields"]
    assert result["automatic_winner_selected"] is False


def test_compare_rejects_nonhuman_attestation(tmp_path):
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    first = _annotation("human-a")
    first["independence_attestation"]["is_human"] = False
    _write(path_a, first)
    _write(path_b, _annotation("human-b"))
    with pytest.raises(P1AnnotationError, match="Invalid annotation"):
        compare_p1_annotation_paths(path_a, path_b, "templates/p1_annotation.schema.json")


def test_compare_rejects_same_annotator(tmp_path):
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    _write(path_a, _annotation("human-a"))
    _write(path_b, _annotation("human-a"))
    with pytest.raises(P1AnnotationError, match="distinct annotator"):
        compare_p1_annotation_paths(path_a, path_b, "templates/p1_annotation.schema.json")
