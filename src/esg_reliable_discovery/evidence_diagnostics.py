from __future__ import annotations

from collections.abc import Iterable
from typing import Any

NOT_DISCLOSED_MARKERS = (
    "not reported",
    "not disclosed",
    "information unavailable",
)


def _canonical(value: Any) -> str:
    return " ".join(str(value).casefold().replace(",", "").split())


def _contains_all(text: str, anchors: Iterable[Any]) -> bool:
    canonical = _canonical(text)
    return all(_canonical(anchor) in canonical for anchor in anchors)


def diagnose_evidence_state(
    *,
    issuer_answer_status: str,
    expected_anchors: list[Any],
    raw_page_text: str,
    parsed_page_text: str,
    retrieved_evidence_text: str,
    structure_required: bool = False,
    raw_structure_supported: bool = True,
    parsed_structure_supported: bool = True,
    retrieved_structure_supported: bool = True,
) -> dict[str, Any]:
    """Separate issuer non-disclosure, parser loss, and retrieval loss.

    Expected anchors are benchmark-only facts. This diagnostic must not be used
    to inject hidden values into candidate evidence or outputs.
    """
    raw_has = _contains_all(raw_page_text, expected_anchors)
    parsed_has = _contains_all(parsed_page_text, expected_anchors)
    retrieved_has = _contains_all(retrieved_evidence_text, expected_anchors)
    parsed_canonical = _canonical(parsed_page_text)

    raw_supported = raw_has and (not structure_required or raw_structure_supported)
    parsed_supported = parsed_has and (not structure_required or parsed_structure_supported)
    retrieved_supported = retrieved_has and (
        not structure_required or retrieved_structure_supported
    )

    if issuer_answer_status == "not_disclosed":
        marker = next(
            (item for item in NOT_DISCLOSED_MARKERS if item in parsed_canonical), None
        )
        state = "not_disclosed_by_issuer" if marker else "non_disclosure_marker_missing"
    elif retrieved_supported:
        marker = None
        state = "supported_in_retrieved_evidence"
    elif parsed_supported:
        marker = None
        state = "retrieval_miss"
    elif raw_supported:
        marker = None
        state = "parser_structure_unrecoverable"
    else:
        marker = None
        state = "source_or_benchmark_anchor_unresolved"

    return {
        "state": state,
        "issuer_answer_status": issuer_answer_status,
        "raw_page_contains_all_anchors": raw_has,
        "parsed_page_contains_all_anchors": parsed_has,
        "retrieved_evidence_contains_all_anchors": retrieved_has,
        "structure_required": structure_required,
        "raw_structure_supported": raw_structure_supported,
        "parsed_structure_supported": parsed_structure_supported,
        "retrieved_structure_supported": retrieved_structure_supported,
        "non_disclosure_marker": marker,
        "hidden_anchor_injection_allowed": False,
    }
