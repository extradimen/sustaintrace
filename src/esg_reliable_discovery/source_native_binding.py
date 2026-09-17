from __future__ import annotations

import re
from typing import Any

from .knowledge_base import normalized_text, scalar_literal_variants


def _literal_present(literal: str, text: str, *, numeric: bool) -> bool:
    needle = normalized_text(literal)
    haystack = normalized_text(text)
    if not needle:
        return False
    if not numeric:
        return needle in haystack
    return re.search(rf"(?<![\d.]){re.escape(needle)}(?![\d.])", haystack) is not None


def bind_source_native_field(
    fact: dict[str, Any],
    qualification: dict[str, Any],
    native_page_text: str | None,
    *,
    pdf_path: str | None,
    pdf_page: int | None,
    context_radius: int = 2,
) -> dict[str, Any]:
    """Locate a scalar and its frozen row/column labels in native PDF text lines.

    The result is diagnostic only. It never changes fact trust or qualification.
    """
    matches = qualification.get("table_cell_binding", {}).get("matches", [])
    required_labels = sorted(
        {
            normalized_text(str(value))
            for match in matches
            for value in (match.get("row"), match.get("column"))
            if normalized_text(str(value or ""))
        }
    )
    if native_page_text is None:
        status = "unavailable"
        candidates: list[dict[str, Any]] = []
        reason = "native_pdf_page_text_unavailable"
    else:
        lines = [line for line in native_page_text.splitlines() if line.strip()]
        value = fact.get("value")
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        variants = scalar_literal_variants(value)
        candidates = []
        for index, line in enumerate(lines):
            if not any(_literal_present(item, line, numeric=numeric) for item in variants):
                continue
            start = max(0, index - context_radius)
            end = min(len(lines), index + context_radius + 1)
            window = "\n".join(lines[start:end])
            normalized_window = normalized_text(window)
            found_labels = [label for label in required_labels if label in normalized_window]
            candidates.append(
                {
                    "line_number": index + 1,
                    "context_start_line": start + 1,
                    "context_end_line": end,
                    "value_line": line.strip(),
                    "context": window,
                    "found_labels": found_labels,
                    "all_required_labels_found": len(found_labels) == len(required_labels),
                }
            )
        complete = [item for item in candidates if item["all_required_labels_found"]]
        if not candidates:
            status = "literal_not_found"
            reason = "no_native_line_contains_the_scalar_literal"
        elif len(complete) == 1:
            status = "unique_context_binding"
            reason = "one_native_line_window_contains_the_scalar_and_all_required_labels"
        elif len(complete) > 1:
            status = "ambiguous_context_binding"
            reason = "multiple_native_line_windows_contain_the_scalar_and_required_labels"
        elif required_labels:
            status = "label_context_incomplete"
            reason = "scalar_occurs_but_row_or_column_labels_are_not_in_the_local_window"
        elif len(candidates) == 1:
            status = "unique_literal_binding"
            reason = "one_native_line_contains_the_scalar_and_no_table_labels_are_required"
        else:
            status = "ambiguous_literal_binding"
            reason = "scalar_occurs_on_multiple_native_lines_without_table_labels"

    return {
        "schema_version": "0.1",
        "record_kind": "source_native_field_binding",
        "fact_record_id": fact["record_id"],
        "task_id": fact["subject"]["task_id"],
        "pdf_path": pdf_path,
        "pdf_page": pdf_page,
        "required_labels": required_labels,
        "status": status,
        "candidates": candidates,
        "promotion_eligible": False,
        "reason": reason,
    }
