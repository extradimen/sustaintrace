from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ollama_client import OllamaClient, OllamaResult
from .softwarex_comparative import ACTION_LABELS, SLOTS, SUPPORT_LABELS, sha256
from .structured_output import parse_strict_json_content

_WHITESPACE = re.compile(r"\s+")
_HTML_TAG = re.compile(r"<[^>]+>")
_TOKEN = re.compile(r"[a-z0-9]+")


class ComparativeProtocolError(RuntimeError):
    """Raised when a comparison task cannot run without protocol drift."""


class SourcePreflightError(ComparativeProtocolError):
    """Raised before a model call when frozen local evidence is invalid."""


class ModelBehaviorError(ComparativeProtocolError):
    """Raised after the one allowed model response violates the output contract."""


@dataclass(frozen=True)
class ComparativeContext:
    task_id: str
    document_path: Path
    pages: tuple[int, ...]
    page_text: dict[int, str]
    evidence_page_is_permitted: bool
    evidence_quote_is_grounded: bool


MODEL_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["support_label", "knowledge_base_action", "slots"],
    "properties": {
        "support_label": {"type": "string", "enum": sorted(SUPPORT_LABELS)},
        "knowledge_base_action": {"type": "string", "enum": sorted(ACTION_LABELS)},
        "slots": {
            "type": "object",
            "additionalProperties": False,
            "required": list(SLOTS),
            "properties": {
                slot: {"type": "string", "enum": ["Y", "N", "NA"]}
                for slot in SLOTS
            },
        },
    },
}

CONTRACT_V2_ID = "SUSTAINTRACE-SOFTX-EXECUTABLE-CONTRACT-v2.0"


def contract_v2_instructions() -> str:
    """Return the condition-invariant executable decision contract for E2."""
    return (
        "Return exactly one JSON object and nothing else. Do not use Markdown, prose, code "
        "fences, comments, aliases, additional keys, or a wrapper such as decision. The three "
        "top-level keys must be exactly support_label, knowledge_base_action, and slots. "
        "support_label must be exactly one of: fully_supported, partially_supported, "
        "unsupported, cannot_assess, source_defect. knowledge_base_action must be exactly one "
        "of: admit, correct_then_review, reject, abstain_or_conflict. slots must contain exactly "
        "these seven case-sensitive keys: Subject, Predicate, Value, Period, Unit, "
        "Boundary/method, Evidence coordinates. Every slot value must be exactly Y, N, or NA. "
        "Use this exact shape: "
        '{"support_label":"fully_supported","knowledge_base_action":"admit",'
        '"slots":{"Subject":"Y","Predicate":"Y","Value":"Y","Period":"Y",'
        '"Unit":"Y","Boundary/method":"Y","Evidence coordinates":"Y"}}. '
        "Judge only from the permitted PDF pages. Do not use outside knowledge. Do not infer a "
        "missing period, unit, boundary, method, assurance status, or evidence coordinate. "
        "fully_supported means every material populated element and its evidence coordinates "
        "are supported. partially_supported means the core meaning is supported but at least "
        "one material element is missing, wrong, or over-broad. unsupported means contradicted, "
        "mismatched, or not established. cannot_assess means the permitted window is "
        "insufficient. source_defect means the named source is missing or irreparably "
        "unreadable. admit only a complete supported atomic claim. Use correct_then_review when "
        "a bounded correction may be possible, reject for an unsupported or non-atomic claim, "
        "and abstain_or_conflict when trustworthy admission is not possible from the window. "
        "For an abstention-audit candidate, fully_supported means the proposed refusal is "
        "correct and unsupported means the window actually contains an eligible fact; set all "
        "seven slots to NA for every abstention-audit candidate."
    )


def _normalize(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip().casefold()


def _tokens(value: str) -> list[str]:
    without_markup = _HTML_TAG.sub("", html.unescape(value))
    normalized = unicodedata.normalize("NFKD", without_markup).casefold()
    return _TOKEN.findall(normalized)


def quote_is_grounded(quote: str, source_text: str) -> bool:
    """Deterministic v1 grounding robust to PDF layout order and glyph variants."""
    if _normalize(quote) in _normalize(source_text):
        return True
    quote_tokens = _tokens(quote)
    if not quote_tokens:
        return True
    source_tokens = set(_tokens(source_text))
    coverage = sum(token in source_tokens for token in quote_tokens) / len(quote_tokens)
    return coverage >= 0.8


def _resolve_document(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise SourcePreflightError(f"Document escapes the project root: {relative_path}")
    return candidate


def _extract_page_text(document_path: Path, page: int) -> str:
    command = [
        "pdftotext",
        "-f",
        str(page),
        "-l",
        str(page),
        "-layout",
        str(document_path),
        "-",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise SourcePreflightError(
            f"pdftotext failed for {document_path.name} page {page}: {detail}"
        )
    if not completed.stdout.strip():
        raise SourcePreflightError(
            f"No extractable text for {document_path.name} page {page}"
        )
    return completed.stdout


def build_context(task: dict[str, Any], root: Path) -> ComparativeContext:
    document_path = _resolve_document(root, task["local_path"])
    if not document_path.is_file():
        raise SourcePreflightError(f"Missing source PDF: {document_path}")
    actual_sha256 = sha256(document_path)
    if actual_sha256 != task["document_sha256"]:
        raise SourcePreflightError(
            f"Source PDF SHA256 mismatch for {task['task_id']}: "
            f"expected {task['document_sha256']}, got {actual_sha256}"
        )
    pages = tuple(task["pdf_pages"])
    if not pages or any(not isinstance(page, int) or page < 1 for page in pages):
        raise SourcePreflightError(f"Invalid page window for {task['task_id']}")
    page_text = {page: _extract_page_text(document_path, page) for page in pages}
    evidence = task.get("candidate_evidence") or {}
    evidence_page = evidence.get("pdf_page")
    quote = evidence.get("quote")
    joined = "\n".join(page_text.values())
    return ComparativeContext(
        task_id=task["task_id"],
        document_path=document_path,
        pages=pages,
        page_text=page_text,
        evidence_page_is_permitted=evidence_page is None or evidence_page in pages,
        evidence_quote_is_grounded=(
            not quote or quote_is_grounded(str(quote), joined)
        ),
    )


def _page_sections(context: ComparativeContext) -> str:
    return "\n\n".join(
        f"--- PDF page {page} ---\n{text.rstrip()}"
        for page, text in context.page_text.items()
    )


def build_messages(
    task: dict[str, Any], context: ComparativeContext, condition: str
) -> list[dict[str, Any]]:
    if condition not in {
        "plain_model_verifier",
        "ungated_pipeline_verifier",
        "sustaintrace_full",
    }:
        raise ComparativeProtocolError(f"Unknown condition: {condition}")

    common = (
        "Return JSON only, conforming exactly to the supplied schema. Judge only from the "
        "permitted PDF pages. Do not use outside knowledge. Do not infer a missing period, "
        "unit, boundary, method, assurance status, or evidence coordinate."
    )
    if condition == "plain_model_verifier":
        system = (
            "You verify whether a candidate statement is supported by a report excerpt. " + common
        )
        guidance = (
            "Choose the support label, the appropriate knowledge-base action, and Y/N/NA for "
            "each slot."
        )
    else:
        system = (
            "You are the frozen SustainTrace candidate-verification component. " + common
        )
        guidance = (
            "Support labels: fully_supported means every material populated element and its "
            "evidence coordinates are supported; partially_supported means the core meaning is "
            "supported but at least one material element is missing, wrong, or over-broad; "
            "unsupported means contradicted, mismatched, or not established; cannot_assess means "
            "the permitted window is insufficient; source_defect means the named source is "
            "missing or irreparably unreadable. Actions: admit only a complete supported atomic "
            "claim; correct_then_review when a bounded correction may be possible; reject an "
            "unsupported or non-atomic claim; abstain_or_conflict when trustworthy admission is "
            "not possible from the window. For abstention-audit candidates, fully_supported means "
            "the proposed refusal is correct; unsupported means the window actually contains an "
            "eligible fact. Mark all abstention-audit slots NA."
        )
    evidence = json.dumps(task.get("candidate_evidence", {}), ensure_ascii=False, sort_keys=True)
    user = (
        f"Condition: {condition}\n"
        f"Task ID: {task['task_id']}\n"
        f"Task stratum: {task['stratum']}\n"
        f"Company: {task['company']}\n"
        f"Report: {task['report_title']}\n"
        f"Candidate predicate: {task['candidate_predicate']}\n"
        f"Candidate claim: {task['candidate_claim']}\n"
        f"Declared candidate evidence: {evidence}\n"
        f"Instruction: {task['instruction']}\n\n"
        f"Decision guidance:\n{guidance}\n\n"
        f"Permitted source window:\n{_page_sections(context)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_messages_v2(
    task: dict[str, Any], context: ComparativeContext
) -> list[dict[str, Any]]:
    """Build the E2 prompt shared verbatim by every comparison condition."""
    evidence = json.dumps(
        task.get("candidate_evidence", {}), ensure_ascii=False, sort_keys=True
    )
    user = (
        f"Task ID: {task['task_id']}\n"
        f"Task stratum: {task['stratum']}\n"
        f"Company: {task['company']}\n"
        f"Report: {task['report_title']}\n"
        f"Candidate predicate: {task['candidate_predicate']}\n"
        f"Candidate claim: {task['candidate_claim']}\n"
        f"Declared candidate evidence: {evidence}\n"
        f"Instruction: {task['instruction']}\n\n"
        f"Permitted source window:\n{_page_sections(context)}"
    )
    return [
        {"role": "system", "content": contract_v2_instructions()},
        {"role": "user", "content": user},
    ]


def parse_model_decision(content: str) -> dict[str, Any]:
    try:
        parsed = parse_strict_json_content(content)
    except (json.JSONDecodeError, TypeError) as error:
        raise ModelBehaviorError("Model output is not strict JSON") from error
    if not isinstance(parsed, dict) or set(parsed) != {
        "support_label",
        "knowledge_base_action",
        "slots",
    }:
        raise ModelBehaviorError("Model output has unexpected top-level fields")
    if parsed["support_label"] not in SUPPORT_LABELS:
        raise ModelBehaviorError("Model output has an invalid support_label")
    if parsed["knowledge_base_action"] not in ACTION_LABELS:
        raise ModelBehaviorError("Model output has an invalid knowledge_base_action")
    slots = parsed.get("slots")
    if not isinstance(slots, dict) or set(slots) != set(SLOTS):
        raise ModelBehaviorError("Model output does not contain exactly seven slots")
    if any(value not in {"Y", "N", "NA"} for value in slots.values()):
        raise ModelBehaviorError("Model output has an invalid slot decision")
    return parsed


def apply_full_admission_gate(
    decision: dict[str, Any], context: ComparativeContext
) -> dict[str, Any]:
    """Block unsafe admission without rewriting the model's semantic judgement."""
    guarded = json.loads(json.dumps(decision))
    if guarded["knowledge_base_action"] != "admit":
        return guarded
    if (
        guarded["support_label"] != "fully_supported"
        or not context.evidence_page_is_permitted
        or not context.evidence_quote_is_grounded
    ):
        guarded["knowledge_base_action"] = "reject"
    return guarded


def apply_full_admission_gate_v3(
    decision: dict[str, Any],
    context: ComparativeContext,
    *,
    stratum: str,
    admission_contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply auditable admission controls to one frozen candidate decision.

    The contract is frozen with the task before model execution.  It may state
    whether this task class can produce an admitted fact and which semantic
    slots are mandatory.  The gate only changes the knowledge-base action; it
    preserves the model's support and slot judgements for paired analysis.
    """
    required_slots = admission_contract.get("required_slots")
    allow_admission = admission_contract.get("allow_admission")
    component_count = admission_contract.get("candidate_component_count")
    if not isinstance(allow_admission, bool):
        raise SourcePreflightError(
            f"{context.task_id}: admission_contract.allow_admission must be boolean"
        )
    if not isinstance(required_slots, list) or any(
        slot not in SLOTS for slot in required_slots
    ):
        raise SourcePreflightError(
            f"{context.task_id}: admission_contract.required_slots is invalid"
        )
    if len(required_slots) != len(set(required_slots)):
        raise SourcePreflightError(
            f"{context.task_id}: admission_contract.required_slots contains duplicates"
        )
    if (
        not isinstance(component_count, int)
        or isinstance(component_count, bool)
        or component_count < 0
    ):
        raise SourcePreflightError(
            f"{context.task_id}: admission_contract.candidate_component_count is invalid"
        )

    guarded = json.loads(json.dumps(decision))
    checks = {
        "model_requested_admission": decision["knowledge_base_action"] == "admit",
        "task_class_allows_admission": allow_admission,
        "not_abstention_audit": stratum != "abstention_audit",
        "claim_is_atomic": component_count == 1,
        "support_is_fully_supported": decision["support_label"] == "fully_supported",
        "evidence_page_is_permitted": context.evidence_page_is_permitted,
        "evidence_quote_is_grounded": context.evidence_quote_is_grounded,
        "required_slots_are_supported": all(
            decision["slots"].get(slot) == "Y" for slot in required_slots
        ),
        "no_negative_slot": all(value != "N" for value in decision["slots"].values()),
    }
    reason_codes = [name for name, passed in checks.items() if not passed]
    if not checks["model_requested_admission"]:
        outcome = "not_applicable_model_did_not_admit"
    elif not reason_codes:
        outcome = "admission_preserved"
    else:
        if (
            not checks["task_class_allows_admission"]
            or not checks["not_abstention_audit"]
            or not checks["claim_is_atomic"]
            or not checks["evidence_page_is_permitted"]
            or not checks["evidence_quote_is_grounded"]
            or decision["support_label"] == "unsupported"
        ):
            guarded["knowledge_base_action"] = "reject"
        elif decision["support_label"] in {"cannot_assess", "source_defect"}:
            guarded["knowledge_base_action"] = "abstain_or_conflict"
        else:
            guarded["knowledge_base_action"] = "correct_then_review"
        outcome = "admission_blocked"
    return guarded, {
        "schema_version": "1.0",
        "outcome": outcome,
        "input_action": decision["knowledge_base_action"],
        "output_action": guarded["knowledge_base_action"],
        "checks": checks,
        "reason_codes": reason_codes,
        "required_slots": required_slots,
    }


def execute_task_paired_v3(
    task: dict[str, Any],
    root: Path,
    client: OllamaClient,
    *,
    raw_archive: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Generate once, then evaluate ungated and full paths as a paired outcome."""
    context = build_context(task, root)
    admission_contract = task.get("admission_contract")
    if not isinstance(admission_contract, dict):
        raise SourcePreflightError(
            f"{task['task_id']}: frozen admission_contract is required for paired v3"
        )
    messages = build_messages_v2(task, context)
    result: OllamaResult = client.chat(messages, schema=MODEL_OUTPUT_SCHEMA, think=False)
    content = result.response.get("message", {}).get("content")
    if not isinstance(content, str):
        raise ModelBehaviorError("Ollama response has no string message.content")
    raw_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if raw_archive is not None:
        raw_archive(
            {
                "task_id": task["task_id"],
                "prompt_contract_id": CONTRACT_V2_ID,
                "request_sha256": result.request_sha256,
                "raw_response_sha256": raw_sha256,
                "elapsed_seconds": result.elapsed_seconds,
                "response": result.response,
                "deterministic_evidence_checks": {
                    "evidence_page_is_permitted": context.evidence_page_is_permitted,
                    "evidence_quote_is_grounded": context.evidence_quote_is_grounded,
                },
            }
        )
    ungated = parse_model_decision(content)
    full, gate_audit = apply_full_admission_gate_v3(
        ungated,
        context,
        stratum=task["stratum"],
        admission_contract=admission_contract,
    )
    return {
        "task_id": task["task_id"],
        "execution_status": "completed",
        "ungated_decision": ungated,
        "sustaintrace_full_decision": full,
        "gate_audit": gate_audit,
        "latency_ms": round(result.elapsed_seconds * 1000, 3),
        "usage": {
            "input_tokens": int(result.response.get("prompt_eval_count", 0)),
            "output_tokens": int(result.response.get("eval_count", 0)),
            "estimated_cost_usd": None,
        },
        "raw_response_sha256": raw_sha256,
    }


def execute_task(
    task: dict[str, Any],
    condition: str,
    root: Path,
    client: OllamaClient,
    *,
    raw_archive: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    context = build_context(task, root)
    messages = build_messages(task, context, condition)
    result: OllamaResult = client.chat(messages, schema=MODEL_OUTPUT_SCHEMA, think=False)
    content = result.response.get("message", {}).get("content")
    if not isinstance(content, str):
        raise ModelBehaviorError("Ollama response has no string message.content")
    raw_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if raw_archive is not None:
        raw_archive(
            {
                "task_id": task["task_id"],
                "condition": condition,
                "request_sha256": result.request_sha256,
                "raw_response_sha256": raw_sha256,
                "elapsed_seconds": result.elapsed_seconds,
                "response": result.response,
                "deterministic_evidence_checks": {
                    "evidence_page_is_permitted": context.evidence_page_is_permitted,
                    "evidence_quote_is_grounded": context.evidence_quote_is_grounded,
                },
            }
        )
    decision = parse_model_decision(content)
    if condition == "sustaintrace_full":
        decision = apply_full_admission_gate(decision, context)
    return {
        "task_id": task["task_id"],
        "execution_status": "completed",
        **decision,
        "latency_ms": round(result.elapsed_seconds * 1000, 3),
        "usage": {
            "input_tokens": int(result.response.get("prompt_eval_count", 0)),
            "output_tokens": int(result.response.get("eval_count", 0)),
            "estimated_cost_usd": None,
        },
        "raw_response_sha256": raw_sha256,
    }


def execute_task_v2(
    task: dict[str, Any],
    condition: str,
    root: Path,
    client: OllamaClient,
    *,
    raw_archive: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Execute one E2 candidate using a condition-invariant visible contract."""
    if condition not in {
        "plain_model_verifier",
        "ungated_pipeline_verifier",
        "sustaintrace_full",
    }:
        raise ComparativeProtocolError(f"Unknown condition: {condition}")
    context = build_context(task, root)
    messages = build_messages_v2(task, context)
    result: OllamaResult = client.chat(messages, schema=MODEL_OUTPUT_SCHEMA, think=False)
    content = result.response.get("message", {}).get("content")
    if not isinstance(content, str):
        raise ModelBehaviorError("Ollama response has no string message.content")
    raw_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if raw_archive is not None:
        raw_archive(
            {
                "task_id": task["task_id"],
                "condition": condition,
                "prompt_contract_id": CONTRACT_V2_ID,
                "request_sha256": result.request_sha256,
                "raw_response_sha256": raw_sha256,
                "elapsed_seconds": result.elapsed_seconds,
                "response": result.response,
                "deterministic_evidence_checks": {
                    "evidence_page_is_permitted": context.evidence_page_is_permitted,
                    "evidence_quote_is_grounded": context.evidence_quote_is_grounded,
                },
            }
        )
    decision = parse_model_decision(content)
    if condition == "sustaintrace_full":
        decision = apply_full_admission_gate(decision, context)
    return {
        "task_id": task["task_id"],
        "execution_status": "completed",
        **decision,
        "latency_ms": round(result.elapsed_seconds * 1000, 3),
        "usage": {
            "input_tokens": int(result.response.get("prompt_eval_count", 0)),
            "output_tokens": int(result.response.get("eval_count", 0)),
            "estimated_cost_usd": None,
        },
        "raw_response_sha256": raw_sha256,
    }
