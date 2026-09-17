from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .archive import RunArchive, build_model_manifest
from .config import ModelConfig
from .ollama_client import OllamaClient, OllamaError
from .p1_stage_b import stage_b_schema
from .p1_stage_b_runner import build_stage_b_packet
from .repair_dispatch import StageBHandleClosureError, enforce_stage_b_handle_closure
from .structured_output import parse_strict_json_content
from .v11_evidence import build_v11_packet
from .v11_stage_b import validate_and_project_v11


def run_v11_stage_b_task(
    *,
    model_config_path: str | Path,
    parent_run_directory: str | Path,
    task_pack_path: str | Path,
    acquisition_manifest_path: str | Path,
    raw_root: str | Path,
    interventions_root: str | Path,
    registry_path: str | Path,
    workspace_root: str | Path,
    ontology_path: str | Path,
    source_registry_path: str | Path,
    projection_contracts_path: str | Path,
    reporting_year_registry_path: str | Path,
    system_prompt_path: str | Path,
    archive_root: str | Path,
    experiment_id: str,
    run_id: str,
    think: bool | str | None = None,
) -> dict[str, Any]:
    parent = Path(parent_run_directory)
    parent_context = json.loads((parent / "task_context_manifest.json").read_text(encoding="utf-8"))
    task_id = parent_context["task_id"]
    _, _, available_handles = build_v11_packet(
        task_pack_path=task_pack_path,
        task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path,
        raw_root=raw_root,
        interventions_root=interventions_root,
        registry_path=registry_path,
        workspace_root=workspace_root,
    )
    packet, context, evidence, ontology, subject = build_stage_b_packet(
        parent_run_directory=parent,
        available_handles=available_handles,
        ontology_path=ontology_path,
        source_registry_path=source_registry_path,
    )
    contracts = json.loads(Path(projection_contracts_path).read_text(encoding="utf-8"))["contracts"]
    reporting_years = json.loads(Path(reporting_year_registry_path).read_text(encoding="utf-8"))[
        "reporting_years"
    ]
    required_claims = contracts.get(task_id)
    if not required_claims:
        raise ValueError(f"v11_projection_contract_missing:{task_id}")
    reporting_year = reporting_years[parent_context["document_id"]]
    packet["required_claim_contract"] = required_claims
    packet["framework_reporting_year"] = reporting_year
    context["pipeline_version"] = "ESG-RD-v1.1-TABLE-AND-PERIOD"
    context["projection_contract"] = required_claims
    context["framework_reporting_year"] = reporting_year
    stage_a_output = json.loads(
        (parent / "normalized_output.json").read_text(encoding="utf-8")
    )
    context["stage_b_handle_closure_preflight"] = enforce_stage_b_handle_closure(
        stage_a_output=stage_a_output,
        stage_b_context=context,
        projected_output={"validated_claims": []},
        gate_phase="pre_model",
    )
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("v1.1 Stage B requires a locked model digest")
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
    finalized: Any = None
    closure_postflight: dict[str, Any] | None = None
    try:
        model_output = parse_strict_json_content(result.response.get("message", {}).get("content"))
        finalized = validate_and_project_v11(
            model_output,
            evidence,
            ontology,
            subject,
            required_claims,
            reporting_year,
        )
        closure_postflight = enforce_stage_b_handle_closure(
            stage_a_output=stage_a_output,
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
        "cell_level_evidence_enabled": True,
        "reporting_year_inheritance_enabled": True,
        "semantic_coverage_gate_enabled": True,
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
            f"v1.1 Stage B model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "model": config.model,
        "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
        "validated_claim_count": len(finalized["validated_claims"]),
        "reporting_year_inheritance_count": len(finalized["reporting_year_inheritance"]),
    }
