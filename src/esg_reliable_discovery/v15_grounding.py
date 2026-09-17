from __future__ import annotations

import re
import unicodedata
from typing import Any

_YEAR = re.compile(r"(?:19|20|21|22)\d{2}")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "＇": "'"})
_QUOTATION_MARKS = str.maketrans({"“": '"', "”": '"', "„": '"', "‟": '"'})


def comparison_form(value: str) -> str:
    """Return a conservative comparison-only form while preserving source text."""
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.translate(_APOSTROPHES).translate(_QUOTATION_MARKS).split())


def unicode_equivalent_substring(verbatim: str, source: str) -> bool:
    return comparison_form(verbatim) in comparison_form(source)


def bind_period_headers_from_spatial_graph(
    handles: list[dict[str, Any]],
    graph: dict[str, Any],
    *,
    x_tolerance: float = 15.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Bind unique numeric table cells to the nearest explicit year above.

    The binding is geometry-only and fails closed on ambiguous value-node matches.
    Original evidence text is never changed.
    """
    nodes = graph.get("nodes", [])
    output: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    for handle in handles:
        copied = dict(handle)
        if handle.get("block_type") != "table_cell":
            output.append(copied)
            continue
        text = " ".join(str(handle.get("normalized_text", "")).split())
        value_nodes = [
            node
            for node in nodes
            if node.get("page") == handle.get("page")
            and " ".join(str(node.get("text", "")).split()) == text
            and node.get("kind") == "value"
        ]
        if len(value_nodes) != 1:
            output.append(copied)
            continue
        value_node = value_nodes[0]
        vx = (value_node["bbox"][0] + value_node["bbox"][2]) / 2
        vy = (value_node["bbox"][1] + value_node["bbox"][3]) / 2
        candidates = []
        for node in nodes:
            if node.get("page") != handle.get("page") or not _YEAR.fullmatch(
                str(node.get("text", ""))
            ):
                continue
            hx = (node["bbox"][0] + node["bbox"][2]) / 2
            hy = (node["bbox"][1] + node["bbox"][3]) / 2
            if hy < vy and abs(hx - vx) <= x_tolerance:
                candidates.append((vy - hy, abs(hx - vx), node))
        if not candidates:
            output.append(copied)
            continue
        candidates.sort(key=lambda item: (item[0], item[1], item[2]["node_id"]))
        header = candidates[0][2]
        copied["period_header_context"] = header["text"]
        copied["period_header_binding"] = {
            "value_node_id": value_node["node_id"],
            "header_node_id": header["node_id"],
            "relation": "same_column_nearest_explicit_year_above",
            "x_delta": round(candidates[0][1], 6),
            "y_delta": round(candidates[0][0], 6),
            "graph_schema_version": graph.get("schema_version"),
        }
        bindings.append({"evidence_handle": handle["handle"], **copied["period_header_binding"]})
        output.append(copied)
    return output, bindings
