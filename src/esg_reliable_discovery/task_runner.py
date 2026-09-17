from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .archive import RunArchive, build_model_manifest
from .config import ModelConfig
from .hashing import sha256_file
from .ollama_client import OllamaClient, OllamaError
from .structured_output import parse_strict_json_content
from .task_context import build_task_context
from .v3_tools import (
    evidence_handle_model_schema,
    resolve_evidence_handles,
    verify_deterministic_calculation,
)

V1_FRAMEWORK_FIELDS = {"finding_id", "task_id", "company_id", "company", "provenance"}


def _response_schema(finding_schema: dict[str, Any], minimum: int, maximum: int) -> dict[str, Any]:
    if minimum == maximum == 1:
        return finding_schema
    item_schema = deepcopy(finding_schema)
    definitions = item_schema.pop("$defs", None)
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "items": item_schema,
        "minItems": minimum,
        "maxItems": maximum,
    }
    if definitions:
        wrapper["$defs"] = definitions
    return wrapper


def _model_content_schema(
    finding_schema: dict[str, Any], injection_policy: dict[str, Any]
) -> dict[str, Any]:
    schema = deepcopy(finding_schema)
    excluded = injection_policy["framework_injected_fields"]
    schema["title"] = "Model-generated ESG Finding Content"
    schema.pop("$id", None)
    schema["required"] = [field for field in schema["required"] if field not in excluded]
    for field in excluded:
        schema["properties"].pop(field, None)
    return schema


def _validate_injection_policy(injection_policy: dict[str, Any]) -> None:
    if set(injection_policy.get("framework_injected_fields", [])) != V1_FRAMEWORK_FIELDS:
        raise ValueError("Injection policy must contain exactly the registered V1 fields")
    if injection_policy.get("posthoc_semantic_repair_allowed") is not False:
        raise ValueError("Injection policy must prohibit posthoc semantic repair")
    if injection_policy.get("model_generated_content_preserved") is not True:
        raise ValueError("Injection policy must preserve model-generated content")


def _task_conditioned_schema(
    model_schema: dict[str, Any], task: dict[str, Any], contracts: dict[str, Any]
) -> dict[str, Any]:
    schema = deepcopy(model_schema)
    task_type = task["task_type"]
    try:
        contract = contracts["contracts"][task_type]
    except KeyError as error:
        raise ValueError(f"No V2 contract registered for task type: {task_type}") from error
    required = list(schema["required"])
    for field in contract.get("required_fields", []):
        if field not in required:
            required.append(field)
    schema["required"] = required
    if statuses := contract.get("allowed_statuses"):
        schema["properties"]["status"] = {"enum": statuses}
    if finding_types := contract.get("allowed_finding_types"):
        schema["properties"]["finding_type"] = {"enum": finding_types}
    schema["properties"]["claim_level"] = {"enum": task["allowed_claim_levels"]}
    for field, minimum in contract.get("minimum_items", {}).items():
        schema["properties"][field] = deepcopy(schema["properties"][field])
        schema["properties"][field]["minItems"] = minimum
    schema["title"] = f"V2 {task_type} ESG Finding Content"
    return schema


def _inject_framework_fields(
    model_output: Any,
    *,
    task: dict[str, Any],
    context_manifest: dict[str, Any],
    expected_provenance: dict[str, Any],
    run_id: str,
) -> Any:
    source_cards = model_output if isinstance(model_output, list) else [model_output]
    companies = {
        (page["company_id"], page["company_name"]) for page in context_manifest["pages"]
    }
    if len(companies) != 1:
        raise ValueError("framework_injection_ambiguous_company")
    company_id, company_name = next(iter(companies))
    assembled = []
    for index, source in enumerate(source_cards, start=1):
        if not isinstance(source, dict):
            assembled.append(source)
            continue
        card = deepcopy(source)
        card.update(
            {
                "finding_id": f"{run_id}-card-{index:03d}",
                "task_id": task["task_id"],
                "company_id": company_id,
                "company": company_name,
                "provenance": {"annotation_source": "model"} | expected_provenance,
            }
        )
        assembled.append(card)
    return assembled if isinstance(model_output, list) else assembled[0]


def _validate_cards(
    normalized: Any,
    *,
    finding_schema: dict[str, Any],
    task: dict[str, Any],
    context_manifest: dict[str, Any],
    expected_provenance: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    cards = normalized if isinstance(normalized, list) else [normalized]
    errors: list[str] = []
    counts = task["expected_card_count"]
    if not counts["minimum"] <= len(cards) <= counts["maximum"]:
        errors.append("prohibited_card_count")
    validator = Draft202012Validator(finding_schema)
    allowed_evidence = {
        (page["document_id"], page["document_sha256"], page["pdf_page"])
        for page in context_manifest["pages"]
    }
    intervention = context_manifest.get("controlled_intervention")
    if intervention:
        allowed_evidence.add((intervention["intervention_id"], intervention["sha256"], 1))
    allowed_companies = {
        (page["company_id"], page["company_name"]) for page in context_manifest["pages"]
    }
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            errors.append(f"card_{index}:not_an_object")
            continue
        schema_errors = sorted(validator.iter_errors(card), key=lambda item: list(item.path))
        if schema_errors:
            errors.append(f"card_{index}:schema:{schema_errors[0].message}")
            continue
        if card["task_id"] != task["task_id"]:
            errors.append(f"card_{index}:wrong_task_id")
        if card["claim_level"] not in task["allowed_claim_levels"]:
            errors.append(f"card_{index}:prohibited_claim_level")
        if (card["company_id"], card["company"]) not in allowed_companies:
            errors.append(f"card_{index}:company_boundary_mismatch")
        for key, expected in expected_provenance.items():
            if card["provenance"].get(key) != expected:
                errors.append(f"card_{index}:provenance_mismatch:{key}")
        for evidence_kind in ("supporting_evidence", "contrary_evidence"):
            for evidence in card[evidence_kind]:
                evidence_key = (
                    evidence["document_id"],
                    evidence["document_sha256"],
                    evidence["page"],
                )
                if evidence_key not in allowed_evidence:
                    errors.append(f"card_{index}:invalid_evidence_locator:{evidence_kind}")
    return cards, errors


def run_task(
    *,
    model_config_path: str | Path,
    task_pack_path: str | Path,
    task_id: str,
    document_manifest_path: str | Path,
    raw_root: str | Path,
    system_prompt_path: str | Path,
    finding_schema_path: str | Path,
    archive_root: str | Path,
    experiment_id: str,
    run_id: str,
    framework_version: str,
    include_images: bool = False,
    think: bool | str | None = None,
    injection_policy_path: str | Path | None = None,
    task_contracts_path: str | Path | None = None,
    evidence_handle_policy_path: str | Path | None = None,
    calculation_policy_path: str | Path | None = None,
) -> dict[str, Any]:
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("Formal task runs require a locked expected_digest")
    evidence_handle_policy = (
        json.loads(Path(evidence_handle_policy_path).read_text(encoding="utf-8"))
        if evidence_handle_policy_path
        else None
    )
    calculation_policy = (
        json.loads(Path(calculation_policy_path).read_text(encoding="utf-8"))
        if calculation_policy_path
        else None
    )
    context = build_task_context(
        task_pack_path,
        task_id,
        document_manifest_path,
        raw_root,
        include_images=include_images,
        include_evidence_handles=bool(evidence_handle_policy),
    )
    task = context["task"]
    system_prompt = Path(system_prompt_path).read_text(encoding="utf-8").strip()
    finding_schema = json.loads(Path(finding_schema_path).read_text(encoding="utf-8"))
    injection_policy = (
        json.loads(Path(injection_policy_path).read_text(encoding="utf-8"))
        if injection_policy_path
        else None
    )
    if injection_policy:
        _validate_injection_policy(injection_policy)
    task_contracts = (
        json.loads(Path(task_contracts_path).read_text(encoding="utf-8"))
        if task_contracts_path
        else None
    )
    counts = task["expected_card_count"]
    model_schema = (
        _model_content_schema(finding_schema, injection_policy)
        if injection_policy
        else finding_schema
    )
    if task_contracts:
        model_schema = _task_conditioned_schema(model_schema, task, task_contracts)
    if evidence_handle_policy:
        model_schema = evidence_handle_model_schema(model_schema)
    response_schema = _response_schema(model_schema, counts["minimum"], counts["maximum"])
    created_at = datetime.now(UTC).isoformat()
    prompt_sha256 = sha256_file(system_prompt_path)
    user_content = (
        f"TASK ID: {task_id}\n"
        f"TASK INSTRUCTION: {task['instruction']}\n"
        f"ALLOWED CLAIM LEVELS: {', '.join(task['allowed_claim_levels'])}\n"
        f"CARD COUNT: {counts['minimum']} to {counts['maximum']}\n"
        + (
            "Do not generate finding_id, task_id, company_id, company, or provenance; "
            "the framework injects those fields deterministically.\n\n"
            if injection_policy
            else (
                "Use these exact provenance values in every card:\n"
                f"framework_version={framework_version}\n"
                f"model_snapshot={config.model}@{config.expected_digest}\n"
                f"prompt_sha256={prompt_sha256}\n"
                f"run_id={run_id}\n"
                f"created_at={created_at}\n\n"
            )
        )
        + f"{context['context_text']}"
    )
    user_message: dict[str, Any] = {"role": "user", "content": user_content}
    if context["images"]:
        user_message["images"] = context["images"]
    messages = [{"role": "system", "content": system_prompt}, user_message]

    client = OllamaClient(config)
    digest = client.verify_digest()
    if digest != config.expected_digest:
        raise OllamaError(f"Locked model not available: {config.model}")
    model_details = client.show_model()
    archive = RunArchive.create(archive_root, experiment_id, run_id)
    model_manifest = build_model_manifest(config.public_dict(), model_details, digest)
    context_manifest = context["public_manifest"] | {
        "system_prompt_path": str(system_prompt_path),
        "system_prompt_sha256": prompt_sha256,
        "finding_schema_path": str(finding_schema_path),
        "finding_schema_sha256": sha256_file(finding_schema_path),
        "framework_version": framework_version,
        "include_images": include_images,
        "injection_policy_path": str(injection_policy_path) if injection_policy_path else None,
        "injection_policy_sha256": (
            sha256_file(injection_policy_path) if injection_policy_path else None
        ),
        "framework_injected_fields": (
            injection_policy["framework_injected_fields"] if injection_policy else []
        ),
        "task_contracts_path": str(task_contracts_path) if task_contracts_path else None,
        "task_contracts_sha256": sha256_file(task_contracts_path) if task_contracts_path else None,
        "task_contract_id": (
            task_contracts["contracts"][task["task_type"]]["contract_id"]
            if task_contracts
            else None
        ),
        "evidence_handle_policy_path": (
            str(evidence_handle_policy_path) if evidence_handle_policy_path else None
        ),
        "evidence_handle_policy_sha256": (
            sha256_file(evidence_handle_policy_path) if evidence_handle_policy_path else None
        ),
        "calculation_policy_path": (
            str(calculation_policy_path) if calculation_policy_path else None
        ),
        "calculation_policy_sha256": (
            sha256_file(calculation_policy_path) if calculation_policy_path else None
        ),
    }
    expected_provenance = {
        "framework_version": framework_version,
        "model_snapshot": f"{config.model}@{config.expected_digest}",
        "prompt_sha256": prompt_sha256,
        "run_id": run_id,
        "created_at": created_at,
    }
    request = client.build_chat_payload(messages, schema=response_schema, think=think)
    started = time.perf_counter()
    try:
        result = client.chat(messages, schema=response_schema, think=think)
    except Exception as error:
        validation = {
            "status": "failed",
            "errors": [f"execution_failure:{type(error).__name__}"],
            "card_count": 0,
            "posthoc_card_repair_applied": False,
        }
        archive.record_failure(
            request=request,
            error=error,
            elapsed_seconds=time.perf_counter() - started,
            model_manifest=model_manifest,
            stage="model_chat",
            redact_request_content=True,
            additional_json={
                "task_context_manifest.json": context_manifest,
                "validation.json": validation,
            },
        )
        raise OllamaError(
            f"Model execution failed; archived at {archive.run_dir}: "
            f"{type(error).__name__}: {error}"
        ) from error
    content = result.response.get("message", {}).get("content")
    model_generated_content = None
    normalized = None
    validation_errors = []
    try:
        model_generated_content = parse_strict_json_content(content)
    except (TypeError, json.JSONDecodeError) as error:
        validation_errors.append(f"invalid_json:{type(error).__name__}")
        cards: list[dict[str, Any]] = []
    else:
        try:
            resolved_content = (
                resolve_evidence_handles(model_generated_content, context_manifest)
                if evidence_handle_policy
                else model_generated_content
            )
            normalized = (
                _inject_framework_fields(
                    resolved_content,
                    task=task,
                    context_manifest=context_manifest,
                    expected_provenance=expected_provenance,
                    run_id=run_id,
                )
                if injection_policy
                else resolved_content
            )
        except ValueError as error:
            validation_errors.append(str(error))
            normalized = model_generated_content
        cards, card_errors = _validate_cards(
            normalized,
            finding_schema=finding_schema,
            task=task,
            context_manifest=context_manifest,
            expected_provenance=expected_provenance,
        )
        validation_errors.extend(card_errors)
    deterministic_verification = None
    if (
        normalized
        and calculation_policy
        and task["task_type"] in calculation_policy.get("operations_by_task_type", {})
    ):
        deterministic_verification = verify_deterministic_calculation(
            normalized,
            calculation_policy["operations_by_task_type"][task["task_type"]],
        )
        if not deterministic_verification["consistent"]:
            validation_errors.append("deterministic_calculation_mismatch")
    validation = {
        "status": "passed" if not validation_errors else "failed",
        "errors": validation_errors,
        "card_count": len(cards),
        "posthoc_card_repair_applied": False,
        "framework_injection_applied": bool(injection_policy),
        "framework_injected_fields": (
            injection_policy["framework_injected_fields"] if injection_policy else []
        ),
    }
    archive.record_result(
        result,
        model_manifest=model_manifest,
        normalized_output=normalized,
        redact_request_content=True,
        additional_json={
            "model_generated_content.json": model_generated_content,
            "deterministic_verification.json": deterministic_verification,
            "task_context_manifest.json": context_manifest,
            "validation.json": validation,
        },
    )
    if validation_errors:
        raise OllamaError(
            f"Model behavior failed validation; archived at {archive.run_dir}: "
            + "; ".join(validation_errors)
        )
    return {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "task_id": task_id,
        "model": config.model,
        "digest": digest,
        "card_count": len(cards),
        "archive_directory": str(archive.run_dir),
        "elapsed_seconds": result.elapsed_seconds,
        "schema_valid": True,
        "performance_interpretation_allowed": config.model != "qwen3:0.6b",
    }
