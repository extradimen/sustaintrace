from __future__ import annotations

import re
import unicodedata
from typing import Any


def _position_text(text: str) -> str:
    """Normalize characters without changing their one-character column positions."""
    return "".join(
        {
            "³": "3",
            "²": "2",
            "¹": "1",
            "–": "-",
            "—": "-",
            "’": "'",
        }.get(character, character)
        for character in unicodedata.normalize("NFKC", text)
    ).casefold()


def _semantic_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", _position_text(text)).split())


def _header_position(line: str, header: str) -> int:
    haystack = _position_text(line)
    needle = _position_text(header).strip()
    exact = haystack.find(needle)
    if exact >= 0:
        return exact
    tokens = _semantic_text(header).split()
    if not tokens:
        return -1
    # A header may wrap physically. Its first distinctive token still fixes the
    # column start; require at least four characters to avoid matching noise.
    anchor = next((token for token in tokens if len(token) >= 4), tokens[0])
    return haystack.find(anchor)


def corroborate_wrapped_table_cell(
    *,
    native_page: str,
    row_header: str,
    raw_value: str,
    column_headers: list[str],
    row_header_column_index: int,
    value_column_index: int,
    line_radius: int = 4,
) -> dict[str, Any]:
    """Bind a wrapped native-PDF row label to one table value, fail-closed.

    The method uses only physical layout columns inferred from a single header
    line. It never joins text across a table boundary or chooses a fuzzy semantic
    match. A match is accepted only when exactly one value-bearing physical line
    has the full normalized row label in its bounded same-column neighbourhood.
    """
    result: dict[str, Any] = {
        "matched": False,
        "method": "bounded_layout_column_reassembly_v1",
        "header_line_index": None,
        "value_line_index": None,
        "indicator_span": None,
        "value_span": None,
        "candidate_matches": 0,
    }
    if not (0 <= row_header_column_index < value_column_index < len(column_headers)):
        result["failure_reason"] = "invalid_column_indices"
        return result

    lines = native_page.splitlines()
    header_candidates: list[tuple[int, list[int]]] = []
    required_indices = (row_header_column_index, value_column_index)
    for line_index, line in enumerate(lines):
        positions = [_header_position(line, header) for header in column_headers]
        if all(positions[index] >= 0 for index in required_indices):
            ordered = [position for position in positions if position >= 0]
            if ordered == sorted(ordered):
                header_candidates.append((line_index, positions))
    if len(header_candidates) != 1:
        result["failure_reason"] = "header_line_not_unique"
        result["header_candidate_count"] = len(header_candidates)
        return result

    header_line_index, positions = header_candidates[0]
    indicator_start = positions[row_header_column_index]
    later_indicator_boundaries = [
        position
        for index, position in enumerate(positions)
        if index > row_header_column_index and position > indicator_start
    ]
    value_start = positions[value_column_index]
    later_value_boundaries = [
        position
        for index, position in enumerate(positions)
        if index > value_column_index and position > value_start
    ]
    if not later_indicator_boundaries:
        result["failure_reason"] = "indicator_column_has_no_right_boundary"
        return result
    indicator_end = min(later_indicator_boundaries)
    value_end = min(later_value_boundaries, default=value_start + max(12, len(raw_value) + 4))
    if indicator_end > value_start:
        result["failure_reason"] = "overlapping_column_spans"
        return result

    value_literal = _semantic_text(raw_value)
    row_literal = _semantic_text(row_header)
    matches = []
    for line_index in range(header_line_index + 1, len(lines)):
        value_cell = _semantic_text(lines[line_index][value_start:value_end])
        if value_cell != value_literal:
            continue
        lower = max(header_line_index + 1, line_index - line_radius)
        upper = min(len(lines), line_index + line_radius + 1)
        assembled = _semantic_text(
            " ".join(lines[index][indicator_start:indicator_end] for index in range(lower, upper))
        )
        if row_literal in assembled:
            matches.append((line_index, lower, upper, assembled))

    result.update(
        {
            "header_line_index": header_line_index,
            "indicator_span": [indicator_start, indicator_end],
            "value_span": [value_start, value_end],
            "candidate_matches": len(matches),
        }
    )
    if len(matches) != 1:
        result["failure_reason"] = "row_value_binding_not_unique"
        return result
    line_index, lower, upper, assembled = matches[0]
    result.update(
        {
            "matched": True,
            "value_line_index": line_index,
            "bounded_line_window": [lower, upper - 1],
            "assembled_indicator_text": assembled,
        }
    )
    return result
