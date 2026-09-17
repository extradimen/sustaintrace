from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .archive import RunArchive, build_model_manifest, verify_run_checksums
from .config import ModelConfig
from .ollama_client import OllamaClient, OllamaError
from .p1_stage_b import stage_b_schema, validate_and_project_stage_b
from .p1_v06_runner import build_v066_packet_from_registry
from .repair_dispatch import StageBHandleClosureError, enforce_stage_b_handle_closure
from .structured_output import parse_strict_json_content


def build_stage_b_packet(
    *, parent_run_directory: str | Path, available_handles: list[dict[str, Any]],
    ontology_path: str | Path, source_registry_path: str | Path,
) -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, str]
]:
    parent = Path(parent_run_directory)
    verify_run_checksums(parent)
    normalized = json.loads((parent / "normalized_output.json").read_text(encoding="utf-8"))
    context = json.loads((parent / "task_context_manifest.json").read_text(encoding="utf-8"))
    if normalized.get("framework_evidence_state") != "supported":
        raise ValueError("stage_b_parent_not_supported")
    model_output = normalized.get("model_output")
    if not isinstance(model_output, dict) or not model_output.get("answer"):
        raise ValueError("stage_b_parent_answer_missing")
    selected = normalized.get("resolved_evidence", [])
    selected_ids = [item.get("source_handle") for item in selected]
    if not selected_ids or len(set(selected_ids)) != len(selected_ids):
        raise ValueError("stage_b_parent_handles_invalid")
    handle_index = {item["handle"]: item for item in available_handles}
    evidence = []
    for archived in selected:
        handle = archived["source_handle"]
        if handle not in handle_index:
            raise ValueError(f"stage_b_parent_handle_not_available:{handle}")
        original = handle_index[handle]
        if archived["verbatim_excerpt"] != original["verbatim_text"]:
            raise ValueError(f"stage_b_parent_verbatim_mismatch:{handle}")
        evidence.append(original)
    ontology = json.loads(Path(ontology_path).read_text(encoding="utf-8"))
    document_ids = {item["source_id"] for item in evidence}
    if len(document_ids) != 1:
        raise ValueError("stage_b_requires_one_source_document")
    document_id = next(iter(document_ids))
    source_registry = json.loads(Path(source_registry_path).read_text(encoding="utf-8"))
    candidates = [
        item for item in source_registry.get("candidates", [])
        if item.get("document_id") == document_id and item.get("eligibility_status") == "eligible"
    ]
    if len(candidates) != 1:
        raise ValueError(f"stage_b_source_entity_not_unique:{document_id}")
    evidence_hashes = {item.get("document_sha256") for item in evidence}
    if evidence_hashes != {candidates[0].get("sha256")}:
        raise ValueError(f"stage_b_source_entity_hash_mismatch:{document_id}")
    subject = {
        "entity_id": f"ENTITY::{document_id}",
        "entity_label": candidates[0]["company"],
    }
    packet = {
        "task_id": context["task_id"],
        "stage_a_answer": model_output["answer"],
        "evidence_blocks": [{
            "handle": item["handle"], "source_id": item["source_id"],
            "page": item["page"], "text": item["verbatim_text"],
            "table_header_context": item.get("table_header_context"),
        } for item in evidence],
        "ontology": {
            "metrics": ontology["metrics"],
            "units": ontology["units"],
            "scopes": ontology["scopes"],
        },
    }
    manifest = {
        "pipeline_version": "P1-PIPELINE-v0.8-STAGE-B-ATOMIC-CLAIM",
        "task_id": context["task_id"],
        "parent_run_id": parent.name,
        "parent_run_directory": str(parent),
        "parent_framework_evidence_state": "supported",
        "selected_evidence_handles": selected_ids,
        "full_report_visible_to_stage_b": False,
        "reference_answer_visible_to_runner": False,
        "framework_subject": subject,
    }
    return packet, manifest, evidence, ontology, subject


def run_p1_stage_b_task(
    *, model_config_path: str | Path, parent_run_directory: str | Path,
    task_pack_path: str | Path, acquisition_manifest_path: str | Path,
    raw_root: str | Path, interventions_root: str | Path,
    registry_path: str | Path, workspace_root: str | Path,
    ontology_path: str | Path, source_registry_path: str | Path,
    system_prompt_path: str | Path,
    archive_root: str | Path, experiment_id: str, run_id: str,
    think: bool | str | None = None,
) -> dict[str, Any]:
    parent_context = json.loads(
        (Path(parent_run_directory) / "task_context_manifest.json").read_text(encoding="utf-8")
    )
    _, _, available_handles = build_v066_packet_from_registry(
        task_pack_path=task_pack_path, task_id=parent_context["task_id"],
        acquisition_manifest_path=acquisition_manifest_path, raw_root=raw_root,
        interventions_root=interventions_root, registry_path=registry_path,
        workspace_root=workspace_root, split_table_rows=True,
    )
    packet, context_manifest, evidence, ontology, subject = build_stage_b_packet(
        parent_run_directory=parent_run_directory,
        available_handles=available_handles, ontology_path=ontology_path,
        source_registry_path=source_registry_path,
    )
    stage_a_output = json.loads(
        (Path(parent_run_directory) / "normalized_output.json").read_text(encoding="utf-8")
    )
    context_manifest["stage_b_handle_closure_preflight"] = enforce_stage_b_handle_closure(
        stage_a_output=stage_a_output,
        stage_b_context=context_manifest,
        projected_output={"validated_claims": []},
        gate_phase="pre_model",
    )
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("P1 Stage B requires a locked model digest")
    prompt = Path(system_prompt_path).read_text(encoding="utf-8").strip()
    schema = stage_b_schema([item["handle"] for item in evidence], ontology)
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
            additional_json={"stage_b_context_manifest.json": context_manifest},
        )
        raise
    model_output: Any = None
    finalized: Any = None
    closure_postflight: dict[str, Any] | None = None
    try:
        model_output = parse_strict_json_content(result.response.get("message", {}).get("content"))
        finalized = validate_and_project_stage_b(
            model_output, evidence, ontology, subject
        )
        closure_postflight = enforce_stage_b_handle_closure(
            stage_a_output=stage_a_output,
            stage_b_context=context_manifest,
            projected_output=finalized,
            gate_phase="pre_knowledge_write",
        )
        errors: list[str] = []
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        if isinstance(error, StageBHandleClosureError):
            closure_postflight = error.audit
            finalized = None
        errors = [f"{type(error).__name__}:{error}"]
    validation = {
        "status": "passed" if not errors else "failed", "errors": errors,
        "reference_answer_visible_to_runner": False,
        "full_report_visible_to_stage_b": False,
        "posthoc_semantic_repair_applied": False,
        "stage_b_handle_closure_postflight": closure_postflight,
    }
    archive.record_result(
        result, model_manifest=model_manifest, normalized_output=finalized,
        redact_request_content=True,
        additional_json={
            "model_generated_content.json": model_output,
            "stage_b_context_manifest.json": context_manifest,
            "validation.json": validation,
        },
    )
    if errors:
        raise OllamaError(
            f"P1 Stage B model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {
        "task_id": context_manifest["task_id"], "run_id": run_id,
        "model": config.model, "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
        "validated_claim_count": len(finalized["validated_claims"]),
    }
