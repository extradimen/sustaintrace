from __future__ import annotations

import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_YEAR = re.compile(r"\b20\d{2}\b")


def layout_line_records(xml_text: str) -> list[dict[str, Any]]:
    """Return visible PDF lines with stable coordinates and word geometry."""
    # Poppler's bbox HTML can contain a literal ampersand copied from visible PDF
    # text. Preserve it as text while making the otherwise XML-shaped output
    # parseable; already escaped entities are left untouched.
    xml_text = re.sub(
        r"&(?!#\d+;|#x[0-9A-Fa-f]+;|amp;|lt;|gt;|quot;|apos;)",
        "&amp;",
        xml_text,
    )
    xml_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
    root = ET.fromstring(xml_text)
    records: list[dict[str, Any]] = []
    for line in root.iter():
        if line.tag.rsplit("}", 1)[-1] != "line":
            continue
        words = []
        for word in line.iter():
            if word.tag.rsplit("}", 1)[-1] != "word":
                continue
            text = "".join(word.itertext()).strip()
            if not text:
                continue
            words.append(
                {
                    "text": text,
                    "x_min": float(word.attrib["xMin"]),
                    "x_max": float(word.attrib["xMax"]),
                    "y_min": float(word.attrib["yMin"]),
                    "y_max": float(word.attrib["yMax"]),
                }
            )
        if not words:
            continue
        records.append(
            {
                "line_index": len(records) + 1,
                "text": " ".join(word["text"] for word in words),
                "bbox": [
                    min(word["x_min"] for word in words),
                    min(word["y_min"] for word in words),
                    max(word["x_max"] for word in words),
                    max(word["y_max"] for word in words),
                ],
                "words": words,
            }
        )
    return records


def add_layout_adjacent_context(
    handles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach an immediately preceding explicit-year line to a continued numeric line."""
    augmented = []
    links = []
    for index, item in enumerate(handles):
        copied = dict(item)
        text = item["verbatim_text"].strip()
        if index and re_starts_numeric(text):
            previous = handles[index - 1]
            years = sorted(set(_YEAR.findall(previous["verbatim_text"])))
            if years:
                copied["table_header_context"] = (
                    "Adjacent previous visible line: " + previous["verbatim_text"]
                )
                links.append(
                    {
                        "value_handle": item["handle"],
                        "context_handle": previous["handle"],
                        "explicit_years": years,
                        "rule": "same_page_immediately_preceding_visual_line",
                    }
                )
        augmented.append(copied)
    return augmented, links


def re_starts_numeric(text: str) -> bool:
    return bool(text and text[0].isdigit())


def build_layout_fallback_handles(
    *,
    pdf_path: str | Path,
    pdf_page: int,
    document_id: str,
    document_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Expose all visible lines; selection never uses a hidden expected value."""
    with tempfile.TemporaryDirectory(prefix="esg-rd-layout-") as directory:
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
        records = layout_line_records(output.read_text(encoding="utf-8"))
    handles = []
    for record in records:
        text = record["text"]
        handles.append(
            {
                "handle": f"P{pdf_page:03d}-L{record['line_index']:04d}",
                "source_id": document_id,
                "document_sha256": document_sha256,
                "page": pdf_page,
                "block_type": "native_pdf_layout_line",
                "bbox": record["bbox"],
                "table_header_context": None,
                "verbatim_text": text,
                "normalized_text": " ".join(text.split()),
                "parser": "poppler_pdftotext_bbox_layout",
                "word_geometry": record["words"],
            }
        )
    handles, context_links = add_layout_adjacent_context(handles)
    return handles, {
        "parser": "poppler_pdftotext_bbox_layout",
        "pdf_page": pdf_page,
        "line_count": len(handles),
        "selection_rule": "all_visible_lines_no_hidden_reference_selection",
        "coordinate_system": "PDF points from pdftotext bbox-layout",
        "hidden_reference_value_used": False,
        "adjacent_period_context_links": context_links,
    }
