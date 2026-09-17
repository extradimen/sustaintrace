from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .archive import RunArchive, build_model_manifest
from .config import ModelConfig
from .hashing import sha256_file
from .ollama_client import OllamaClient, OllamaError
from .p1_mineru_blocks import load_mineru_block_handles
from .p1_runner import _load_document, _load_task
from .p1_v04 import build_line_evidence_handles, finalize_v04_output, task_conditioned_schema
from .structured_output import parse_strict_json_content


def resolve_mineru_content_list(
    output_dir: Path, run_record: Path, document_id: str
) -> Path:
    """Resolve the recorded MinerU artifact while retaining legacy layout support."""
    run_payload = json.loads(run_record.read_text(encoding="utf-8"))
    candidates = [
        output_dir / item["path"]
        for item in run_payload.get("output_files", [])
        if item.get("path", "").endswith("_content_list.json")
    ]
    if len(candidates) == 1 and candidates[0].is_file():
        return candidates[0]
    legacy = output_dir / document_id / "auto" / f"{document_id}_content_list.json"
    if legacy.is_file():
        return legacy
    raise ValueError("MinerU content list missing or ambiguous")


def _resolve_registry_artifacts(
    *, registry_path: str | Path, workspace_root: str | Path, task_id: str,
    document_id: str, document_sha256: str, target_pages: list[int],
) -> list[dict[str, Any]]:
    registry_file = Path(registry_path)
    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    root = Path(workspace_root)
    by_page: dict[int, dict[str, Any]] = {}
    for target in registry.get("targets", []):
        if task_id not in target.get("task_ids", []):
            continue
        if target.get("document_id") != document_id:
            raise ValueError(f"MinerU registry document mismatch: {target.get('target_id')}")
        if target.get("document_sha256") != document_sha256:
            raise ValueError(f"MinerU registry source hash mismatch: {target.get('target_id')}")
        page = target.get("pdf_page")
        if page not in target_pages or not isinstance(page, int):
            continue
        output_dir = root / target["output_directory"]
        run_record = output_dir / "esg_rd_mineru_run.json"
        if not run_record.is_file():
            raise ValueError(f"MinerU registry artifact missing: {target.get('target_id')}")
        try:
            content_list = resolve_mineru_content_list(
                output_dir, run_record, document_id
            )
        except ValueError as error:
            raise ValueError(
                f"MinerU registry content list missing or ambiguous: "
                f"{target.get('target_id')}"
            ) from error
        actual_run_hash = sha256_file(run_record)
        if actual_run_hash != target.get("run_record_sha256"):
            raise ValueError(f"MinerU registry run hash mismatch: {target.get('target_id')}")
        if page in by_page:
            raise ValueError(f"Duplicate MinerU registry target page: {page}")
        by_page[page] = {
            "target_id": target["target_id"],
            "pdf_page": page,
            "content_list_path": content_list,
            "run_record_path": run_record,
        }
    missing = sorted(set(target_pages) - set(by_page))
    if missing:
        raise ValueError(f"MinerU registry missing target pages: {missing}")
    return [by_page[page] for page in sorted(by_page)]


def build_v066_packet_from_registry(
    *, task_pack_path: str | Path, task_id: str,
    acquisition_manifest_path: str | Path, raw_root: str | Path,
    interventions_root: str | Path, registry_path: str | Path,
    workspace_root: str | Path, split_table_rows: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    task = _load_task(task_pack_path, task_id)
    document = _load_document(acquisition_manifest_path, task["document_id"])
    pdf_path = Path(raw_root) / document["local_path"]
    if sha256_file(pdf_path) != document["sha256"]:
        raise ValueError(f"Source hash mismatch: {document['document_id']}")
    artifacts = _resolve_registry_artifacts(
        registry_path=registry_path, workspace_root=workspace_root, task_id=task_id,
        document_id=document["document_id"], document_sha256=document["sha256"],
        target_pages=task["target_pages"],
    )
    handles: list[dict[str, Any]] = []
    for artifact in artifacts:
        handles.extend(load_mineru_block_handles(
            content_list_path=artifact["content_list_path"],
            run_record_path=artifact["run_record_path"],
            document_id=document["document_id"], document_sha256=document["sha256"],
            target_pdf_pages=[artifact["pdf_page"]], split_table_rows=split_table_rows,
        ))
    intervention_id = task.get("controlled_intervention_id")
    if intervention_id:
        intervention_path = Path(interventions_root) / f"{intervention_id}.json"
        intervention = json.loads(intervention_path.read_text(encoding="utf-8"))
        if intervention["source_document_sha256"] != document["sha256"]:
            raise ValueError(f"Controlled intervention hash mismatch: {intervention_id}")
        handles.extend(build_line_evidence_handles(
            intervention_id, 1, intervention["injected_text"], controlled=True
        ))
    packet = {
        "task_id": task_id, "task_type": task["task_type"],
        "question": task["question"],
        "evidence_blocks": [{
            "handle": item["handle"], "source_id": item["source_id"],
            "page": item["page"],
            "block_type": item.get("block_type", "controlled_note"),
            "bbox": item.get("bbox"),
            "table_header_context": item.get("table_header_context"),
            "text": item["verbatim_text"],
        } for item in handles],
    }
    artifact_manifest = [{
        "target_id": item["target_id"], "pdf_page": item["pdf_page"],
        "content_list_sha256": sha256_file(item["content_list_path"]),
        "run_record_sha256": sha256_file(item["run_record_path"]),
    } for item in artifacts]
    manifest = {
        "pipeline_version": "P1-PIPELINE-v0.6.6-MULTIPAGE-MINERU",
        "task_id": task_id, "task_type": task["task_type"],
        "document_id": document["document_id"], "document_sha256": document["sha256"],
        "target_pages": task["target_pages"],
        "controlled_intervention_id": intervention_id,
        "evidence_handle_count": len(handles), "mineru_artifacts": artifact_manifest,
        "mineru_registry_sha256": sha256_file(registry_path),
        "reference_answer_visible_to_runner": False,
    }
    return packet, manifest, handles


def build_v06_packet(
    *, task_pack_path: str | Path, task_id: str,
    acquisition_manifest_path: str | Path, raw_root: str | Path,
    interventions_root: str | Path, mineru_content_list_path: str | Path,
    mineru_run_record_path: str | Path,
    split_table_rows: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    task = _load_task(task_pack_path, task_id)
    document = _load_document(acquisition_manifest_path, task["document_id"])
    pdf_path = Path(raw_root) / document["local_path"]
    if sha256_file(pdf_path) != document["sha256"]:
        raise ValueError(f"Source hash mismatch: {document['document_id']}")
    handles = load_mineru_block_handles(
        content_list_path=mineru_content_list_path,
        run_record_path=mineru_run_record_path,
        document_id=document["document_id"],
        document_sha256=document["sha256"],
        target_pdf_pages=task["target_pages"],
        split_table_rows=split_table_rows,
    )
    intervention_id = task.get("controlled_intervention_id")
    if intervention_id:
        intervention_path = Path(interventions_root) / f"{intervention_id}.json"
        intervention = json.loads(intervention_path.read_text(encoding="utf-8"))
        if intervention["source_document_sha256"] != document["sha256"]:
            raise ValueError(f"Controlled intervention hash mismatch: {intervention_id}")
        handles.extend(
            build_line_evidence_handles(
                intervention_id, 1, intervention["injected_text"], controlled=True
            )
        )
    packet = {
        "task_id": task_id,
        "task_type": task["task_type"],
        "question": task["question"],
        "evidence_blocks": [
            {
                "handle": item["handle"],
                "source_id": item["source_id"],
                "page": item["page"],
                "block_type": item.get("block_type", "controlled_note"),
                "bbox": item.get("bbox"),
                "table_header_context": item.get("table_header_context"),
                "text": item["verbatim_text"],
            }
            for item in handles
        ],
    }
    manifest = {
        "pipeline_version": "P1-PIPELINE-v0.6-MINERU-BLOCKS",
        "task_id": task_id,
        "task_type": task["task_type"],
        "document_id": document["document_id"],
        "document_sha256": document["sha256"],
        "target_pages": task["target_pages"],
        "controlled_intervention_id": intervention_id,
        "evidence_handle_count": len(handles),
        "mineru_content_list_sha256": sha256_file(mineru_content_list_path),
        "mineru_run_record_sha256": sha256_file(mineru_run_record_path),
        "reference_answer_visible_to_runner": False,
    }
    return packet, manifest, handles


def run_p1_v06_task(
    *, model_config_path: str | Path, task_pack_path: str | Path, task_id: str,
    acquisition_manifest_path: str | Path, raw_root: str | Path,
    interventions_root: str | Path, mineru_content_list_path: str | Path,
    mineru_run_record_path: str | Path, system_prompt_path: str | Path,
    archive_root: str | Path, experiment_id: str, run_id: str,
    think: bool | str | None = None,
    split_table_rows: bool = False,
) -> dict[str, Any]:
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("P1 v0.6 requires a locked model digest")
    packet, context_manifest, handles = build_v06_packet(
        task_pack_path=task_pack_path, task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path, raw_root=raw_root,
        interventions_root=interventions_root,
        mineru_content_list_path=mineru_content_list_path,
        mineru_run_record_path=mineru_run_record_path,
        split_table_rows=split_table_rows,
    )
    prompt = Path(system_prompt_path).read_text(encoding="utf-8").strip()
    schema = task_conditioned_schema(
        context_manifest["task_type"], [item["handle"] for item in handles]
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
    ]
    client = OllamaClient(config)
    digest = client.verify_digest()
    if digest != config.expected_digest:
        raise OllamaError(f"Locked model not available: {config.model}")
    model_manifest = build_model_manifest(config.public_dict(), client.show_model(), digest)
    archive = RunArchive.create(archive_root, experiment_id, run_id)
    request = client.build_chat_payload(messages, schema=schema, think=think)
    started = time.perf_counter()
    try:
        result = client.chat(messages, schema=schema, think=think)
    except Exception as error:
        archive.record_failure(
            request=request, error=error, elapsed_seconds=time.perf_counter() - started,
            model_manifest=model_manifest, stage="model_chat", redact_request_content=True,
            additional_json={"task_context_manifest.json": context_manifest},
        )
        raise
    model_output: Any = None
    finalized: Any = None
    try:
        model_output = parse_strict_json_content(result.response.get("message", {}).get("content"))
        finalized = finalize_v04_output(
            model_output, context_manifest["task_type"], handles
        )
        errors: list[str] = []
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        errors = [f"{type(error).__name__}:{error}"]
    validation = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "reference_answer_visible_to_runner": False,
        "posthoc_semantic_repair_applied": False,
    }
    archive.record_result(
        result, model_manifest=model_manifest, normalized_output=finalized,
        redact_request_content=True,
        additional_json={
            "model_generated_content.json": model_output,
            "task_context_manifest.json": context_manifest,
            "validation.json": validation,
        },
    )
    if errors:
        raise OllamaError(
            f"P1 v0.6 model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "model": config.model,
        "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
    }


def run_p1_v066_task(
    *, model_config_path: str | Path, task_pack_path: str | Path, task_id: str,
    acquisition_manifest_path: str | Path, raw_root: str | Path,
    interventions_root: str | Path, registry_path: str | Path,
    workspace_root: str | Path, system_prompt_path: str | Path,
    archive_root: str | Path, experiment_id: str, run_id: str,
    think: bool | str | None = None,
) -> dict[str, Any]:
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("P1 v0.6.6 requires a locked model digest")
    packet, context_manifest, handles = build_v066_packet_from_registry(
        task_pack_path=task_pack_path, task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path, raw_root=raw_root,
        interventions_root=interventions_root, registry_path=registry_path,
        workspace_root=workspace_root, split_table_rows=True,
    )
    prompt = Path(system_prompt_path).read_text(encoding="utf-8").strip()
    schema = task_conditioned_schema(
        context_manifest["task_type"], [item["handle"] for item in handles]
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
    ]
    client = OllamaClient(config)
    digest = client.verify_digest()
    if digest != config.expected_digest:
        raise OllamaError(f"Locked model not available: {config.model}")
    model_manifest = build_model_manifest(config.public_dict(), client.show_model(), digest)
    archive = RunArchive.create(archive_root, experiment_id, run_id)
    request = client.build_chat_payload(messages, schema=schema, think=think)
    started = time.perf_counter()
    try:
        result = client.chat(messages, schema=schema, think=think)
    except Exception as error:
        archive.record_failure(
            request=request, error=error, elapsed_seconds=time.perf_counter() - started,
            model_manifest=model_manifest, stage="model_chat", redact_request_content=True,
            additional_json={"task_context_manifest.json": context_manifest},
        )
        raise
    model_output: Any = None
    finalized: Any = None
    try:
        model_output = parse_strict_json_content(result.response.get("message", {}).get("content"))
        finalized = finalize_v04_output(model_output, context_manifest["task_type"], handles)
        errors: list[str] = []
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        errors = [f"{type(error).__name__}:{error}"]
    validation = {
        "status": "passed" if not errors else "failed", "errors": errors,
        "reference_answer_visible_to_runner": False,
        "posthoc_semantic_repair_applied": False,
    }
    archive.record_result(
        result, model_manifest=model_manifest, normalized_output=finalized,
        redact_request_content=True,
        additional_json={
            "model_generated_content.json": model_output,
            "task_context_manifest.json": context_manifest,
            "validation.json": validation,
        },
    )
    if errors:
        raise OllamaError(
            f"P1 v0.6.6 model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {
        "task_id": task_id, "run_id": run_id, "model": config.model,
        "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
    }
