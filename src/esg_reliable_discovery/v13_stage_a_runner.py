from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .archive import RunArchive, build_model_manifest
from .config import ModelConfig
from .ollama_client import OllamaClient, OllamaError
from .p1_v07 import finalize_v07_output, task_conditioned_schema_v07
from .structured_output import parse_strict_json_content
from .v12_direct import direct_extraction_schema_v12, finalize_direct_v12
from .v13_evidence import build_v13_packet
from .v15_evidence import build_v15_packet
from .v21_calculation import calculation_schema_v21, finalize_calculation_v21
from .v23_preflight import calculation_binding_schema_v23, execute_calculation_plan_v23
from .v24_integrity import (
    normalize_calculation_binding_v24,
    validate_layout_registry_v24,
)
from .v25_integrity import (
    execute_calculation_plan_v25,
    normalize_calculation_binding_v25,
)
from .v26_integrity import (
    normalize_calculation_binding_v26,
    validate_candidate_handles_v26,
)
from .v27_integrity import bind_partial_calculation_request_v27
from .v28_integrity import (
    bind_handle_role_calculation_request_v28,
    validate_stage_a_task_id_v28,
)
from .v29_integrity import (
    bind_exact_task_id_schema_v29,
    calculation_payload_v29,
    execute_calculation_plan_v29,
)
from .v30_integrity import (
    bind_response_to_identity_v30,
    create_task_identity_envelope_v30,
)
from .v31_integrity import (
    alias_stage_a_evidence_v31,
    decode_stage_a_aliases_v31,
    project_calculation_slots_v31,
)


def run_v13_stage_a_task(
    *,
    model_config_path: str | Path,
    task_pack_path: str | Path,
    task_id: str,
    acquisition_manifest_path: str | Path,
    raw_root: str | Path,
    interventions_root: str | Path,
    registry_path: str | Path,
    workspace_root: str | Path,
    layout_registry_path: str | Path,
    system_prompt_path: str | Path,
    archive_root: str | Path,
    experiment_id: str,
    run_id: str,
    think: bool | str | None = None,
    use_v15_grounding: bool = False,
    use_v21_calculation: bool = False,
    calculation_plan_path: str | Path | None = None,
    use_v24_calculation_adapter: bool = False,
    use_v24_layout_gate: bool = False,
    use_v25_calculation_adapter: bool = False,
    use_v26_calculation_adapter: bool = False,
    use_v26_handle_audit: bool = False,
    use_v27_partial_calculation: bool = False,
    use_v28_handle_role_binding: bool = False,
    use_v28_task_id_gate: bool = False,
    use_v29_task_id_schema: bool = False,
    use_v29_calculation_executor: bool = False,
    use_v30_executor_identity_envelope: bool = False,
    use_v31_stage_a_handle_aliases: bool = False,
    use_v31_calculation_slot_projection: bool = False,
) -> dict[str, Any]:
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("v1.3 Stage A requires a locked model digest")
    if use_v24_layout_gate:
        layout_registry = json.loads(Path(layout_registry_path).read_text(encoding="utf-8"))
        validate_layout_registry_v24(layout_registry.get("targets", []))
    evidence_builder = build_v15_packet if use_v15_grounding else build_v13_packet
    packet, context, handles = evidence_builder(
        task_pack_path=task_pack_path,
        task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path,
        raw_root=raw_root,
        interventions_root=interventions_root,
        registry_path=registry_path,
        workspace_root=workspace_root,
        layout_registry_path=layout_registry_path,
    )
    prompt = Path(system_prompt_path).read_text(encoding="utf-8").strip()
    canonical_handle_ids = [item["handle"] for item in handles]
    stage_a_alias_catalog = None
    stage_a_alias_audit = None
    if use_v31_stage_a_handle_aliases:
        packet, stage_a_alias_catalog, stage_a_alias_audit = alias_stage_a_evidence_v31(
            packet, handles
        )
        handle_ids = list(stage_a_alias_catalog)
    else:
        handle_ids = canonical_handle_ids
    calculation_plan = None
    if calculation_plan_path is not None and context["task_type"] == "deterministic_calculation":
        plan_registry = json.loads(Path(calculation_plan_path).read_text(encoding="utf-8"))
        calculation_plan = plan_registry["plans"].get(task_id)
        if calculation_plan is None:
            raise ValueError(f"v23_calculation_plan_missing:{task_id}")
        schema = calculation_binding_schema_v23(handle_ids, calculation_plan)
        context["v23_calculation_plan"] = calculation_plan
        context["candidate_selects_operation"] = False
    elif use_v21_calculation and context["task_type"] == "deterministic_calculation":
        schema = calculation_schema_v21(handle_ids)
    elif context["task_type"] == "direct_extraction":
        schema = direct_extraction_schema_v12(handle_ids)
    else:
        schema = task_conditioned_schema_v07(context["task_type"], handle_ids)
    if use_v30_executor_identity_envelope and (
        use_v28_task_id_gate or use_v29_task_id_schema
    ):
        raise ValueError("v30_identity_modes_mutually_exclusive")
    if use_v29_task_id_schema:
        schema = bind_exact_task_id_schema_v29(schema, task_id)
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
    task_identity_envelope = (
        create_task_identity_envelope_v30(
            task_pack_path=task_pack_path,
            task_id=task_id,
            experiment_id=experiment_id,
            run_id=run_id,
            request_payload=request,
        )
        if use_v30_executor_identity_envelope
        else None
    )
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
            additional_json={
                "task_context_manifest.json": context,
                **(
                    {"task_identity_envelope.json": task_identity_envelope}
                    if task_identity_envelope is not None
                    else {}
                ),
            },
        )
        raise
    model_output: Any = None
    finalized: Any = None
    calculation_adapter_audit: dict[str, Any] | None = None
    partial_calculation_audit: dict[str, Any] | None = None
    candidate_handle_audit: dict[str, Any] | None = None
    task_id_audit: dict[str, Any] | None = None
    response_identity_link: dict[str, Any] | None = None
    stage_a_alias_decode_audit: dict[str, Any] | None = None
    calculation_slot_projection: dict[str, Any] | None = None
    try:
        model_output = parse_strict_json_content(result.response.get("message", {}).get("content"))
        processing_output = model_output
        if use_v31_stage_a_handle_aliases:
            processing_output, stage_a_alias_decode_audit = decode_stage_a_aliases_v31(
                model_output, stage_a_alias_catalog or {}
            )
        if use_v30_executor_identity_envelope:
            response_identity_link = bind_response_to_identity_v30(
                task_identity_envelope, result.response
            )
            task_id_audit = response_identity_link
        elif use_v28_task_id_gate or use_v29_task_id_schema:
            task_id_audit = validate_stage_a_task_id_v28(processing_output, task_id)
        if use_v26_handle_audit:
            candidate_handle_audit = validate_candidate_handles_v26(
                processing_output, canonical_handle_ids
            )
        if calculation_plan is not None:
            calculation_output = (
                calculation_payload_v29(processing_output, task_id)
                if use_v29_task_id_schema
                else processing_output
            )
            binding_output = calculation_output
            if use_v26_calculation_adapter:
                try:
                    binding_output, calculation_adapter_audit = (
                        normalize_calculation_binding_v26(
                            calculation_output, calculation_plan, canonical_handle_ids
                        )
                    )
                except ValueError:
                    if not use_v27_partial_calculation:
                        raise
                    binding_output, partial_calculation_audit = (
                        bind_partial_calculation_request_v27(
                            calculation_output, calculation_plan, canonical_handle_ids
                        )
                    )
            elif use_v25_calculation_adapter:
                try:
                    binding_output, calculation_adapter_audit = (
                        normalize_calculation_binding_v25(calculation_output, calculation_plan)
                    )
                except ValueError as error:
                    if not use_v28_handle_role_binding or not str(error).startswith(
                        "v24_calculation_metric_unmatched:"
                    ):
                        raise
                    binding_output, calculation_adapter_audit = (
                        bind_handle_role_calculation_request_v28(
                            calculation_output, calculation_plan, canonical_handle_ids
                        )
                    )
                    if calculation_adapter_audit["missing_roles"]:
                        partial_calculation_audit = calculation_adapter_audit
            elif use_v24_calculation_adapter:
                binding_output, calculation_adapter_audit = (
                    normalize_calculation_binding_v24(calculation_output, calculation_plan)
                )
            selected = list(
                dict.fromkeys(
                    item["evidence_handle"]
                    for item in binding_output["observations"].values()
                )
            )
            handle_index = {item["handle"]: item for item in handles}
            if partial_calculation_audit is not None:
                finalized = {
                    "model_output": model_output,
                    "resolved_evidence": [handle_index[handle] for handle in selected],
                    "partial_calculation_binding": binding_output,
                    "partial_calculation_audit": partial_calculation_audit,
                    "framework_evidence_state": "partially_supported",
                    "model_output_modified": False,
                    "missing_values_invented": False,
                    "posthoc_semantic_repair_applied": False,
                    "v28_task_id_audit": task_id_audit,
                }
            else:
                calculation_executor = (
                    execute_calculation_plan_v29
                    if use_v29_calculation_executor
                    else execute_calculation_plan_v25
                    if use_v25_calculation_adapter or use_v26_calculation_adapter
                    else execute_calculation_plan_v23
                )
                execution = calculation_executor(
                    binding_output, handles, calculation_plan
                )
                if use_v31_calculation_slot_projection:
                    calculation_slot_projection = project_calculation_slots_v31(
                        execution, calculation_plan.get("output_slot_map", [])
                    )
                finalized = {
                    "model_output": model_output,
                    "resolved_evidence": [handle_index[handle] for handle in selected],
                    "deterministic_calculation": execution,
                    "calculation_binding_adapter": calculation_adapter_audit,
                    "v28_task_id_audit": task_id_audit,
                    "v31_calculation_slot_projection": calculation_slot_projection,
                    "framework_evidence_state": "supported",
                    "model_output_modified": False,
                    "posthoc_semantic_repair_applied": False,
                }
        elif use_v21_calculation and context["task_type"] == "deterministic_calculation":
            finalized = finalize_calculation_v21(processing_output, handles)
        elif context["task_type"] == "direct_extraction":
            finalized = finalize_direct_v12(processing_output, handles, packet["question"])
        else:
            finalized = finalize_v07_output(processing_output, context["task_type"], handles)
        errors: list[str] = []
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        errors = [f"{type(error).__name__}:{error}"]
    validation = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "reference_answer_visible_to_runner": False,
        "posthoc_semantic_repair_applied": False,
        "dual_parser_evidence_enabled": True,
        "layout_fallback_provenance": context["layout_fallback_provenance"],
        "v23_framework_owned_calculation_plan": calculation_plan is not None,
        "v24_calculation_adapter_enabled": use_v24_calculation_adapter,
        "v24_layout_gate_enabled": use_v24_layout_gate,
        "v25_calculation_adapter_enabled": use_v25_calculation_adapter,
        "v26_calculation_adapter_enabled": use_v26_calculation_adapter,
        "v26_candidate_handle_audit_enabled": use_v26_handle_audit,
        "v26_candidate_handle_audit": candidate_handle_audit,
        "v27_partial_calculation_enabled": use_v27_partial_calculation,
        "v27_partial_calculation_audit": partial_calculation_audit,
        "v28_handle_role_binding_enabled": use_v28_handle_role_binding,
        "v28_task_id_gate_enabled": use_v28_task_id_gate,
        "v28_task_id_audit": task_id_audit,
        "v29_exact_task_id_schema_enabled": use_v29_task_id_schema,
        "v29_calculation_executor_enabled": use_v29_calculation_executor,
        "v30_executor_identity_envelope_enabled": use_v30_executor_identity_envelope,
        "v30_response_identity_link": response_identity_link,
        "v31_stage_a_handle_aliases_enabled": use_v31_stage_a_handle_aliases,
        "v31_stage_a_alias_catalog": stage_a_alias_catalog,
        "v31_stage_a_alias_audit": stage_a_alias_audit,
        "v31_stage_a_alias_decode_audit": stage_a_alias_decode_audit,
        "v31_calculation_slot_projection_enabled": use_v31_calculation_slot_projection,
        "v31_calculation_slot_projection": calculation_slot_projection,
    }
    archive.record_result(
        result,
        model_manifest=model_manifest,
        normalized_output=finalized,
        redact_request_content=True,
        additional_json={
            "model_generated_content.json": model_output,
            "task_context_manifest.json": context,
            "validation.json": validation,
            **(
                {
                    "task_identity_envelope.json": task_identity_envelope,
                    "response_identity_link.json": response_identity_link,
                }
                if task_identity_envelope is not None
                else {}
            ),
        },
    )
    if errors:
        raise OllamaError(
            f"v1.3 Stage A model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "model": config.model,
        "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
        "framework_evidence_state": finalized["framework_evidence_state"],
    }
