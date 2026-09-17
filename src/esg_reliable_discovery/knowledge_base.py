from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(canonical.encode()).hexdigest()[:24]}"


def canonicalize_predicate(raw_key: str) -> tuple[str, str | None]:
    """Split the established ``metric::period`` convention without changing its meaning."""
    if "::" not in raw_key:
        return raw_key, None
    metric, period = raw_key.rsplit("::", 1)
    if re.fullmatch(r"(?:fy)?\d{4}(?:/\d{2,4})?", period, flags=re.IGNORECASE):
        return metric, period
    return raw_key, None


def iter_normalized_values(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        yield from sorted(value.items())
    elif value is not None:
        yield "normalized_value", value


def reference_to_fact_records(
    path: Path, root: Path, document_index: dict[str, dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    task_id = payload.get("task_id")
    normalized = payload.get("normalized_value")
    if not isinstance(task_id, str) or normalized is None:
        return []

    evidence = []
    for item in payload.get("evidence", []):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        if "source_id" not in normalized_item and isinstance(
            normalized_item.get("document_id"), str
        ):
            normalized_item["source_id"] = normalized_item["document_id"]
        if (
            isinstance(normalized_item.get("source_id"), str)
            and isinstance(normalized_item.get("pdf_page"), int)
            and normalized_item["pdf_page"] >= 1
            and isinstance(normalized_item.get("quote"), str)
            and bool(normalized_item["quote"].strip())
        ):
            evidence.append(normalized_item)
    document_ids = sorted(
        {item["source_id"] for item in evidence if isinstance(item.get("source_id"), str)}
    )
    document_index = document_index or {}
    document_metadata = [document_index[item] for item in document_ids if item in document_index]
    simulated = bool(payload.get("provenance", {}).get("reference_is_simulated", True))
    source_artifact = path.relative_to(root).as_posix()
    source_sha256 = sha256_file(path)
    reference_context = {
        "reference_period": payload.get("period"),
        "normalized_unit": payload.get("normalized_unit"),
        "scope_boundary": payload.get("scope_boundary"),
        "calculation_expression": payload.get("calculation"),
        "answer_status": payload.get("answer_status"),
    }
    records = []
    for raw_key, value in iter_normalized_values(normalized):
        canonical_key, period = canonicalize_predicate(raw_key)
        identity = {"source": source_artifact, "task_id": task_id, "predicate": raw_key}
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "fact",
                "record_id": stable_id("fact", identity),
                "knowledge_status": "reference_candidate",
                "trust_tier": "C" if simulated else "B",
                "subject": {
                    "task_id": task_id,
                    "entity_label": payload.get("subject"),
                    "document_ids": document_ids,
                    "document_metadata": document_metadata,
                },
                "predicate": {"raw_key": raw_key, "canonical_key": canonical_key},
                "value": value,
                "qualifiers": {
                    "period_literal": period,
                    "value_origin": "simulated_reference" if simulated else "curated_reference",
                    **reference_context,
                },
                "evidence": evidence,
                "provenance": {
                    "source_artifact": source_artifact,
                    "source_sha256": source_sha256,
                    "reference_status": payload.get("reference_status"),
                    "simulated": simulated,
                },
                "promotion": {
                    "eligible": False,
                    "reason": "requires_independent_fact_promotion_audit",
                },
            }
        )
    return records


def _contains_failure(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.casefold()
        return "fail" in lowered or "error" in lowered or "invalid" in lowered
    if isinstance(value, dict):
        return any(_contains_failure(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_failure(item) for item in value)
    return False


def _normalize_owner(task_state: dict[str, Any]) -> str:
    raw = task_state.get("failure_owner", task_state.get("integrity_owner", "unknown"))
    aliases = {
        "none": "unknown",
        "model": "candidate_model",
        "candidate": "candidate_model",
        "parser": "document_pipeline",
    }
    normalized = aliases.get(str(raw), str(raw))
    allowed = {"candidate_model", "framework", "document_pipeline", "infrastructure"}
    if normalized in allowed:
        return normalized
    text = json.dumps(task_state, ensure_ascii=False, sort_keys=True).casefold()
    if any(token in text for token in ("mineru", "parser", "text was corrupted")):
        return "document_pipeline"
    if any(
        token in text
        for token in (
            "pre_model_framework_failure",
            "frozen_configuration_failure",
            "post-call framework failure",
            "missing predicate_id",
        )
    ):
        return "framework"
    if any(token in text for token in ("model_behavior_fail", "candidate ", "model ")):
        return "candidate_model"
    stage_b = task_state.get("stage_b")
    stage_a = task_state.get("stage_a", task_state.get("stage_a_framework"))
    if (
        isinstance(stage_b, str)
        and _contains_failure(stage_b)
        and isinstance(stage_a, str)
        and not _contains_failure(stage_a)
    ):
        return "candidate_model"
    return "unknown"


def _failure_category(owner: str, diagnostic_text: str) -> str:
    text = diagnostic_text.casefold()
    if owner == "candidate_model":
        return "model_behavior"
    if owner == "framework":
        return "executor_or_configuration"
    if owner == "document_pipeline":
        return "parser_or_document_structure"
    if owner == "infrastructure":
        return "cloud_transport"
    if any(token in text for token in ("reference", "gold", "page window", "page_window")):
        return "reference_integrity"
    if any(
        token in text
        for token in ("retrieval", "selected prior-period block", "evidence selection")
    ):
        return "retrieval_or_evidence_selection"
    if any(token in text for token in ("mineru", "parser", "structure_unrecoverable")):
        return "parser_or_document_structure"
    if any(token in text for token in ("transport", "timed out", "timeout", "http 502")):
        return "cloud_transport"
    return "unknown"


def derive_failure_signature(
    owner: str, category: str, task_state: dict[str, Any], diagnostic_text: str
) -> str:
    text = (json.dumps(task_state, ensure_ascii=False, sort_keys=True) + diagnostic_text).casefold()
    if category == "parser_or_document_structure":
        if any(token in text for token in ("table", "column", "misalign")):
            return "PARSER_TABLE_STRUCTURE"
        return "PARSER_CONTENT_OMISSION"
    if category == "retrieval_or_evidence_selection":
        return "EVIDENCE_SELECTION_GAP"
    if owner == "framework":
        if any(token in text for token in ("attributeerror", "has no attribute", "plain strings")):
            return "EXECUTOR_TYPE_MISMATCH"
        if any(token in text for token in ("alias", "canonical_handle", "canonical handle")):
            return "HANDLE_CANONICALIZATION_MISMATCH"
        if any(token in text for token in ("pre_model", "required-term gate", "required term")):
            return "PREFLIGHT_CONTRACT_GATE"
        if any(
            token in text
            for token in (
                "missing predicate_id",
                "frozen contract missing",
                "slot contract omitted",
            )
        ):
            return "FROZEN_CONTRACT_INCOMPLETE"
        return "FRAMEWORK_EXECUTION_FAILURE"
    if owner == "candidate_model":
        if any(token in text for token in ("unmapped_calculation_handle", "unmapped calculation")):
            return "CALCULATION_HANDLE_UNMAPPED"
        if "task_id" in text and any(token in text for token in ("omitted", "missing", "wrong")):
            return "TASK_IDENTITY_OMISSION"
        if any(token in text for token in ("collection", "plain strings", "scalar string")):
            return "COLLECTION_SHAPE_VIOLATION"
        if any(token in text for token in ("calculation", "comparison_value", "percentage_change")):
            return "CALCULATION_CONTRACT_VIOLATION"
        if any(token in text for token in ("empty_claims", "no claims")):
            return "EMPTY_KNOWLEDGE_PROJECTION"
        if any(token in text for token in ("ontology", "metric_unit", "period_grounding")):
            return "SEMANTIC_PROJECTION_MISMATCH"
        if any(token in text for token in ("grounding", "truncated", "not_exact", "rounded")):
            return "EVIDENCE_GROUNDING_MISMATCH"
        if "abstain" in text:
            return "UNSUPPORTED_ABSTENTION"
        if any(token in text for token in ("schema", "extra_property", "unsupported")):
            return "SCHEMA_CONTRACT_VIOLATION"
        return "MODEL_OUTPUT_FAILURE"
    if category == "reference_integrity":
        return "REFERENCE_INTEGRITY_FAILURE"
    if category == "cloud_transport":
        return "CLOUD_TRANSPORT_FAILURE"
    return "UNADJUDICATED_FAILURE"


def result_to_failure_records(path: Path, root: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    experiment_id = payload.get("experiment_id", path.stem)
    task_results_raw = payload.get("task_results", {})
    if isinstance(task_results_raw, list):
        task_results = {
            state["task_id"]: state
            for state in task_results_raw
            if isinstance(state, dict) and isinstance(state.get("task_id"), str)
        }
    elif isinstance(task_results_raw, dict):
        task_results = task_results_raw
    else:
        return []
    diagnostic_keys = (
        "integrity_finding",
        "integrity_findings",
        "framework_findings",
        "infrastructure",
        "reference_adjudication",
        "decision",
        "status",
    )
    diagnostics = [{key: payload[key]} for key in diagnostic_keys if key in payload]
    diagnostic_text = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)
    source_artifact = path.relative_to(root).as_posix()
    source_sha256 = sha256_file(path)
    records = []
    for task_id, state in sorted(task_results.items()):
        if not isinstance(state, dict) or not _contains_failure(state):
            continue
        owner = _normalize_owner(state)
        combined_diagnostics = diagnostic_text + json.dumps(
            state, ensure_ascii=False, sort_keys=True
        )
        category = _failure_category(owner, combined_diagnostics)
        identity = {"source": source_artifact, "experiment": experiment_id, "task": task_id}
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "failure_observation",
                "record_id": stable_id("failure", identity),
                "experiment_id": str(experiment_id),
                "task_id": str(task_id),
                "failure_owner": owner,
                "failure_category": category,
                "failure_signature": derive_failure_signature(
                    owner, category, state, diagnostic_text
                ),
                "observed_stage_states": state,
                "diagnostics": diagnostics,
                "provenance": {
                    "source_artifact": source_artifact,
                    "source_sha256": source_sha256,
                },
            }
        )
    return records


def development_result_to_repair_observation(path: Path, root: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_artifact = path.relative_to(root).as_posix()
    identity = {"source": source_artifact, "sha256": sha256_file(path)}
    change = next(
        (
            payload[key]
            for key in ("change", "changes", "implemented", "features", "mechanisms", "results")
            if key in payload
        ),
        {},
    )
    validation = next(
        (
            payload[key]
            for key in ("validation", "tests", "regression", "test_result")
            if key in payload
        ),
        {},
    )
    if "ruff_result" in payload:
        if not isinstance(validation, dict):
            validation = {"test_result": validation}
        validation = {**validation, "ruff_result": payload["ruff_result"]}
    return {
        "schema_version": "0.1",
        "record_kind": "repair_observation",
        "record_id": stable_id("repair", identity),
        "development_source": payload.get(
            "development_source", payload.get("development_input", payload.get("experiment_id"))
        ),
        "status": payload.get("status"),
        "change": change,
        "validation": validation,
        "automation_eligibility": {
            "allowed": False,
            "reason": "historical_observation_requires_strategy_adjudication",
        },
        "provenance": {
            "source_artifact": source_artifact,
            "source_sha256": sha256_file(path),
        },
    }


def validate_records(records: Iterable[dict[str, Any]], schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    for index, record in enumerate(records):
        errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
        if errors:
            messages = "; ".join(error.message for error in errors)
            raise ValueError(f"record {index} failed schema validation: {messages}")


def normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[`*_#|]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def quote_matches(quote: str, page_text: str) -> bool:
    fragments = [
        normalized_text(fragment)
        for fragment in re.split(r"(?:\.{3}|…)", quote)
        if normalized_text(fragment)
    ]
    if not fragments:
        return False
    cursor = 0
    for fragment in fragments:
        position = page_text.find(fragment, cursor)
        if position < 0:
            return False
        cursor = position + len(fragment)
    return True


def build_parser_page_index(
    registry_paths: Iterable[Path],
    root: Path,
    fallback_document_ids: dict[int, str] | None = None,
) -> dict[tuple[str, int], dict[str, Any]]:
    fallback_document_ids = fallback_document_ids or {}
    index: dict[tuple[str, int], dict[str, Any]] = {}
    for registry_path in registry_paths:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        phase_match = re.search(r"p(\d+)_", registry_path.name)
        phase = int(phase_match.group(1)) if phase_match else -1
        top_document_id = payload.get("document_id", fallback_document_ids.get(phase))
        entries = payload.get("targets") if isinstance(payload.get("targets"), list) else None
        if entries is None:
            entries = payload.get("pages", [])
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            document_id = entry.get("document_id", top_document_id)
            page = entry.get("pdf_page", entry.get("page"))
            if not isinstance(document_id, str) or not isinstance(page, int):
                continue
            markdown_paths = []
            if isinstance(entry.get("markdown"), str):
                markdown_paths.append(root / entry["markdown"])
            if isinstance(entry.get("output_directory"), str):
                output_directory = root / entry["output_directory"]
                if output_directory.exists():
                    markdown_paths.extend(sorted(output_directory.rglob("*.md")))
            markdown_path = next((path for path in markdown_paths if path.is_file()), None)
            declared_hash = entry.get("markdown_sha256")
            actual_hash = sha256_file(markdown_path) if markdown_path else None
            index[(document_id, page)] = {
                "registry_path": registry_path.relative_to(root).as_posix(),
                "markdown_path": (
                    markdown_path.relative_to(root).as_posix() if markdown_path else None
                ),
                "declared_sha256": declared_hash,
                "actual_sha256": actual_hash,
                "hash_valid": declared_hash is None or declared_hash == actual_hash,
                "normalized_text": (
                    normalized_text(markdown_path.read_text(encoding="utf-8", errors="replace"))
                    if markdown_path
                    else None
                ),
            }
    return index


def build_native_page_index(
    registry_paths: Iterable[Path],
    root: Path,
    fallback_document_ids: dict[int, str],
) -> dict[tuple[str, int], dict[str, Any]]:
    index: dict[tuple[str, int], dict[str, Any]] = {}
    for registry_path in registry_paths:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        phase_match = re.search(r"p(\d+)_", registry_path.name)
        phase = int(phase_match.group(1)) if phase_match else -1
        document_id = fallback_document_ids.get(phase)
        if not document_id:
            continue
        entries = payload.get("outputs")
        output_root = None
        if not isinstance(entries, list):
            fallback = payload.get("native_pdf_fallback", {})
            entries = fallback.get("pages", [])
            output_root = fallback.get("output_root")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("page"), int):
                continue
            page = entry["page"]
            path_value = entry.get("path")
            if isinstance(path_value, str):
                text_path = root / path_value
            elif isinstance(output_root, str):
                candidates = sorted((root / output_root).glob(f"*-p{page:04d}.txt"))
                text_path = candidates[0] if candidates else None
            else:
                text_path = None
            declared_hash = entry.get("sha256")
            actual_hash = sha256_file(text_path) if text_path and text_path.is_file() else None
            index[(document_id, page)] = {
                "registry_path": registry_path.relative_to(root).as_posix(),
                "markdown_path": text_path.relative_to(root).as_posix() if text_path else None,
                "declared_sha256": declared_hash,
                "actual_sha256": actual_hash,
                "hash_valid": declared_hash is None or declared_hash == actual_hash,
                "normalized_text": (
                    normalized_text(text_path.read_text(encoding="utf-8", errors="replace"))
                    if text_path and text_path.is_file()
                    else None
                ),
            }
    return index


def audit_fact_source_grounding(
    fact: dict[str, Any],
    parser_page_index: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    unmatched = []
    registered_documents = 0
    located_pages = 0
    matched_quotes = 0
    valid_hashes = 0
    for evidence in fact["evidence"]:
        source_id = evidence["source_id"]
        page = evidence["pdf_page"]
        entry = parser_page_index.get((source_id, page))
        if any(
            item.get("document_id") == source_id
            for item in fact["subject"].get("document_metadata", [])
        ):
            registered_documents += 1
        if entry is None or entry["normalized_text"] is None:
            unmatched.append({"source_id": source_id, "pdf_page": page, "reason": "missing_page"})
            continue
        located_pages += 1
        if entry["hash_valid"]:
            valid_hashes += 1
        else:
            unmatched.append(
                {"source_id": source_id, "pdf_page": page, "reason": "parser_hash_mismatch"}
            )
            continue
        if quote_matches(evidence["quote"], entry["normalized_text"]):
            matched_quotes += 1
        else:
            unmatched.append(
                {
                    "source_id": source_id,
                    "pdf_page": page,
                    "quote": evidence["quote"],
                    "reason": "quote_not_found",
                }
            )

    evidence_count = len(fact["evidence"])
    reasons = {item["reason"] for item in unmatched}
    if "parser_hash_mismatch" in reasons:
        status = "hash_mismatch"
    elif "missing_page" in reasons:
        status = "missing_parser_artifact"
    elif "quote_not_found" in reasons:
        status = "failed_quote"
    else:
        status = "passed"
    return {
        "schema_version": "0.1",
        "record_kind": "fact_promotion_audit",
        "fact_record_id": fact["record_id"],
        "source_grounding_status": status,
        "checks": {
            "evidence_items": evidence_count,
            "registered_documents": registered_documents,
            "located_parser_pages": located_pages,
            "matched_quotes": matched_quotes,
            "parser_hashes_valid": valid_hashes,
        },
        "unmatched_evidence": unmatched,
        "promotion_decision": {
            "eligible": False,
            "target_tier": "B",
            "reason": "field_level_semantic_evidence_binding_not_yet_available",
        },
    }


def json_value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def scalar_literal_variants(value: Any) -> list[str]:
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, int):
        grouped = f"{abs(value):,}"
        sign = "-" if value < 0 else ""
        return sorted(
            {
                str(value),
                sign + grouped,
                sign + grouped.replace(",", " "),
                sign + grouped.replace(",", "\u202f"),
            }
        )
    if isinstance(value, float):
        literal = format(value, ".15g")
        return [literal]
    if isinstance(value, str) and len(normalized_text(value)) >= 4:
        return [value]
    return []


def _literal_in_quote(literal: str, quote: str, *, numeric: bool) -> bool:
    normalized_literal = normalized_text(literal)
    normalized_quote = normalized_text(quote)
    if not normalized_literal:
        return False
    if not numeric:
        return normalized_literal in normalized_quote
    pattern = rf"(?<![\d.]){re.escape(normalized_literal)}(?![\d.])"
    return re.search(pattern, normalized_quote) is not None


def bind_fact_field_to_evidence(
    fact: dict[str, Any], source_audit: dict[str, Any]
) -> dict[str, Any]:
    value = fact["value"]
    value_type = json_value_type(value)
    if source_audit["source_grounding_status"] != "passed":
        status = "source_grounding_failed"
        matches: list[int] = []
        reason = "task_level_source_grounding_did_not_pass"
    elif value_type in {"array", "object", "boolean", "null"}:
        status = "unsupported_complex_value"
        matches = []
        reason = "requires_structural_or_semantic_binding_not_literal_matching"
    else:
        variants = scalar_literal_variants(value)
        matches = [
            index
            for index, evidence in enumerate(fact["evidence"])
            if any(
                _literal_in_quote(variant, evidence["quote"], numeric=value_type == "number")
                for variant in variants
            )
        ]
        if len(matches) == 1:
            status = "unique_literal"
            reason = "one_task_evidence_item_contains_the_exact_scalar_literal"
        elif len(matches) > 1:
            status = "multiple_literal"
            reason = "scalar_literal_occurs_in_multiple_task_evidence_items"
        else:
            status = "literal_not_found"
            reason = "scalar_literal_not_present_in_any_grounded_task_evidence_quote"
    return {
        "schema_version": "0.1",
        "record_kind": "field_evidence_binding",
        "fact_record_id": fact["record_id"],
        "binding_status": status,
        "value_type": value_type,
        "matched_evidence_indices": matches,
        "promotion_eligible": False,
        "reason": reason,
    }


def _semantic_task_qualifier(task_id: str, semantic_catalog: dict[str, Any]) -> Any:
    return semantic_catalog.get(task_id)


def _predicate_declares_unit(predicate: str) -> bool:
    tokens = {
        "percent",
        "percentage",
        "tco2e",
        "co2e",
        "mtco2e",
        "ktco2e",
        "mwh",
        "gwh",
        "m3",
        "litres",
        "liters",
        "tonnes",
        "tonne",
        "employees",
        "fatalities",
        "count",
        "eur",
        "usd",
        "rate",
        "share",
        "kg",
        "tons",
        "ton",
        "mmwh",
        "mdkk",
        "mchf",
        "fte",
        "headcount",
        "deaths",
        "fatality",
        "accidents",
        "cases",
        "patients",
        "countries",
        "facilities",
        "partnerships",
        "beneficiaries",
        "hours",
        "year",
        "kt",
        "mtco2",
        "frequency",
        "ffr",
        "trir",
        "aifr",
        "ltir",
        "etir",
        "months",
        "levels",
        "category",
        "period",
    }
    parts = set(re.split(r"[^a-z0-9]+", predicate.casefold()))
    return bool(parts & tokens)


def normalized_unit_markers(unit: Any) -> list[str]:
    """Return conservative literal markers for a scalar normalized unit."""
    if not isinstance(unit, str) or unit.casefold() == "mixed":
        return []
    lowered = unit.casefold().replace("_", " ")
    markers = {lowered}
    if "percent" in lowered:
        markers.update({"%", "percent", "percentage"})
    if "tco2e" in lowered or "co2e" in lowered:
        markers.update({"tco2e", "co2e", "co₂e"})
    if "cubic meter" in lowered or "m3" in lowered:
        markers.update({"m3", "m³", "cubic metres", "cubic meters"})
    if "tonne" in lowered:
        markers.update({"tonne", "tonnes"})
    return sorted(marker for marker in markers if marker)


def unit_marker_present(unit: Any, text: str) -> bool:
    normalized = normalized_text(text)
    return any(normalized_text(marker) in normalized for marker in normalized_unit_markers(unit))


def _year_tokens(value: Any) -> list[str]:
    return sorted(set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", str(value or ""))))


def _numeric_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return False
    return abs(float(left) - float(right)) <= max(1e-9, abs(float(left)) * 1e-9)


def qualify_fact_jointly(
    fact: dict[str, Any],
    field_binding: dict[str, Any],
    semantic_catalog: dict[str, Any],
    calculation_catalog: dict[str, Any],
    table_graphs: list[dict[str, Any]],
    calculation_replays: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Conservatively join literal, qualifier, calculation and table evidence.

    This function inventories qualification only. It deliberately cannot promote a
    simulated reference into a validated fact without an independent adjudication.
    """
    task_id = fact["subject"]["task_id"]
    predicate = fact["predicate"]["raw_key"]
    qualifiers = fact.get("qualifiers", {})
    evidence_indices = field_binding.get("matched_evidence_indices", [])
    matched_evidence = [
        fact["evidence"][index]
        for index in evidence_indices
        if isinstance(index, int) and 0 <= index < len(fact["evidence"])
    ]
    matched_text = " ".join(item.get("quote", "") for item in matched_evidence)

    period_value = qualifiers.get("period_literal") or qualifiers.get("reference_period")
    years = _year_tokens(period_value)
    if qualifiers.get("period_literal") and years and all(year in matched_text for year in years):
        period = {
            "status": "exact_in_bound_quote",
            "reason": "predicate period occurs in the uniquely bound evidence quote",
        }
    elif qualifiers.get("period_literal"):
        period = {
            "status": "predicate_declared",
            "reason": (
                "period is encoded in the normalized predicate but not jointly localized "
                "in the quote"
            ),
        }
    elif qualifiers.get("reference_period") is not None:
        period = {
            "status": "reference_task_level",
            "reason": "reference preserves a task-level period without field-level localization",
        }
    elif _semantic_task_qualifier(task_id, semantic_catalog) is not None:
        period = {
            "status": "semantic_task_level",
            "reason": "frozen semantic qualifiers provide task context only",
        }
    else:
        period = {"status": "not_declared", "reason": "no field or task period qualifier was found"}

    unit_value = qualifiers.get("normalized_unit")
    if _predicate_declares_unit(predicate):
        unit = {
            "status": "predicate_declared",
            "reason": "the normalized predicate explicitly encodes a controlled unit or measure",
        }
    elif unit_value is not None:
        unit = {
            "status": "reference_task_level",
            "reason": "the reference preserves a task-level normalized unit",
        }
    elif not isinstance(fact.get("value"), (int, float)) or isinstance(fact.get("value"), bool):
        unit = {
            "status": "not_required_non_numeric",
            "reason": "unit qualification is not required for this non-numeric value",
        }
    else:
        unit = {"status": "not_declared", "reason": "numeric value has no explicit normalized unit"}

    semantic = _semantic_task_qualifier(task_id, semantic_catalog)
    boundary_key = any(
        token in predicate.casefold()
        for token in ("boundary", "scope", "method", "assur", "coverage")
    )
    if boundary_key and field_binding.get("binding_status") == "unique_literal":
        boundary = {
            "status": "self_describing_literal",
            "reason": "the bound field itself records a boundary or method",
        }
    elif qualifiers.get("scope_boundary") is not None:
        boundary = {
            "status": "reference_task_level",
            "reason": "scope boundary is preserved at task level, not uniquely bound to the scalar",
        }
    elif semantic is not None:
        boundary = {
            "status": "semantic_task_level",
            "reason": "frozen semantic qualifier provides task-level boundary context",
        }
    else:
        boundary = {"status": "not_declared", "reason": "no boundary qualifier was found"}

    plan = calculation_catalog.get(task_id)
    calculation_replays = calculation_replays or {}
    output_slots = (
        {
            item.get("slot_id"): item.get("source_value_id")
            for item in plan.get("output_slot_map", [])
            if isinstance(item, dict)
        }
        if isinstance(plan, dict)
        else {}
    )
    if predicate in output_slots:
        origin = "deterministically_derived_candidate"
        replay = calculation_replays.get((task_id, predicate))
        if replay and replay.get("status") == "passed":
            calculation = {
                "status": "frozen_plan_replayed",
                "reason": "frozen selected cells and calculation plan reproduce this output",
                "source_value_id": output_slots[predicate],
                "replayed_actual": replay.get("actual"),
            }
        else:
            calculation = {
                "status": "frozen_plan_output",
                "reason": (
                    "predicate is an output slot in the frozen deterministic calculation plan"
                ),
                "source_value_id": output_slots[predicate],
            }
    elif qualifiers.get("calculation_expression") is not None:
        origin = "legacy_expression_candidate"
        calculation = {
            "status": "legacy_expression_only",
            "reason": "a reference formula exists but is not a replayable field-level frozen plan",
        }
    else:
        origin = "direct_source_candidate"
        calculation = {
            "status": "not_required_direct",
            "reason": "field is not declared as a deterministic calculation output",
        }

    pages = {item.get("pdf_page") for item in matched_evidence}
    graph_matches = []
    graphs_on_page = []
    for graph in table_graphs:
        if graph.get("pdf_page") not in pages:
            continue
        graphs_on_page.append(graph)
        for cell in graph.get("selected_cells", []):
            if (
                isinstance(cell, list)
                and len(cell) == 3
                and _numeric_equal(cell[2], fact.get("value"))
            ):
                graph_matches.append(
                    {
                        "graph_id": graph.get("graph_id"),
                        "pdf_page": graph.get("pdf_page"),
                        "row": cell[0],
                        "column": cell[1],
                        "value": cell[2],
                        "bbox": graph.get("bbox"),
                    }
                )
    if len(graph_matches) == 1:
        table = {
            "status": "unique_selected_cell",
            "reason": (
                "one frozen row-column-value cell matches the bound numeric value and evidence page"
            ),
            "matches": graph_matches,
        }
    elif len(graph_matches) > 1:
        table = {
            "status": "ambiguous_selected_cells",
            "reason": "the same value maps to multiple frozen cells",
            "matches": graph_matches,
        }
    elif graphs_on_page and isinstance(fact.get("value"), (int, float)):
        table = {
            "status": "graph_present_cell_unbound",
            "reason": (
                "a table graph exists on the evidence page but no unique selected cell "
                "binds this value"
            ),
            "matches": [],
        }
    else:
        table = {
            "status": "not_applicable_or_unavailable",
            "reason": "no selected-cell graph applies to the bound evidence page",
            "matches": [],
        }

    scalar = field_binding.get("value_type") in {"number", "string"}
    checks_sufficient = (
        field_binding.get("binding_status") == "unique_literal"
        and period["status"] != "not_declared"
        and unit["status"] != "not_declared"
        and boundary["status"] != "not_declared"
        and calculation["status"] != "legacy_expression_only"
        and table["status"] not in {"ambiguous_selected_cells", "graph_present_cell_unbound"}
    )
    if not scalar:
        qualification_status = "not_applicable_non_scalar"
    elif checks_sufficient:
        qualification_status = "jointly_qualified_candidate"
    else:
        qualification_status = "incomplete_qualification"
    return {
        "schema_version": "0.1",
        "record_kind": "joint_fact_qualification",
        "fact_record_id": fact["record_id"],
        "task_id": task_id,
        "field_binding_status": field_binding["binding_status"],
        "period_binding": period,
        "unit_binding": unit,
        "boundary_binding": boundary,
        "value_origin": origin,
        "calculation_lineage": calculation,
        "table_cell_binding": table,
        "qualification_status": qualification_status,
        "promotion_decision": {
            "eligible": False,
            "target_tier": "B",
            "reason": (
                "simulated_reference_requires_independent_adjudication_even_when_joint_checks_pass"
            ),
        },
    }


def _cell_for_handle(
    handle: str,
    table_graphs: list[dict[str, Any]],
    *,
    role: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any] | None:
    match = re.fullmatch(r"M(\d+)-T\d+-R(\d+)-C(\d+)", handle)
    if not match:
        return None
    page, row_index, column_index = map(int, match.groups())
    candidates = []
    for graph in table_graphs:
        if graph.get("pdf_page") != page:
            continue
        rows = graph.get("row_axis", [])
        columns = graph.get("header_axis", [])
        if not (1 <= row_index <= len(rows) and 1 <= column_index <= len(columns)):
            continue
        row, column = rows[row_index - 1], columns[column_index - 1]
        for cell in graph.get("selected_cells", []):
            if isinstance(cell, list) and len(cell) == 3 and cell[:2] == [row, column]:
                candidates.append(
                    {
                        "handle": handle,
                        "graph_id": graph.get("graph_id"),
                        "pdf_page": page,
                        "row": row,
                        "column": column,
                        "value": cell[2],
                    }
                )
    if len(candidates) == 1:
        return candidates[0]
    if role is None:
        return None

    # Some frozen graphs intentionally expose only selected semantic cells, while
    # handles preserve the original full-table row number. In that case bind by a
    # controlled role/domain label and the explicit column year, never by value.
    role_tokens = set(re.findall(r"[a-z]+|\d{4}", role.casefold()))
    year_tokens = {token for token in role_tokens if re.fullmatch(r"\d{4}", token)}
    semantic_tokens = role_tokens - year_tokens
    task_text = (task_id or "").casefold()
    if "energy" in task_text and "total" in semantic_tokens:
        semantic_tokens.add("energy")
    if "water" in task_text and "total" in semantic_tokens:
        semantic_tokens.update({"supplied", "water"})
    if "water" in task_text and "stress" in semantic_tokens:
        semantic_tokens.add("water")
    semantic_candidates = []
    for graph in table_graphs:
        if graph.get("pdf_page") != page:
            continue
        for cell in graph.get("selected_cells", []):
            if not isinstance(cell, list) or len(cell) != 3:
                continue
            row_tokens = set(re.findall(r"[a-z]+", str(cell[0]).casefold()))
            column_tokens = set(re.findall(r"[a-z]+|\d{4}", str(cell[1]).casefold()))
            if semantic_tokens <= row_tokens and year_tokens <= column_tokens:
                semantic_candidates.append(
                    {
                        "handle": handle,
                        "graph_id": graph.get("graph_id"),
                        "pdf_page": page,
                        "row": cell[0],
                        "column": cell[1],
                        "value": cell[2],
                        "binding_method": "controlled_role_column_label",
                    }
                )
    return semantic_candidates[0] if len(semantic_candidates) == 1 else None


def replay_calculation_plan_from_table_cells(
    task_id: str,
    plan: dict[str, Any],
    table_graphs: list[dict[str, Any]],
    expected_outputs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Replay a frozen plan only when every role has one explicit frozen table cell."""
    role_values: dict[str, float] = {}
    role_cells: dict[str, dict[str, Any]] = {}
    unresolved = []
    for handle, role in plan.get("candidate_handle_role_map", {}).items():
        cell = _cell_for_handle(handle, table_graphs, role=role, task_id=task_id)
        if cell is None or not isinstance(cell["value"], (int, float)):
            unresolved.append(role)
            continue
        if role in role_values and not _numeric_equal(role_values[role], cell["value"]):
            unresolved.append(role)
            continue
        role_values[role] = float(cell["value"])
        role_cells[role] = cell

    calculated = dict(role_values)
    executed_steps = []
    for step in plan.get("steps", []):
        inputs = step.get("inputs", [])
        if not all(item in calculated for item in inputs):
            unresolved.append(step.get("step_id", "unknown_step"))
            continue
        values = [calculated[item] for item in inputs]
        operation = step.get("operation")
        if operation == "sum":
            result = sum(values)
        elif operation == "difference" and len(values) == 2:
            result = values[0] - values[1]
        elif operation == "percentage_change" and len(values) == 2 and values[1] != 0:
            result = (values[0] - values[1]) / values[1] * 100
        elif operation == "percentage_share" and len(values) == 2 and values[1] != 0:
            result = values[0] / values[1] * 100
        else:
            unresolved.append(step.get("step_id", "unknown_step"))
            continue
        if isinstance(step.get("rounding_decimals"), int):
            result = round(result, step["rounding_decimals"])
        calculated[step["step_id"]] = result
        executed_steps.append(
            {
                "step_id": step["step_id"],
                "operation": operation,
                "inputs": inputs,
                "result": result,
            }
        )

    records = []
    for output in plan.get("output_slot_map", []):
        slot_id = output.get("slot_id")
        source_value_id = output.get("source_value_id")
        expected = expected_outputs.get(slot_id)
        actual = calculated.get(source_value_id)
        if actual is None:
            status = "unreplayable_missing_cell"
            reason = "the output dependency path lacks a unique frozen selected cell"
        elif not isinstance(expected, (int, float)):
            status = "unreplayable_missing_expected_output"
            reason = "the normalized reference does not contain a numeric output slot"
        elif _numeric_equal(actual, expected):
            status = "passed"
            reason = "frozen table cells and plan reproduce the normalized output"
        else:
            status = "mismatch"
            reason = "replayed result differs from the normalized reference output"
        records.append(
            {
                "schema_version": "0.1",
                "record_kind": "calculation_replay_audit",
                "task_id": task_id,
                "slot_id": slot_id,
                "source_value_id": source_value_id,
                "status": status,
                "expected": expected,
                "actual": actual,
                "resolved_role_cells": role_cells,
                "unresolved_roles_or_steps": sorted(set(unresolved)),
                "executed_steps": executed_steps,
                "reason": reason,
            }
        )
    return records


def audit_native_page_corroboration(
    fact: dict[str, Any],
    qualification: dict[str, Any],
    native_page_text: str | None,
    pdf_path: str | None,
    pdf_page: int | None = None,
) -> dict[str, Any]:
    """Corroborate a qualified scalar against PDF-native text, independent of MinerU."""
    matches = qualification.get("table_cell_binding", {}).get("matches", [])
    if native_page_text is None:
        status = "unavailable_pdf_or_page"
        literal_found = False
        labels_found = False
        reason = "native PDF page text was unavailable"
    else:
        value = fact.get("value")
        variants = scalar_literal_variants(value)
        literal_found = any(
            _literal_in_quote(
                variant,
                native_page_text,
                numeric=isinstance(value, (int, float)) and not isinstance(value, bool),
            )
            for variant in variants
        )
        labels_found = all(
            normalized_text(str(item.get("row", ""))) in normalized_text(native_page_text)
            and normalized_text(str(item.get("column", ""))) in normalized_text(native_page_text)
            for item in matches
        )
        if not literal_found:
            status = "failed_literal"
            reason = "normalized scalar was not found in PDF-native page text"
        elif matches and labels_found:
            status = "passed_scalar_and_cell_labels"
            reason = "scalar plus frozen row and column labels occur in PDF-native page text"
        elif not matches:
            status = "passed_scalar_only"
            reason = "scalar occurs in PDF-native page text; no selected table cell applies"
        else:
            status = "failed_cell_labels"
            reason = "scalar occurs but frozen row or column label is absent from native page text"
    return {
        "schema_version": "0.1",
        "record_kind": "native_pdf_corroboration",
        "fact_record_id": fact["record_id"],
        "task_id": fact["subject"]["task_id"],
        "pdf_path": pdf_path,
        "pdf_page": matches[0]["pdf_page"] if matches else pdf_page,
        "status": status,
        "literal_found": literal_found,
        "cell_labels_required": bool(matches),
        "cell_labels_found": labels_found,
        "promotion_eligible": False,
        "reason": reason,
    }
