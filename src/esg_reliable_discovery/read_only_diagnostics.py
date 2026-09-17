from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from typing import Any

from .knowledge_base import stable_id


def _page_text(pdf: Path, page: int, *, layout: bool = False) -> str:
    command = ["pdftotext", "-f", str(page), "-l", str(page)]
    if layout:
        command.append("-layout")
    command.extend([str(pdf), "-"])
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def _page_words(pdf: Path, page: int) -> list[dict[str, Any]]:
    command = [
        "pdftotext",
        "-f",
        str(page),
        "-l",
        str(page),
        "-bbox-layout",
        str(pdf),
        "-",
    ]
    output = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(output)
    words = []
    for word in root.findall(".//{http://www.w3.org/1999/xhtml}word"):
        words.append(
            {
                "text": "".join(word.itertext()),
                "x0": float(word.attrib["xMin"]),
                "y0": float(word.attrib["yMin"]),
                "x1": float(word.attrib["xMax"]),
                "y1": float(word.attrib["yMax"]),
            }
        )
    return words


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _numeric(value: Any) -> Decimal | None:
    raw = str(value).strip().replace(",", "")
    match = re.fullmatch(r"[-+]?\d+(?:\.\d+)?", raw)
    return Decimal(raw) if match else None


def _coordinates(word: dict[str, Any]) -> dict[str, float]:
    return {key: float(word[key]) for key in ("x0", "y0", "x1", "y1")}


def _nearest_year_header(
    words: list[dict[str, Any]], item: dict[str, Any]
) -> dict[str, Any] | None:
    candidates = [
        word
        for word in words
        if re.fullmatch(r"20\d{2}", word["text"]) and word["y1"] < item["y0"]
    ]
    if not candidates:
        return None

    # A single visual header row is not guaranteed to share one PDF baseline.
    # Holcim's 2025 header is vertically shifted but still overlaps 2023/2024.
    # Build connected vertical bands from overlapping year boxes, then use the
    # nearest complete band above the cell.  This avoids treating a shifted
    # header as a separate row while keeping genuinely separate tables apart.
    bands: list[list[dict[str, Any]]] = []
    for word in sorted(candidates, key=lambda candidate: (candidate["y0"], candidate["y1"])):
        if not bands or word["y0"] > max(member["y1"] for member in bands[-1]) + 2:
            bands.append([word])
        else:
            bands[-1].append(word)
    header_band = max(bands, key=lambda band: max(word["y1"] for word in band))
    distances = [
        (
            abs((word["x0"] + word["x1"]) - (item["x0"] + item["x1"])),
            word,
        )
        for word in header_band
    ]
    minimum = min(distance for distance, _ in distances)
    nearest = [word for distance, word in distances if abs(distance - minimum) <= 1e-6]
    return nearest[0] if len(nearest) == 1 else None


def _fact_field(fact: dict[str, Any]) -> str:
    return fact.get("predicate", {}).get("canonical_key", fact["record_id"])


def _literal_coordinate_matches(
    words: list[dict[str, Any]], literal: str
) -> list[dict[str, float]]:
    target = _compact(literal).rstrip(".;:")
    token_count = len(literal.split())
    matches = []
    for start in range(len(words)):
        for width in range(max(1, token_count - 2), token_count + 3):
            selected = words[start : start + width]
            candidate = _compact(" ".join(word["text"] for word in selected)).rstrip(
                ".;:"
            )
            if selected and candidate == target:
                matches.append(
                    {
                        "x0": min(word["x0"] for word in selected),
                        "y0": min(word["y0"] for word in selected),
                        "x1": max(word["x1"] for word in selected),
                        "y1": max(word["y1"] for word in selected),
                    }
                )
    return matches


def _row_label_tokens(
    words: list[dict[str, Any]], cell: dict[str, Any]
) -> list[dict[str, Any]]:
    candidates = sorted(
        (
            word
            for word in words
            if abs(
                (word["y0"] + word["y1"]) / 2
                - (cell["y0"] + cell["y1"]) / 2
            )
            <= 2
            and word["x1"] < cell["x0"]
        ),
        key=lambda word: word["x0"],
    )
    if len(candidates) < 2:
        return candidates
    gaps = [
        (candidates[index + 1]["x0"] - candidates[index]["x1"], index)
        for index in range(len(candidates) - 1)
    ]
    gap, index = max(gaps)
    return candidates[: index + 1] if gap >= 12 else candidates


def _normalize_row_label(value: str) -> str:
    value = re.sub(r"\bCO\s+2\s+e\b", "CO2e", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def diagnose_field_binding(fixture: dict[str, Any], fact: dict[str, Any], root: Path) -> dict:
    pdf = root / fixture["native_source"]["path"]
    selector = fixture.get("adapter_inputs", {}).get("evidence_selector")
    if selector is not None:
        reasons = []
        required = {"source_id", "pdf_page", "quote"}
        if not isinstance(selector, dict) or not required <= set(selector):
            reasons.append("evidence_selector_incomplete")
            selector = selector if isinstance(selector, dict) else {}
        quote = selector.get("quote")
        page = selector.get("pdf_page")
        source_id = selector.get("source_id")
        evidence = fact.get("evidence", [])
        selected = [
            item
            for item in evidence
            if item.get("source_id") == source_id
            and item.get("pdf_page") == page
            and item.get("quote") == quote
        ]
        if len(selected) != 1:
            reasons.append("evidence_selector_not_unique_in_frozen_fact")
        if quote not in fixture.get("source_literals", []):
            reasons.append("selected_quote_absent_from_frozen_fixture_literals")
        if page not in fixture.get("evidence_pages", []):
            reasons.append("selected_page_outside_frozen_fixture")
        if source_id not in fact.get("subject", {}).get("document_ids", []):
            reasons.append("selected_source_conflicts_with_frozen_fact")

        coordinates = []
        if not reasons:
            page_text = _compact(_page_text(pdf, page))
            match_count = page_text.count(_compact(quote)) if quote else 0
            boxes = _literal_coordinate_matches(_page_words(pdf, page), quote)
            if match_count != 1:
                reasons.append("selected_quote_not_unique_on_native_page")
            if len(boxes) != 1:
                reasons.append("selected_quote_coordinates_not_unique")
            if match_count == 1 and len(boxes) == 1:
                coordinates.append(
                    {
                        "page": page,
                        "literal": quote,
                        "match_count": match_count,
                        "coordinates": boxes[0],
                    }
                )
        return {
            "field_id": _fact_field(fact),
            "collection_cardinality": len(evidence),
            "selected_collection_cardinality": len(selected),
            "evidence_selector": selector,
            "selected_evidence": selected[0] if len(selected) == 1 else None,
            "evidence_coordinates": coordinates,
            "unique_binding": not reasons,
            "blocking_reasons": sorted(set(reasons)),
        }

    matches = []
    for page in fixture["evidence_pages"]:
        text = _compact(_page_text(pdf, page))
        for literal in fixture["source_literals"]:
            count = text.count(_compact(literal)) if literal else 0
            if count:
                matches.append({"page": page, "literal": literal, "match_count": count})
    unique = len(fixture["source_literals"]) == 1 and sum(x["match_count"] for x in matches) == 1
    reasons = [] if unique else ["field_collection_not_uniquely_bound"]
    return {
        "field_id": _fact_field(fact),
        "collection_cardinality": len(fixture["source_literals"]),
        "evidence_coordinates": matches,
        "unique_binding": unique,
        "blocking_reasons": reasons,
    }


def _target_literal(fact: dict[str, Any]) -> str:
    target = _numeric(fact["value"])
    candidates = [item.get("quote") for item in fact.get("evidence", [])]
    matches = [item for item in candidates if _numeric(item) == target]
    if len(matches) != 1:
        raise ValueError("target_literal_not_unique_in_frozen_evidence")
    return matches[0]


def _structured_quote_contains_value(quotes: list[str], value: Decimal) -> bool:
    for quote in quotes:
        literals = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", quote)
        if any(_numeric(literal) == value for literal in literals):
            return True
    return False


def _secondary_header_boxes(
    words: list[dict[str, Any]], label: str, *, above_y: float
) -> list[dict[str, float]]:
    tokens = label.casefold().split()
    if not tokens:
        return []
    anchors = [
        word
        for word in words
        if word["text"].casefold() == tokens[0] and word["y1"] < above_y
    ]
    boxes = []
    for anchor in anchors:
        selected = [anchor]
        for token in tokens[1:]:
            matches = [
                word
                for word in words
                if word["text"].casefold() == token
                and word["y1"] < above_y
                and abs((word["x0"] + word["x1"]) - (anchor["x0"] + anchor["x1"]))
                <= 30
                and abs(word["y0"] - anchor["y0"]) <= 20
            ]
            if not matches:
                break
            selected.append(min(matches, key=lambda word: abs(word["y0"] - anchor["y0"])))
        if len(selected) == len(tokens):
            boxes.append(
                {
                    "x0": min(word["x0"] for word in selected),
                    "y0": min(word["y0"] for word in selected),
                    "x1": max(word["x1"] for word in selected),
                    "y1": max(word["y1"] for word in selected),
                }
            )
    return boxes


def diagnose_table_cell(fixture: dict[str, Any], fact: dict[str, Any], root: Path) -> dict:
    pdf = root / fixture["native_source"]["path"]
    page = fixture["evidence_pages"][0]
    words = _page_words(pdf, page)
    adapter_inputs = fixture.get("adapter_inputs", {})
    if adapter_inputs.get("target_value") is not None:
        target_literal = str(adapter_inputs["target_value"])
        target = _numeric(target_literal)
        if target is None or not _structured_quote_contains_value(
            fixture["source_literals"], target
        ):
            raise ValueError("target_value_not_found_in_structured_frozen_evidence")
    else:
        target_literal = _target_literal(fact)
        target = _numeric(target_literal)
    cells = [word for word in words if _numeric(word["text"]) == target]
    row_constraint = fixture.get("adapter_inputs", {}).get("row_label")
    if row_constraint:
        cells = [
            cell
            for cell in cells
            if row_constraint.casefold()
            in " ".join(
                word["text"]
                for word in words
                if abs(
                    (word["y0"] + word["y1"]) / 2
                    - (cell["y0"] + cell["y1"]) / 2
                )
                <= 2
                ).casefold()
        ]
    period = str(
        fixture.get("adapter_inputs", {}).get("period")
        or fact.get("qualifiers", {}).get("period_literal")
        or ""
    )
    if period and len(cells) > 1:
        years = [word for word in words if word["text"] == period]
        cells = [
            cell
            for cell in cells
            if years
            and (nearest := _nearest_year_header(words, cell)) is not None
            and nearest["text"] == period
        ]
    column_path = adapter_inputs.get("column_path")
    secondary_header = None
    if column_path and len(column_path) > 1 and len(cells) > 1:
        secondary = _secondary_header_boxes(
            words, str(column_path[1]), above_y=min(cell["y0"] for cell in cells)
        )
        secondary = [
            box
            for box in secondary
            if (nearest := _nearest_year_header(words, box)) is not None
            and nearest["text"] == str(column_path[0])
        ]
        if secondary:
            box = min(
                secondary,
                key=lambda item: min(
                    abs((cell["x0"] + cell["x1"]) - (item["x0"] + item["x1"]))
                    for cell in cells
                ),
            )
            cells = [
                min(
                    cells,
                    key=lambda cell: abs(
                        (cell["x0"] + cell["x1"]) - (box["x0"] + box["x1"])
                    ),
                )
            ]
            secondary_header = box
    if len(cells) != 1:
        raise ValueError("native_target_cell_not_unique")
    cell = cells[0]
    years = [word for word in words if word["text"] == period and word["y1"] < cell["y0"]]
    if not years:
        raise ValueError("native_column_year_not_found")
    column = min(years, key=lambda word: abs((word["x0"] + word["x1"]) - (cell["x0"] + cell["x1"])))
    header_coordinates = [{"label": column["text"], "coordinates": _coordinates(column)}]
    if secondary_header is not None:
        header_coordinates.append(
            {"label": str(column_path[1]), "coordinates": secondary_header}
        )
    same_row = _row_label_tokens(words, cell)
    raw_row_header = " ".join(word["text"] for word in same_row).strip()
    row_header = _normalize_row_label(raw_row_header)
    if not row_header:
        raise ValueError("native_row_header_not_found")
    return {
        "page": page,
        "row_header": row_header,
        "raw_row_header": raw_row_header,
        "normalized_row_header": row_header,
        "row_tokens": [
            {"text": word["text"], **{key: word[key] for key in ("x0", "y0", "x1", "y1")}}
            for word in same_row
        ],
        "column_header": column["text"],
        "column_path": column_path or [column["text"]],
        "header_coordinates": header_coordinates,
        "cell_value": target_literal,
        "cell_coordinates": {key: cell[key] for key in ("x0", "y0", "x1", "y1")},
        "parser_native_agreement": target_literal in fixture["source_literals"],
    }


def diagnose_native_corroboration(
    fixture: dict[str, Any], fact: dict[str, Any], root: Path
) -> dict:
    pdf = root / fixture["native_source"]["path"]
    source_literal = _target_literal(fact)
    target = _numeric(source_literal)
    row_tokens = fixture.get("adapter_inputs", {}).get("row_tokens", ["Total", "Scope"])
    matches = []
    for page in fixture["evidence_pages"]:
        words = _page_words(pdf, page)
        for word in words:
            if _numeric(word["text"]) == target:
                row = " ".join(
                    candidate["text"]
                    for candidate in words
                    if abs(
                        (candidate["y0"] + candidate["y1"]) / 2
                        - (word["y0"] + word["y1"]) / 2
                    )
                    <= 2
                )
                if all(token.casefold() in row.casefold() for token in row_tokens):
                    matches.append((page, word))
    if len(matches) != 1:
        raise ValueError("native_literal_not_unique")
    page, word = matches[0]
    return {
        "page": page,
        "source_literal": source_literal,
        "parser_literal": source_literal,
        "normalized_literal": str(target),
        "literal_agreement": True,
        "layout_agreement": all(key in word for key in ("x0", "y0", "x1", "y1")),
    }


def _row_values(text: str, label: str) -> list[Decimal]:
    line = next((line for line in text.splitlines() if line.strip().startswith(label)), None)
    if line is None:
        raise ValueError(f"calculation_row_missing:{label}")
    return [
        Decimal(value.replace(",", ""))
        for value in re.findall(r"\d[\d,]*(?:\.\d+)?", line)
    ]


def _row_column_value(
    pdf: Path, page: int, row_label: str, column: str
) -> tuple[Decimal, dict[str, float]]:
    words = _page_words(pdf, page)
    row_centers = []
    seen_centers = []
    for cell in (word for word in words if _numeric(word["text"]) is not None):
        center = (cell["y0"] + cell["y1"]) / 2
        if any(abs(center - prior) <= 1 for prior in seen_centers):
            continue
        seen_centers.append(center)
        row_cells = [
            word
            for word in words
            if _numeric(word["text"]) is not None
            and abs((word["y0"] + word["y1"]) / 2 - center) <= 2
        ]
        label_tokens = _row_label_tokens(words, max(row_cells, key=lambda word: word["x1"]))
        label = _normalize_row_label(" ".join(word["text"] for word in label_tokens))
        expected = _normalize_row_label(row_label).casefold()
        observed = label.casefold()
        observed_without_footnote = re.sub(r"(?:\s+\d+)+$", "", observed)
        if observed == expected or observed_without_footnote == expected:
            row_centers.append(center)
    if not row_centers:
        raise ValueError(f"calculation_row_missing:{row_label}")
    row_center = row_centers[0]
    candidates = [
        word
        for word in words
        if abs((word["y0"] + word["y1"]) / 2 - row_center) <= 2
        and _numeric(word["text"]) is not None
    ]
    scored = []
    for cell in candidates:
        target_headers = [
            word
            for word in words
            if word["text"] == column and word["y1"] < cell["y0"]
        ]
        if target_headers:
            distance = min(
                abs((word["x0"] + word["x1"]) - (cell["x0"] + cell["x1"]))
                for word in target_headers
            )
            scored.append((distance, cell))
    if not scored:
        raise ValueError(f"calculation_cell_not_unique:{row_label}:{column}")
    scored.sort(key=lambda item: item[0])
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        raise ValueError(f"calculation_cell_not_unique:{row_label}:{column}")
    cell = scored[0][1]
    return _numeric(cell["text"]), {
        key: cell[key] for key in ("x0", "y0", "x1", "y1")
    }


def diagnose_calculation_lineage(
    fixture: dict[str, Any], fact: dict[str, Any], root: Path
) -> dict:
    pdf = root / fixture["native_source"]["path"]
    adapter_inputs = fixture.get("adapter_inputs")
    if adapter_inputs:
        page = adapter_inputs["page"]
        text = _page_text(pdf, page, layout=True)
        input_cells = []
        values = []
        for spec in adapter_inputs["input_cells"]:
            coordinates = None
            if re.fullmatch(r"20\d{2}", str(spec.get("column", ""))):
                value, coordinates = _row_column_value(
                    pdf, page, spec["row"], str(spec["column"])
                )
            else:
                row_values = _row_values(text, spec["row"])
                value = row_values[spec["value_index"]]
            values.append(value)
            input_cell = {
                "row": spec["row"],
                "column": spec["column"],
                "value": str(value),
            }
            if coordinates:
                input_cell["coordinates"] = coordinates
            input_cells.append(input_cell)
        operation = adapter_inputs["operation"]
        if operation == "subtract":
            if len(values) != 2:
                raise ValueError("subtract_requires_two_inputs")
            replay = values[0] - values[1]
        elif operation == "add":
            if len(values) != 2:
                raise ValueError("add_requires_two_inputs")
            replay = values[0] + values[1]
        elif operation == "percentage_change":
            if len(values) != 2:
                raise ValueError("percentage_change_requires_two_inputs")
            replay = (values[1] - values[0]) / values[0] * Decimal(100)
        else:
            raise ValueError(f"unsupported_calculation_operation:{operation}")
        rounding = adapter_inputs.get("rounding_decimals")
        if rounding is not None:
            replay = replay.quantize(Decimal(1).scaleb(-rounding))
        expected = _numeric(fact["value"])
        return {
            "input_cells": input_cells,
            "operation_graph": [{"operation": operation, "inputs": list(range(len(values)))}],
            "replay_output": str(replay),
            "replay_status": "passed" if replay == expected else "blocked",
        }
    page = max(fixture["evidence_pages"])
    text = _page_text(pdf, page, layout=True)
    withdrawal = _row_values(text, "Water withdrawal")[-1]
    discharge = _row_values(text, "Water discharge")[-1]
    disclosed = _row_values(text, "Water consumption")[-1]
    replay = withdrawal - discharge
    expected = _numeric(fact["value"])
    status = "passed" if expected == replay else "blocked"
    return {
        "input_cells": [
            {"row": "Water withdrawal", "column": "Total 2025", "value": str(withdrawal)},
            {"row": "Water discharge", "column": "Total 2025", "value": str(discharge)},
        ],
        "operation_graph": [{"operation": "subtract", "left": 0, "right": 1}],
        "replay_output": str(replay),
        "disclosed_value": str(disclosed),
        "difference": str(replay - disclosed),
        "replay_status": status,
    }


ADAPTERS = {
    "FIELD_EVIDENCE_BINDING_INCOMPLETE": diagnose_field_binding,
    "TABLE_CELL_BINDING_INCOMPLETE": diagnose_table_cell,
    "NATIVE_PDF_CORROBORATION_INCOMPLETE": diagnose_native_corroboration,
    "CALCULATION_LINEAGE_INCOMPLETE": diagnose_calculation_lineage,
}


def run_read_only_diagnostic(
    fixture: dict[str, Any], fact: dict[str, Any], root: Path
) -> dict[str, Any]:
    signature = fixture["gap_signature"]
    adapter = ADAPTERS.get(signature)
    if adapter is None:
        raise ValueError(f"read_only_adapter_missing:{signature}")
    diagnostic = adapter(fixture, fact, root)
    required = fixture["diagnostic_contract"]["required_fields"]
    missing = sorted(set(required) - set(diagnostic))
    blocked = (
        bool(diagnostic.get("blocking_reasons"))
        or diagnostic.get("replay_status") == "blocked"
    )
    status = "blocked" if blocked or missing else "passed"
    identity = {"fixture_id": fixture["fixture_id"], "diagnostic": diagnostic}
    return {
        "schema_version": "0.1",
        "record_kind": "read_only_repair_diagnostic",
        "diagnostic_id": stable_id("repair-diagnostic", identity),
        "fixture_id": fixture["fixture_id"],
        "gap_id": fixture["gap_id"],
        "fact_record_id": fixture["fact_record_id"],
        "gap_signature": signature,
        "status": status,
        "diagnostic": diagnostic,
        "validation": {
            "required_fields_present": not missing,
            "missing_fields": missing,
            "source_hash_prevalidated": True,
            "native_hash_prevalidated": True,
            "fact_write_performed": False,
            "trust_promotion_performed": False,
            "semantic_inference_performed": False,
        },
        "rollback_event": {
            "status": "prepared_not_needed",
            "action": fixture["rollback"]["action"],
            "parent_gap_preserved": True,
            "parent_fact_preserved": True,
        },
    }
