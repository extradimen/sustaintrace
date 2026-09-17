from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .p1_runner import _load_document, _load_task
from .p1_v06_runner import build_v066_packet_from_registry, resolve_mineru_content_list
from .v11_chart_fallback import build_chart_text_fallback_handle
from .v11_table_cells import table_cell_records


def build_v11_packet(
    *,
    task_pack_path: str | Path,
    task_id: str,
    acquisition_manifest_path: str | Path,
    raw_root: str | Path,
    interventions_root: str | Path,
    registry_path: str | Path,
    workspace_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    packet, context, handles = build_v066_packet_from_registry(
        task_pack_path=task_pack_path,
        task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path,
        raw_root=raw_root,
        interventions_root=interventions_root,
        registry_path=registry_path,
        workspace_root=workspace_root,
        split_table_rows=True,
    )
    task = _load_task(task_pack_path, task_id)
    document = _load_document(acquisition_manifest_path, task["document_id"])
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    root = Path(workspace_root)
    added: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for target in registry["targets"]:
        if task_id not in target["task_ids"]:
            continue
        output = root / target["output_directory"]
        run_path = output / "esg_rd_mineru_run.json"
        content_path = resolve_mineru_content_list(
            output, run_path, document["document_id"]
        )
        blocks = json.loads(content_path.read_text(encoding="utf-8"))
        for block_index, block in enumerate(blocks, start=1):
            if block.get("type") != "table" or not block.get("table_body"):
                continue
            for cell in table_cell_records(block["table_body"]):
                text = cell["text"]
                header = " | ".join(
                    filter(None, [cell["column_header"], cell["semantic_row_context"]])
                )
                added.append(
                    {
                        "handle": (
                            f"M{target['pdf_page']:03d}-T{block_index:04d}"
                            f"-R{cell['row_index']:04d}-C{cell['column_index']:04d}"
                        ),
                        "source_id": document["document_id"],
                        "document_sha256": document["sha256"],
                        "page": target["pdf_page"],
                        "block_type": "table_cell",
                        "bbox": block.get("bbox"),
                        "table_header_context": header,
                        "verbatim_text": text,
                        "normalized_text": " ".join(text.split()),
                        "parser": "MinerU+v1.1-cell-splitter",
                        "parser_run_sha256": sha256_file(run_path),
                        "content_list_sha256": sha256_file(content_path),
                    }
                )
        has_unparsed_chart = any(
            block.get("type") in {"chart", "table"}
            and not block.get("text")
            and not block.get("table_body")
            for block in blocks
        )
        if has_unparsed_chart:
            fallback, record = build_chart_text_fallback_handle(
                pdf_path=Path(raw_root) / document["local_path"],
                pdf_page=target["pdf_page"],
                question=task["question"],
                document_id=document["document_id"],
                document_sha256=document["sha256"],
            )
            provenance.append(record)
            if fallback is not None:
                added.append(fallback)
    handles.extend(added)
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
    context["pipeline_version"] = "ESG-RD-v1.1-TABLE-AND-PERIOD"
    context["v11_added_handle_count"] = len(added)
    context["chart_fallback_provenance"] = provenance
    return packet, context, handles
