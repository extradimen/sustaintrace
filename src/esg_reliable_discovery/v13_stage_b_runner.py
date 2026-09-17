from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from .archive import RunArchive, build_model_manifest, verify_run_checksums
from .config import ModelConfig
from .ollama_client import OllamaClient, OllamaError
from .repair_dispatch import StageBHandleClosureError, enforce_stage_b_handle_closure
from .structured_output import parse_strict_json_content
from .v13_atomic_projection import slot_output_schema, validate_and_project_slots
from .v13_evidence import build_v13_packet
from .v15_evidence import build_v15_packet
from .v20_contracts import (
    require_controlled_conflict_slots,
    validate_evidence_handle_pages,
    validate_slot_contracts_before_candidate,
)
from .v21_contract_adapters import (
    flatten_object_contracts,
    validate_and_project_slots_v21,
)
from .v22_preflight import dry_run_stage_b_contracts_v22
from .v24_integrity import dry_run_stage_b_contracts_v24, validate_layout_registry_v24
from .v25_integrity import select_single_block_ordered_spans_v25
from .v26_integrity import (
    project_atomic_slots_v26,
    select_semantic_single_block_spans_v26,
)
from .v27_integrity import build_handle_alias_catalog_v27, resolve_handle_aliases_v27


def run_v13_stage_b_task(
    *,
    model_config_path: str | Path,
    parent_run_directory: str | Path,
    task_pack_path: str | Path,
    acquisition_manifest_path: str | Path,
    raw_root: str | Path,
    interventions_root: str | Path,
    registry_path: str | Path,
    workspace_root: str | Path,
    layout_registry_path: str | Path,
    source_registry_path: str | Path,
    slot_contracts_path: str | Path,
    semantic_qualifiers_path: str | Path | None = None,
    system_prompt_path: str | Path,
    archive_root: str | Path,
    experiment_id: str,
    run_id: str,
    think: bool | str | None = None,
    use_v15_grounding: bool = False,
    use_v20_contract_gate: bool = False,
    required_conflict_slot_ids: list[str] | None = None,
    use_v21_contract_adapters: bool = False,
    use_v22_preflight: bool = False,
    use_v24_preflight: bool = False,
    use_v24_layout_gate: bool = False,
    use_v25_single_block_ordered_spans: bool = False,
    use_v26_atomic_projection: bool = False,
    use_v26_semantic_single_block_spans: bool = False,
    use_v27_handle_aliases: bool = False,
) -> dict[str, Any]:
    parent = Path(parent_run_directory)
    verify_run_checksums(parent)
    if use_v24_layout_gate:
        layout_registry = json.loads(Path(layout_registry_path).read_text(encoding="utf-8"))
        validate_layout_registry_v24(layout_registry.get("targets", []))
    parent_context = json.loads((parent / "task_context_manifest.json").read_text(encoding="utf-8"))
    task_id = parent_context["task_id"]
    evidence_builder = build_v15_packet if use_v15_grounding else build_v13_packet
    _, _, available_handles = evidence_builder(
        task_pack_path=task_pack_path,
        task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path,
        raw_root=raw_root,
        interventions_root=interventions_root,
        registry_path=registry_path,
        workspace_root=workspace_root,
        layout_registry_path=layout_registry_path,
    )
    normalized = json.loads((parent / "normalized_output.json").read_text(encoding="utf-8"))
    if normalized.get("framework_evidence_state") != "supported":
        raise ValueError("v13_stage_b_parent_not_supported")
    answer = normalized.get("model_output", {}).get("answer")
    if answer is None:
        raise ValueError("v13_stage_b_parent_answer_missing")
    selected = normalized.get("resolved_evidence", [])
    handle_index = {item["handle"]: item for item in available_handles}
    evidence = []
    for archived in selected:
        handle = archived["source_handle"]
        original = handle_index.get(handle)
        if original is None:
            raise ValueError(f"v13_parent_handle_not_available:{handle}")
        if archived["verbatim_excerpt"] != original["verbatim_text"]:
            raise ValueError(f"v13_parent_verbatim_mismatch:{handle}")
        evidence.append(original)
    if not evidence:
        raise ValueError("v13_stage_b_parent_evidence_empty")
    document_ids = {item["source_id"] for item in evidence}
    if len(document_ids) != 1:
        raise ValueError("v13_stage_b_requires_one_source_document")
    document_id = next(iter(document_ids))
    registry = json.loads(Path(source_registry_path).read_text(encoding="utf-8"))
    candidates = [
        item
        for item in registry["candidates"]
        if item["document_id"] == document_id and item["eligibility_status"] == "eligible"
    ]
    if len(candidates) != 1:
        raise ValueError(f"v13_source_entity_not_unique:{document_id}")
    subject = {
        "entity_id": f"ENTITY::{document_id}",
        "entity_label": candidates[0]["company"],
    }
    contracts = json.loads(Path(slot_contracts_path).read_text(encoding="utf-8"))["contracts"]
    required_slots = contracts.get(task_id)
    if not required_slots:
        raise ValueError(f"v13_slot_contract_missing:{task_id}")
    required_slots = [dict(item) for item in required_slots]
    if semantic_qualifiers_path is not None:
        qualifier_registry = json.loads(Path(semantic_qualifiers_path).read_text(encoding="utf-8"))[
            "qualifiers"
        ]
        task_qualifiers = qualifier_registry.get(task_id, {})
        for slot in required_slots:
            slot.update(task_qualifiers.get(slot["slot_id"], {}))
    if use_v21_contract_adapters:
        required_slots = flatten_object_contracts(required_slots)
    v25_contract_selection = None
    v26_contract_selection = None
    if use_v26_semantic_single_block_spans:
        required_slots, v26_contract_selection = select_semantic_single_block_spans_v26(
            required_slots, evidence
        )
    elif use_v25_single_block_ordered_spans:
        required_slots, v25_contract_selection = select_single_block_ordered_spans_v25(
            required_slots, evidence
        )
    v22_preflight = None
    if use_v24_preflight:
        v22_preflight = dry_run_stage_b_contracts_v24(required_slots)
    elif use_v22_preflight:
        v22_preflight = dry_run_stage_b_contracts_v22(required_slots)
    contract_gate = None
    if use_v20_contract_gate:
        contract_gate = validate_slot_contracts_before_candidate(required_slots)
        require_controlled_conflict_slots(required_slots, required_conflict_slot_ids or [])
        contract_gate["evidence_handle_page_audit"] = validate_evidence_handle_pages(evidence)
    alias_catalog = (
        build_handle_alias_catalog_v27([item["handle"] for item in evidence])
        if use_v27_handle_aliases
        else {}
    )
    reverse_alias_catalog = {handle: alias for alias, handle in alias_catalog.items()}
    packet = {
        "task_id": task_id,
        "stage_a_answer": answer,
        "required_slot_contracts": required_slots,
        "evidence_blocks": [
            {
                "handle": reverse_alias_catalog.get(item["handle"], item["handle"]),
                "source_id": item["source_id"],
                "page": item["page"],
                "text": item["verbatim_text"],
                "adjacent_context": item.get("table_header_context"),
            }
            for item in evidence
        ],
    }
    context = {
        "pipeline_version": "ESG-RD-v1.3-SLOT-ATOMIC-PROJECTION",
        "task_id": task_id,
        "parent_run_directory": str(parent),
        "selected_evidence_handles": [item["handle"] for item in evidence],
        "required_slot_contracts": required_slots,
        "framework_subject": subject,
        "full_report_visible_to_stage_b": False,
        "reference_answer_visible_to_runner": False,
        "v20_contract_gate": contract_gate,
        "v22_same_path_preflight": v22_preflight,
        "v24_preflight_enabled": use_v24_preflight,
        "v24_layout_gate_enabled": use_v24_layout_gate,
        "v25_single_block_ordered_spans_enabled": (
            use_v25_single_block_ordered_spans
        ),
        "v25_contract_selection": v25_contract_selection,
        "v26_atomic_projection_enabled": use_v26_atomic_projection,
        "v26_semantic_single_block_spans_enabled": (
            use_v26_semantic_single_block_spans
        ),
        "v26_contract_selection": v26_contract_selection,
        "v27_handle_aliases_enabled": use_v27_handle_aliases,
        "v27_handle_alias_catalog": alias_catalog,
    }
    context["stage_b_handle_closure_preflight"] = enforce_stage_b_handle_closure(
        stage_a_output=normalized,
        stage_b_context=context,
        projected_output={"validated_claims": []},
        gate_phase="pre_model",
    )
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("v1.3 Stage B requires a locked model digest")
    prompt = Path(system_prompt_path).read_text(encoding="utf-8").strip()
    schema_handles = (
        list(alias_catalog) if use_v27_handle_aliases else [item["handle"] for item in evidence]
    )
    schema = slot_output_schema(schema_handles, required_slots)
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
            request=request,
            error=error,
            elapsed_seconds=time.perf_counter() - started,
            model_manifest=model_manifest,
            stage="model_chat",
            redact_request_content=True,
            additional_json={"stage_b_context_manifest.json": context},
        )
        raise
    model_output: Any = None
    projection_output: Any = None
    finalized: Any = None
    alias_resolution_audit: dict[str, Any] | None = None
    closure_postflight: dict[str, Any] | None = None
    try:
        model_output = parse_strict_json_content(result.response.get("message", {}).get("content"))
        projection_output = model_output
        if use_v27_handle_aliases:
            projection_output = deepcopy(model_output)
            emitted_aliases = [item["evidence_handle"] for item in projection_output["slots"]]
            resolved, alias_resolution_audit = resolve_handle_aliases_v27(
                emitted_aliases, alias_catalog
            )
            for item, handle in zip(projection_output["slots"], resolved, strict=True):
                item["evidence_handle"] = handle
        if use_v26_atomic_projection:
            projector = project_atomic_slots_v26
        elif use_v21_contract_adapters:
            projector = validate_and_project_slots_v21
        else:
            projector = validate_and_project_slots
        finalized = projector(
            model_output=projection_output,
            evidence=evidence,
            required_slots=required_slots,
            framework_subject=subject,
        )
        closure_postflight = enforce_stage_b_handle_closure(
            stage_a_output=normalized,
            stage_b_context=context,
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
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "reference_answer_visible_to_runner": False,
        "full_report_visible_to_stage_b": False,
        "posthoc_semantic_repair_applied": False,
        "framework_owned_semantic_slots": True,
        "v26_atomic_projection_enabled": use_v26_atomic_projection,
        "v27_handle_aliases_enabled": use_v27_handle_aliases,
        "v27_handle_alias_resolution": alias_resolution_audit,
        "stage_b_handle_closure_postflight": closure_postflight,
    }
    archive.record_result(
        result,
        model_manifest=model_manifest,
        normalized_output=finalized,
        redact_request_content=True,
        additional_json={
            "model_generated_content.json": model_output,
            "stage_b_context_manifest.json": context,
            "validation.json": validation,
        },
    )
    if errors:
        raise OllamaError(
            f"v1.3 Stage B model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
        "validated_claim_count": len(finalized["validated_claims"]),
    }
