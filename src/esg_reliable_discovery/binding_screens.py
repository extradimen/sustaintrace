from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .read_only_diagnostics import _numeric, _page_text, _page_words


def _center(word: dict[str, Any], axis: str) -> float:
    return (word[f"{axis}0"] + word[f"{axis}1"]) / 2


def _coordinates(word: dict[str, Any]) -> dict[str, float]:
    return {key: word[key] for key in ("x0", "y0", "x1", "y1")}


def _same_row(words: list[dict[str, Any]], cell: dict[str, Any]) -> str:
    return " ".join(
        word["text"]
        for word in words
        if abs(_center(word, "y") - _center(cell, "y")) <= 2
    )


def screen_period_binding(case: dict[str, Any], root: Path) -> dict[str, Any]:
    reasons: list[str] = []
    evidence_coordinates: list[dict[str, Any]] = []
    parser_year = str(case.get("parser_year") or "")
    target = _numeric(case.get("value"))
    row_label = case.get("row_label")
    if not parser_year or target is None or not row_label:
        reasons.append("one_frozen_cell_or_field_not_supplied")
    else:
        pdf = root / case["native_source"]["path"]
        words = _page_words(pdf, case["page"])
        cells = [word for word in words if _numeric(word["text"]) == target]
        row_cells = [
            cell
            for cell in cells
            if row_label.casefold() in _same_row(words, cell).casefold()
        ]
        if len(row_cells) != 1:
            reasons.append("target_cell_not_unique_on_named_row")
        else:
            cell = row_cells[0]
            years = [
                word
                for word in words
                if re.fullmatch(r"20\d{2}", word["text"]) and word["y1"] < cell["y0"]
            ]
            if not years:
                reasons.append("native_year_header_not_found")
            else:
                year = min(years, key=lambda word: abs(_center(word, "x") - _center(cell, "x")))
                evidence_coordinates.append(
                    {
                        "page": case["page"],
                        "row_label": row_label,
                        "cell": _coordinates(cell),
                        "native_year": year["text"],
                        "year_header": _coordinates(year),
                    }
                )
                if year["text"] != parser_year:
                    reasons.append("parser_native_year_disagreement")
    return {
        "eligibility": "eligible" if not reasons else "ineligible",
        "binding_type": "period",
        "bound_value": case.get("value"),
        "bound_period": parser_year or None,
        "evidence_coordinates": evidence_coordinates,
        "blocking_reasons": reasons,
    }


def screen_unit_binding(case: dict[str, Any], root: Path) -> dict[str, Any]:
    reasons: list[str] = []
    markers = [str(value) for value in case.get("unit_marker_candidates", []) if value]
    quote = str(case.get("bound_quote") or "")
    if len(markers) != 1:
        reasons.append("unit_marker_not_unique")
    marker = markers[0] if len(markers) == 1 else None
    pdf = root / case["native_source"]["path"]
    page_text = _page_text(pdf, case["page"], layout=True)
    if marker and marker.casefold() not in quote.casefold():
        reasons.append("unit_marker_absent_from_bound_quote")
    if marker and marker.casefold() not in page_text.casefold():
        reasons.append("unit_marker_absent_from_native_page")
    if case.get("conversion_required"):
        reasons.append("unit_conversion_or_inference_required")

    coordinates: list[dict[str, Any]] = []
    target = _numeric(case.get("value"))
    row_label = case.get("row_label")
    if marker and target is not None and row_label:
        words = _page_words(pdf, case["page"])
        cells = [
            word
            for word in words
            if _numeric(word["text"]) == target
            and row_label.casefold() in _same_row(words, word).casefold()
        ]
        if len(cells) == 1:
            coordinates.append(
                {
                    "page": case["page"],
                    "row_label": row_label,
                    "value_cell": _coordinates(cells[0]),
                    "unit_marker": marker,
                }
            )
        else:
            reasons.append("value_unit_row_not_unique")
    elif not row_label:
        reasons.append("bound_value_row_not_supplied")

    return {
        "eligibility": "eligible" if not reasons else "ineligible",
        "binding_type": "unit",
        "bound_value": case.get("value"),
        "bound_unit_marker": marker,
        "evidence_coordinates": coordinates,
        "blocking_reasons": reasons,
    }
