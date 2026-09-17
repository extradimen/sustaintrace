from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .v13_evidence import build_v13_packet
from .v14_pdf_vector import graph_pdf_page_vectors
from .v15_grounding import bind_period_headers_from_spatial_graph


def build_v15_packet(
    *,
    task_pack_path: str | Path,
    task_id: str,
    acquisition_manifest_path: str | Path,
    raw_root: str | Path,
    interventions_root: str | Path,
    registry_path: str | Path,
    workspace_root: str | Path,
    layout_registry_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Build v1.3 evidence plus auditable native-PDF period bindings."""
    packet, context, handles = build_v13_packet(
        task_pack_path=task_pack_path,
        task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path,
        raw_root=raw_root,
        interventions_root=interventions_root,
        registry_path=registry_path,
        workspace_root=workspace_root,
        layout_registry_path=layout_registry_path,
    )
    task_pack = json.loads(Path(task_pack_path).read_text(encoding="utf-8"))
    task = next(item for item in task_pack["tasks"] if item["task_id"] == task_id)
    acquisition = json.loads(Path(acquisition_manifest_path).read_text(encoding="utf-8"))
    document = next(
        item for item in acquisition["documents"]
        if item["document_id"] == task["document_id"]
    )
    pdf_path = Path(raw_root) / document["local_path"]
    all_bindings: list[dict[str, Any]] = []
    augmented = handles
    graph_records = []
    for page in sorted(set(task["target_pages"])):
        graph = graph_pdf_page_vectors(pdf_path, page)
        augmented, bindings = bind_period_headers_from_spatial_graph(augmented, graph)
        all_bindings.extend(bindings)
        graph_records.append({
            "page": page,
            "schema_version": graph["schema_version"],
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "extractors": graph["extractors"],
        })
    packet["evidence_blocks"] = [
        {
            "handle": item["handle"],
            "source_id": item["source_id"],
            "page": item["page"],
            "block_type": item.get("block_type"),
            "bbox": item.get("bbox"),
            "table_header_context": item.get("table_header_context"),
            "period_header_context": item.get("period_header_context"),
            "text": item["verbatim_text"],
        }
        for item in augmented
    ]
    context["pipeline_version"] = "ESG-RD-v1.5-AUDITABLE-GROUNDING"
    context["period_header_bindings"] = all_bindings
    context["native_pdf_graph_records"] = graph_records
    return packet, context, augmented
