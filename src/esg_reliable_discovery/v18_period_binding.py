from __future__ import annotations

import re
from typing import Any


def bind_multiyear_inputs(
    *,
    inputs: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    document_reporting_year: int,
) -> dict[str, Any]:
    """Bind explicit reporting-year and previous-year values without model repair."""
    if len(inputs) != 2:
        raise ValueError("v18_requires_two_inputs")
    index = {item["handle"]: item for item in evidence}
    if len(index) != len(evidence):
        raise ValueError("v18_evidence_handles_must_be_unique")
    years = {int(item["period_year"]) for item in inputs}
    expected = {document_reporting_year, document_reporting_year - 1}
    if years != expected:
        raise ValueError("v18_periods_not_reporting_and_previous_year")
    bindings = []
    for item in inputs:
        handle = item["evidence_handle"]
        if handle not in index:
            raise ValueError(f"v18_unknown_evidence_handle:{handle}")
        text = " ".join(
            str(index[handle].get(key, ""))
            for key in ("verbatim_text", "normalized_text", "table_header_context")
        )
        year = int(item["period_year"])
        if str(year) in text:
            rule = "explicit_year_literal"
        elif (
            year == document_reporting_year - 1
            and re.search(r"\b(previous|prior) year\b", text, re.IGNORECASE)
            and str(document_reporting_year) in text
        ):
            rule = "previous_year_relative_to_explicit_reporting_year"
        else:
            raise ValueError(f"v18_period_not_grounded:{handle}:{year}")
        bindings.append({**item, "binding_rule": rule})
    return {
        "bindings": bindings,
        "document_reporting_year": document_reporting_year,
        "period_literals_preserved": True,
        "candidate_output_modified": False,
    }
