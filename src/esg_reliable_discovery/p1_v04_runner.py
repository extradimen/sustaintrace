from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .archive import RunArchive, build_model_manifest
from .config import ModelConfig
from .hashing import sha256_file
from .ollama_client import OllamaClient, OllamaError
from .p1_runner import _load_document, _load_task, extract_target_pages
from .p1_v04 import (
    build_line_evidence_handles,
    finalize_v04_output,
    task_conditioned_schema,
)
from .structured_output import parse_strict_json_content


def build_v04_packet(
    *, task_pack_path: str | Path, task_id: str,
    acquisition_manifest_path: str | Path, raw_root: str | Path,
    interventions_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    task = _load_task(task_pack_path, task_id)
    document = _load_document(acquisition_manifest_path, task["document_id"])
    pdf_path = Path(raw_root) / document["local_path"]
    if sha256_file(pdf_path) != document["sha256"]:
        raise ValueError(f"Source hash mismatch: {document['document_id']}")
    pages = extract_target_pages(pdf_path, task["target_pages"])
    handles: list[dict[str, Any]] = []
    for page, text in pages.items():
        handles.extend(build_line_evidence_handles(document["document_id"], page, text))
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
    visible_lines = [
        {"handle": item["handle"], "source_id": item["source_id"],
         "page": item["page"], "text": item["verbatim_text"]}
        for item in handles
    ]
    packet = {
        "task_id": task_id,
        "task_type": task["task_type"],
        "question": task["question"],
        "evidence_lines": visible_lines,
    }
    manifest = {
        "pipeline_version": "P1-PIPELINE-v0.4",
        "task_id": task_id,
        "task_type": task["task_type"],
        "document_id": document["document_id"],
        "document_sha256": document["sha256"],
        "target_pages": task["target_pages"],
        "controlled_intervention_id": intervention_id,
        "evidence_handle_count": len(handles),
        "reference_answer_visible_to_runner": False,
    }
    return packet, manifest, handles


def run_p1_v04_task(
    *, model_config_path: str | Path, task_pack_path: str | Path, task_id: str,
    acquisition_manifest_path: str | Path, raw_root: str | Path,
    interventions_root: str | Path, system_prompt_path: str | Path,
    archive_root: str | Path, experiment_id: str, run_id: str,
    think: bool | str | None = None,
) -> dict[str, Any]:
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("P1 v0.4 requires a locked model digest")
    packet, context_manifest, handles = build_v04_packet(
        task_pack_path=task_pack_path, task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path, raw_root=raw_root,
        interventions_root=interventions_root,
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
            f"P1 v0.4 model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "model": config.model,
        "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
    }
