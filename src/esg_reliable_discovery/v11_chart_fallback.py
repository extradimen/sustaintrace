from __future__ import annotations

import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_METRIC = re.compile(r"\bscope\s*([123])\b", re.IGNORECASE)
_NUMBER = re.compile(r"^\d[\d,]*(?:\.\d+)?$")


def _words(root: ET.Element) -> list[dict[str, Any]]:
    result = []
    for word in root.iter():
        if word.tag.rsplit("}", 1)[-1] != "word":
            continue
        text = "".join(word.itertext()).strip()
        if not text:
            continue
        result.append(
            {
                "text": text,
                "x_min": float(word.attrib["xMin"]),
                "x_max": float(word.attrib["xMax"]),
                "y_min": float(word.attrib["yMin"]),
                "height": float(word.attrib["yMax"]) - float(word.attrib["yMin"]),
            }
        )
    return result


def select_exact_scope_row_from_bbox_xml(xml_text: str, question: str) -> dict[str, Any] | None:
    """Select a visible exact Scope row without using an expected answer value."""
    requested = _METRIC.search(question)
    if not requested:
        return None
    metric = f"scope {requested.group(1)}"
    words = _words(ET.fromstring(xml_text))
    candidates = []
    for scope_word in words:
        if scope_word["text"].casefold() != "scope":
            continue
        metric_numbers = [
            word
            for word in words
            if word["text"] == requested.group(1)
            and 0 <= word["x_min"] - scope_word["x_max"] <= 12
            and abs(word["y_min"] - scope_word["y_min"]) <= 0.8
        ]
        if not metric_numbers:
            continue
        metric_number = max(metric_numbers, key=lambda word: word["height"])
        for value in words:
            if value["x_min"] <= metric_number["x_max"]:
                continue
            if abs(value["y_min"] - scope_word["y_min"]) > 0.8:
                continue
            if not _NUMBER.fullmatch(value["text"]):
                continue
            candidates.append(
                {
                    "metric_text": metric.title(),
                    "value_text": value["text"],
                    "y_min": scope_word["y_min"],
                    "font_height": min(
                        scope_word["height"], metric_number["height"], value["height"]
                    ),
                    "horizontal_distance": value["x_min"] - scope_word["x_min"],
                }
            )
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (-item["font_height"], item["horizontal_distance"], item["y_min"])
    )
    selected = candidates[0]
    selected["selection_rule"] = (
        "exact_question_metric_same_baseline_right_numeric_largest_visible_font"
    )
    selected["candidate_count"] = len(candidates)
    return selected


def build_chart_text_fallback_handle(
    *,
    pdf_path: str | Path,
    pdf_page: int,
    question: str,
    document_id: str,
    document_sha256: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="esg-rd-bbox-") as directory:
        output = Path(directory) / "page.html"
        subprocess.run(
            [
                "pdftotext",
                "-f",
                str(pdf_page),
                "-l",
                str(pdf_page),
                "-bbox-layout",
                str(pdf_path),
                str(output),
            ],
            check=True,
            capture_output=True,
        )
        selected = select_exact_scope_row_from_bbox_xml(
            output.read_text(encoding="utf-8"), question
        )
    provenance = {
        "parser": "poppler_pdftotext_bbox_layout",
        "pdf_page": pdf_page,
        "selection": selected,
        "hidden_reference_value_used": False,
    }
    if selected is None:
        return None, provenance
    text = f"{selected['metric_text']} | {selected['value_text']} metric tons CO2e"
    handle = {
        "handle": f"P{pdf_page:03d}-XROW0001",
        "source_id": document_id,
        "document_sha256": document_sha256,
        "page": pdf_page,
        "block_type": "chart_text_fallback_row",
        "bbox": None,
        "table_header_context": "Metric | Amount (metric tons CO2e)",
        "verbatim_text": text,
        "normalized_text": text,
    }
    return handle, provenance
