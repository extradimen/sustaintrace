from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .archive import RunArchive, build_model_manifest
from .config import ModelConfig
from .ollama_client import OllamaClient, OllamaError
from .p1_v06_runner import build_v066_packet_from_registry
from .p1_v07 import finalize_v07_output, task_conditioned_schema_v07
from .structured_output import parse_strict_json_content


def run_p1_v07_task(
    *, model_config_path: str | Path, task_pack_path: str | Path, task_id: str,
    acquisition_manifest_path: str | Path, raw_root: str | Path,
    interventions_root: str | Path, registry_path: str | Path,
    workspace_root: str | Path, system_prompt_path: str | Path,
    archive_root: str | Path, experiment_id: str, run_id: str,
    think: bool | str | None = None,
) -> dict[str, Any]:
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("P1 v0.7 requires a locked model digest")
    packet, context_manifest, handles = build_v066_packet_from_registry(
        task_pack_path=task_pack_path, task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path, raw_root=raw_root,
        interventions_root=interventions_root, registry_path=registry_path,
        workspace_root=workspace_root, split_table_rows=True,
    )
    context_manifest["pipeline_version"] = "P1-PIPELINE-v0.7-TOOL-OWNED-SEMANTIC-STATE"
    prompt = Path(system_prompt_path).read_text(encoding="utf-8").strip()
    schema = task_conditioned_schema_v07(
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
        finalized = finalize_v07_output(model_output, context_manifest["task_type"], handles)
        errors: list[str] = []
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        errors = [f"{type(error).__name__}:{error}"]
    validation = {
        "status": "passed" if not errors else "failed", "errors": errors,
        "reference_answer_visible_to_runner": False,
        "posthoc_semantic_repair_applied": False,
        "framework_owns_evidence_state": True,
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
            f"P1 v0.7 model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {
        "task_id": task_id, "run_id": run_id, "model": config.model,
        "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
        "framework_evidence_state": finalized["framework_evidence_state"],
    }
