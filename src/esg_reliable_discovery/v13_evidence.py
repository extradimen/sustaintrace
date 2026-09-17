from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .layout_fallback import build_layout_fallback_handles
from .v11_evidence import build_v11_packet


def build_v13_packet(
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
    packet, context, handles = build_v11_packet(
        task_pack_path=task_pack_path,
        task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path,
        raw_root=raw_root,
        interventions_root=interventions_root,
        registry_path=registry_path,
        workspace_root=workspace_root,
    )
    layout_registry = json.loads(Path(layout_registry_path).read_text(encoding="utf-8"))
    targets = [item for item in layout_registry["targets"] if item["task_id"] == task_id]
    provenance = []
    added = []
    root = Path(workspace_root)
    for target in targets:
        fallback, record = build_layout_fallback_handles(
            pdf_path=root / target["pdf_path"],
            pdf_page=target["pdf_page"],
            document_id=target["document_id"],
            document_sha256=target["document_sha256"],
        )
        added.extend(fallback)
        provenance.append(record)
    existing = {item["handle"] for item in handles}
    handles.extend(item for item in added if item["handle"] not in existing)
    packet["evidence_blocks"] = [
        {
            "handle": item["handle"],
            "source_id": item["source_id"],
            "page": item["page"],
            "block_type": item.get("block_type"),
            "bbox": item.get("bbox"),
            "table_header_context": item.get("table_header_context"),
            "text": item["verbatim_text"],
        }
        for item in handles
    ]
    context["pipeline_version"] = "ESG-RD-v1.3-DUAL-PARSER-EVIDENCE"
    context["layout_fallback_provenance"] = provenance
    context["layout_fallback_handle_count"] = len(added)
    context["layout_registry_path"] = str(layout_registry_path)
    return packet, context, handles
