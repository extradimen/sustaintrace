from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpatialNode:
    node_id: str
    kind: str
    text: str
    bbox: tuple[float, float, float, float]
    page: int
    fill: str | None = None


def _center(node: SpatialNode) -> tuple[float, float]:
    x0, y0, x1, y1 = node.bbox
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _contains(container: SpatialNode, contained: SpatialNode) -> bool:
    x0, y0, x1, y1 = container.bbox
    cx, cy = _center(contained)
    return x0 <= cx <= x1 and y0 <= cy <= y1


def build_spatial_relation_graph(
    nodes: Iterable[SpatialNode], *, axis_tolerance: float = 8.0
) -> dict[str, Any]:
    """Build an auditable page-local graph without altering extracted text.

    Relations describe geometric evidence only. Semantic table/chart labels remain
    explicit nodes, so the same graph can be frozen for candidate and reference use.
    """
    ordered = sorted(nodes, key=lambda item: (item.page, item.bbox[1], item.bbox[0], item.node_id))
    if len({item.node_id for item in ordered}) != len(ordered):
        raise ValueError("spatial_node_ids_must_be_unique")
    edges: list[dict[str, Any]] = []
    for index, left in enumerate(ordered):
        lx, ly = _center(left)
        for right in ordered[index + 1 :]:
            if left.page != right.page:
                continue
            rx, ry = _center(right)
            if abs(ly - ry) <= axis_tolerance:
                source, target = (left, right) if lx <= rx else (right, left)
                edges.append({
                    "source": source.node_id,
                    "target": target.node_id,
                    "relation": "same_row_left_of",
                    "distance": round(abs(rx - lx), 6),
                })
            if abs(lx - rx) <= axis_tolerance:
                source, target = (left, right) if ly <= ry else (right, left)
                edges.append({
                    "source": source.node_id,
                    "target": target.node_id,
                    "relation": "same_column_above",
                    "distance": round(abs(ry - ly), 6),
                })
            if left.fill and left.fill == right.fill:
                edges.append({
                    "source": left.node_id,
                    "target": right.node_id,
                    "relation": "same_fill",
                    "fill": left.fill,
                })
            for container, contained in ((left, right), (right, left)):
                if container.kind in {"shape", "cell"} and _contains(
                    container, contained
                ):
                    edges.append({
                        "source": container.node_id,
                        "target": contained.node_id,
                        "relation": "contains_center",
                    })
    for shape in (item for item in ordered if item.kind == "shape"):
        x0, y0, x1, y1 = shape.bbox
        if x1 - x0 > 12 or y1 - y0 > 12:
            continue
        sx, sy = _center(shape)
        right_text = []
        for candidate in ordered:
            if candidate.page != shape.page or candidate.kind not in {"text", "legend"}:
                continue
            cx, cy = _center(candidate)
            if cx > sx and cx - sx <= 120 and abs(cy - sy) <= 14:
                right_text.append((cx - sx + abs(cy - sy), candidate))
        if right_text:
            right_text.sort(key=lambda item: (item[0], item[1].node_id))
            edges.append({
                "source": shape.node_id,
                "target": right_text[0][1].node_id,
                "relation": "nearest_right_text",
                "distance": round(right_text[0][0], 6),
            })
    return {
        "schema_version": "v1.4-spatial-graph-0.1",
        "coordinate_system": "PDF points, origin and axis orientation declared by source parser",
        "nodes": [
            {
                "node_id": item.node_id,
                "kind": item.kind,
                "text": item.text,
                "bbox": list(item.bbox),
                "page": item.page,
                "fill": item.fill,
            }
            for item in ordered
        ],
        "edges": edges,
        "audit_policy": "geometry_only_no_semantic_repair",
    }


def project_table_cell(
    graph: dict[str, Any], *, row_label_id: str, column_header_id: str
) -> dict[str, Any]:
    """Select a cell at the auditable row/column intersection or fail closed."""
    nodes = {item["node_id"]: item for item in graph["nodes"]}
    row = nodes[row_label_id]
    column = nodes[column_header_id]
    row_y = (row["bbox"][1] + row["bbox"][3]) / 2
    column_x = (column["bbox"][0] + column["bbox"][2]) / 2
    candidates = []
    for node in graph["nodes"]:
        if node["kind"] not in {"cell", "value"} or node["page"] != row["page"]:
            continue
        x = (node["bbox"][0] + node["bbox"][2]) / 2
        y = (node["bbox"][1] + node["bbox"][3]) / 2
        candidates.append((abs(x - column_x) + abs(y - row_y), node))
    if not candidates:
        raise ValueError("spatial_cell_not_found")
    candidates.sort(key=lambda item: (item[0], item[1]["node_id"]))
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ValueError("spatial_cell_ambiguous")
    return {
        "cell": candidates[0][1],
        "row_label": row,
        "column_header": column,
        "projection_distance": round(candidates[0][0], 6),
        "graph_schema_version": graph["schema_version"],
    }


def collect_rightward_text(
    graph: dict[str, Any], *, shape_id: str, max_gap: float = 12.0
) -> dict[str, Any]:
    """Collect the visually contiguous label to the right of a small marker."""
    nodes = {item["node_id"]: item for item in graph["nodes"]}
    starts = [
        edge["target"]
        for edge in graph["edges"]
        if edge["source"] == shape_id and edge["relation"] == "nearest_right_text"
    ]
    if len(starts) != 1:
        raise ValueError("marker_right_text_not_unique")
    marker = nodes[shape_id]
    seed = nodes[starts[0]]
    marker_y = (marker["bbox"][1] + marker["bbox"][3]) / 2
    candidates = sorted(
        (
            item for item in graph["nodes"]
            if item["page"] == marker["page"]
            and item["kind"] in {"text", "legend"}
            and abs(((item["bbox"][1] + item["bbox"][3]) / 2) - marker_y) <= 14
            and item["bbox"][0] >= seed["bbox"][0]
        ),
        key=lambda item: (item["bbox"][1], item["bbox"][0], item["node_id"]),
    )
    selected = [seed]
    right = seed["bbox"][2]
    current_y = seed["bbox"][1]
    for candidate in candidates:
        if candidate["node_id"] == seed["node_id"]:
            continue
        if candidate["bbox"][1] - current_y > 4:
            right = seed["bbox"][0]
            current_y = candidate["bbox"][1]
        gap = candidate["bbox"][0] - right
        if gap < -max_gap:
            continue
        if gap > max_gap:
            continue
        selected.append(candidate)
        right = candidate["bbox"][2]
    return {
        "shape": marker,
        "label": " ".join(item["text"] for item in selected),
        "label_nodes": selected,
        "relation": "contiguous_rightward_text",
    }


def project_colored_chart_values(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Join vector series fills, legend labels, and printed numeric values."""
    nodes = {item["node_id"]: item for item in graph["nodes"]}
    marker_labels: dict[str, dict[str, Any]] = {}
    marker_ids = {
        edge["source"] for edge in graph["edges"]
        if edge["relation"] == "nearest_right_text"
    }
    for marker_id in marker_ids:
        marker = nodes[marker_id]
        if marker.get("fill"):
            marker_labels[marker["fill"]] = collect_rightward_text(
                graph, shape_id=marker_id
            )
    contained = {
        edge["source"]: nodes[edge["target"]]
        for edge in graph["edges"]
        if edge["relation"] == "contains_center"
        and nodes[edge["target"]]["kind"] == "value"
    }
    output = []
    for shape in graph["nodes"]:
        x0, y0, x1, y1 = shape["bbox"]
        if shape["kind"] != "shape" or not shape.get("fill") or y1 - y0 <= 12:
            continue
        value = contained.get(shape["node_id"])
        relation = "contains_center"
        if value is None:
            adjacent = []
            for candidate in graph["nodes"]:
                if candidate["kind"] != "value" or candidate["page"] != shape["page"]:
                    continue
                cx = (candidate["bbox"][0] + candidate["bbox"][2]) / 2
                cy = (candidate["bbox"][1] + candidate["bbox"][3]) / 2
                if 0 <= cx - x1 <= 25 and y0 <= cy <= y1:
                    adjacent.append((cx - x1 + abs(cy - y0), candidate))
            if adjacent:
                adjacent.sort(key=lambda item: (item[0], item[1]["node_id"]))
                value = adjacent[0][1]
                relation = "adjacent_right_near_shape_top"
        label = marker_labels.get(shape["fill"])
        if value is not None and label is not None:
            output.append({
                "series_label": label["label"],
                "value_text": value["text"],
                "value_node": value,
                "shape_node": shape,
                "legend_marker": label["shape"],
                "value_relation": relation,
                "fill_relation": "same_fill",
            })
    return output
