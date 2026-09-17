from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .archive import RunArchive, build_model_manifest
from .config import ModelConfig
from .hashing import sha256_file
from .ollama_client import OllamaClient, OllamaError
from .structured_output import parse_strict_json_content


def _load_task(task_pack_path: str | Path, task_id: str) -> dict[str, Any]:
    pack = json.loads(Path(task_pack_path).read_text(encoding="utf-8"))
    matches = [task for task in pack["tasks"] if task["task_id"] == task_id]
    if len(matches) != 1 or matches[0].get("question_status") != "frozen":
        raise ValueError(f"Task is missing, duplicated, or not frozen: {task_id}")
    return matches[0]


def _load_document(manifest_path: str | Path, document_id: str) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    matches = [item for item in manifest["documents"] if item["document_id"] == document_id]
    if len(matches) != 1 or matches[0].get("ingestion_status") != "verified":
        raise ValueError(f"Document is missing, duplicated, or not verified: {document_id}")
    return matches[0]


def extract_target_pages(pdf_path: str | Path, pages: list[int]) -> dict[int, str]:
    extracted: dict[int, str] = {}
    for page in pages:
        result = subprocess.run(
            ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        extracted[page] = result.stdout.strip()
    return extracted


def build_evidence_packet(
    *,
    task_pack_path: str | Path,
    task_id: str,
    acquisition_manifest_path: str | Path,
    raw_root: str | Path,
    interventions_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build candidate-visible input; deliberately has no reference-answer argument."""
    task = _load_task(task_pack_path, task_id)
    document = _load_document(acquisition_manifest_path, task["document_id"])
    pdf_path = Path(raw_root) / document["local_path"]
    if sha256_file(pdf_path) != document["sha256"]:
        raise ValueError(f"Source hash mismatch: {document['document_id']}")
    pages = extract_target_pages(pdf_path, task["target_pages"])
    packet: dict[str, Any] = {
        "task_id": task_id,
        "task_type": task["task_type"],
        "question": task["question"],
        "official_source": {
            "source_id": document["document_id"],
            "document_sha256": document["sha256"],
            "pages": [{"pdf_page": page, "text": pages[page]} for page in task["target_pages"]],
        },
    }
    intervention_id = task.get("controlled_intervention_id")
    if intervention_id:
        path = Path(interventions_root) / f"{intervention_id}.json"
        intervention = json.loads(path.read_text(encoding="utf-8"))
        if intervention["source_document_sha256"] != document["sha256"]:
            raise ValueError(f"Controlled intervention hash mismatch: {intervention_id}")
        packet["controlled_analyst_note"] = {
            "source_id": intervention_id,
            "page": 1,
            "text": intervention["injected_text"],
            "construction_disclosure": intervention["construction_note"],
        }
    manifest = {
        "task_id": task_id,
        "task_type": task["task_type"],
        "document_id": document["document_id"],
        "document_sha256": document["sha256"],
        "target_pages": task["target_pages"],
        "controlled_intervention_id": intervention_id,
        "reference_answer_visible_to_runner": False,
    }
    return packet, manifest


def validate_candidate_output(
    output: Any,
    schema: dict[str, Any],
    context_manifest: dict[str, Any],
    evidence_texts: dict[tuple[str, int], str] | None = None,
) -> list[str]:
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(output)]
    if not isinstance(output, dict):
        return errors or ["output_not_object"]
    if output.get("task_id") != context_manifest["task_id"]:
        errors.append("wrong_task_id")
    allowed = {(context_manifest["document_id"], page) for page in context_manifest["target_pages"]}
    intervention_id = context_manifest.get("controlled_intervention_id")
    if intervention_id:
        allowed.add((intervention_id, 1))
    for evidence in output.get("evidence", []):
        locator = (evidence.get("source_id"), evidence.get("page"))
        if locator not in allowed:
            errors.append("invalid_evidence_locator")
        elif evidence_texts is not None:
            excerpt = re.sub(r"\s+", " ", evidence.get("verbatim_excerpt", "")).strip()
            source = re.sub(r"\s+", " ", evidence_texts.get(locator, "")).strip()
            if excerpt not in source:
                errors.append("evidence_excerpt_not_verbatim")
    if output.get("answer_status") == "insufficient_information":
        if output.get("answer") is not None or output.get("normalized_value") is not None:
            errors.append("abstention_must_not_contain_answer")
    return errors


def run_p1_task(
    *, model_config_path: str | Path, task_pack_path: str | Path, task_id: str,
    acquisition_manifest_path: str | Path, raw_root: str | Path,
    interventions_root: str | Path, system_prompt_path: str | Path,
    response_schema_path: str | Path, archive_root: str | Path,
    experiment_id: str, run_id: str, think: bool | str | None = None,
) -> dict[str, Any]:
    config = ModelConfig.from_path(model_config_path)
    if not config.expected_digest:
        raise OllamaError("P1 requires a locked model digest")
    packet, context_manifest = build_evidence_packet(
        task_pack_path=task_pack_path, task_id=task_id,
        acquisition_manifest_path=acquisition_manifest_path, raw_root=raw_root,
        interventions_root=interventions_root,
    )
    prompt = Path(system_prompt_path).read_text(encoding="utf-8").strip()
    schema = json.loads(Path(response_schema_path).read_text(encoding="utf-8"))
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
    content = result.response.get("message", {}).get("content")
    output: Any = None
    try:
        output = parse_strict_json_content(content)
        evidence_texts = {
            (packet["official_source"]["source_id"], item["pdf_page"]): item["text"]
            for item in packet["official_source"]["pages"]
        }
        if note := packet.get("controlled_analyst_note"):
            evidence_texts[(note["source_id"], note["page"])] = note["text"]
        errors = validate_candidate_output(output, schema, context_manifest, evidence_texts)
    except (TypeError, json.JSONDecodeError) as error:
        errors = [f"invalid_json:{type(error).__name__}"]
    validation = {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "reference_answer_visible_to_runner": False,
        "posthoc_semantic_repair_applied": False,
        "validated_at": datetime.now(UTC).isoformat(),
    }
    archive.record_result(
        result, model_manifest=model_manifest, normalized_output=output,
        redact_request_content=True,
        additional_json={
            "task_context_manifest.json": context_manifest,
            "validation.json": validation,
        },
    )
    if errors:
        raise OllamaError(
            f"P1 model behavior failed; archived at {archive.run_dir}: "
            + "; ".join(errors)
        )
    return {"task_id": task_id, "run_id": run_id, "model": config.model,
            "archive_directory": str(archive.run_dir), "elapsed_seconds": result.elapsed_seconds}
