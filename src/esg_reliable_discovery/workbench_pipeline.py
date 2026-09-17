from __future__ import annotations

import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Any

from .knowledge_base import stable_id
from .promotion_gate import evaluate_promotion_dry_run
from .table_projection import build_two_axis_table_graph
from .workbench_promotion_review import build_promotion_review_queue
from .workbench_repair import plan_workbench_repairs
from .workbench_repair_dispatch import prepare_workbench_repair_dispatches
from .workbench_table_repair import execute_unique_table_bindings

THEMES: dict[str, tuple[str, ...]] = {
    "ghg_emissions": ("greenhouse gas", "ghg", "scope 1", "scope 2", "scope 3", "co2e"),
    "energy": ("energy consumption", "renewable energy", "electricity", "fuel consumption"),
    "water": ("water consumption", "water withdrawal", "water discharge", "water stress"),
    "workforce": ("employees", "workforce", "full-time equivalent", "fte", "headcount"),
    "health_safety": ("fatalit", "injur", "lost time", "ltifr", "safety"),
    "circularity": ("waste", "recycl", "circular", "material consumption"),
    "targets": ("target", "net zero", "science based target", "sbti"),
    "assurance": ("limited assurance", "reasonable assurance", "isae 3000", "assurance report"),
    "biodiversity": ("biodiversity", "ecosystem", "protected area"),
    "taxonomy": ("eu taxonomy", "taxonomy-aligned", "taxonomy eligible"),
}

YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,.]*(?:\s?%)?")
TAG_PATTERN = re.compile(r"<[^>]+>")

UNIT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("percent", re.compile(r"%|\bpercent(?:age)?\b", re.IGNORECASE)),
    ("tCO2e", re.compile(r"\b(?:t|tonnes?\s+of\s+)co2e\b", re.IGNORECASE)),
    ("m3", re.compile(r"\bm3\b|\bcubic\s+met(?:er|re)s\b", re.IGNORECASE)),
    ("MWh", re.compile(r"\bmwh\b", re.IGNORECASE)),
    ("GWh", re.compile(r"\bgwh\b", re.IGNORECASE)),
    ("TWh", re.compile(r"\btwh\b", re.IGNORECASE)),
    ("FTE", re.compile(r"\bfte\b|full[- ]time equivalent", re.IGNORECASE)),
    ("people", re.compile(r"\b(?:employees?|people|headcount)\b", re.IGNORECASE)),
    ("hours", re.compile(r"\bhours?\b", re.IGNORECASE)),
)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _atomic_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    body = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)


def _block_text(block: dict[str, Any]) -> str:
    if block.get("type") == "table":
        raw = str(block.get("table_body", ""))
        return " ".join(html.unescape(TAG_PATTERN.sub(" ", raw)).split())
    return " ".join(str(block.get("text") or block.get("content") or "").split())


def _themes(text: str) -> list[str]:
    lowered = text.casefold()
    return [theme for theme, terms in THEMES.items() if any(term in lowered for term in terms)]


def _record_id(prefix: str, payload: str) -> str:
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def _normalized_number(literal: str) -> int | float:
    value = float(literal.replace(",", "").replace("%", "").replace(" ", ""))
    return int(value) if value.is_integer() else value


def _is_period_literal(literal: str, periods: list[str]) -> bool:
    return (
        literal.strip() in periods
        and re.fullmatch(r"(?:19|20)\d{2}", literal.strip()) is not None
    )


def _bound_unit(literal: str, quote: str) -> tuple[str | None, list[str]]:
    if "%" in literal:
        return "percent", ["percent"]
    matches = [unit for unit, pattern in UNIT_RULES if pattern.search(quote)]
    unique = list(dict.fromkeys(matches))
    return (unique[0] if len(unique) == 1 else None), unique


def _project_atomic_facts(
    candidates: list[dict[str, Any]],
    *,
    source_sha256: str,
    source_path: Path | None,
    workspace_root: Path | None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    facts: list[dict[str, Any]] = []
    validated: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    source_id = f"WB-SOURCE-{source_sha256[:16]}"
    source_artifact = str(source_path) if source_path else "workbench_job/source.pdf"
    root = workspace_root or Path.cwd()

    for candidate in candidates:
        quote = candidate["evidence"]["quote"]
        periods = list(dict.fromkeys(candidate.get("period_literals", [])))
        themes = candidate.get("theme_candidates", [])
        for ordinal, literal in enumerate(candidate.get("raw_value_literals", []), start=1):
            if _is_period_literal(literal, periods):
                continue
            blockers: list[str] = []
            if quote.count(literal) < 1:
                blockers.append("VERBATIM_LITERAL_NOT_GROUNDED")
            if len(themes) != 1:
                blockers.append("PREDICATE_AMBIGUOUS")
            if len(periods) != 1:
                blockers.append("PERIOD_BINDING_AMBIGUOUS" if periods else "PERIOD_BINDING_MISSING")
            unit, unit_matches = _bound_unit(literal, quote)
            if unit is None:
                blockers.append(
                    "UNIT_BINDING_AMBIGUOUS" if unit_matches else "UNIT_BINDING_MISSING"
                )
            if not isinstance(candidate["evidence"].get("pdf_page"), int):
                blockers.append("PAGE_LOCATOR_MISSING")
            if candidate["evidence"].get("bbox") is None:
                blockers.append("SPATIAL_LOCATOR_MISSING")

            identity = {
                "source_sha256": source_sha256,
                "candidate_id": candidate["record_id"],
                "literal": literal,
                "ordinal": ordinal,
            }
            fact = {
                "schema_version": "0.1",
                "record_kind": "fact",
                "record_id": stable_id("fact", identity),
                "knowledge_status": "reference_candidate" if not blockers else "quarantined",
                "trust_tier": "C",
                "subject": {
                    "task_id": candidate["record_id"],
                    "entity_label": None,
                    "document_ids": [source_id],
                    "document_metadata": ([{
                        "document_id": source_id,
                        "local_path": source_artifact,
                        "sha256": source_sha256,
                    }] if source_path else []),
                },
                "predicate": {
                    "raw_key": themes[0] if len(themes) == 1 else "ambiguous_esg_metric",
                    "canonical_key": themes[0] if len(themes) == 1 else "ambiguous_esg_metric",
                },
                "value": _normalized_number(literal),
                "qualifiers": {
                    "period_literal": periods[0] if len(periods) == 1 else None,
                    "reference_period": int(periods[0]) if len(periods) == 1 else None,
                    "normalized_unit": unit,
                    "scope_boundary": None,
                    "calculation_expression": None,
                    "answer_status": "projection_validated" if not blockers else "quarantined",
                    "value_origin": "mineru_verbatim_literal",
                },
                "evidence": [{
                    "source_id": source_id,
                    "pdf_page": candidate["evidence"]["pdf_page"],
                    "quote": quote,
                    "coordinates": candidate["evidence"].get("bbox"),
                    "block_type": candidate["evidence"].get("block_type"),
                    "source_artifact": candidate["evidence"].get("source_artifact"),
                    "verbatim_value": literal,
                }],
                "provenance": {
                    "source_artifact": source_artifact,
                    "source_sha256": source_sha256,
                    "reference_status": "workbench_local_deterministic_projection",
                    "simulated": False,
                },
                "promotion": {
                    "eligible": False,
                    "reason": "requires_independent_corroboration_and_scope_adjudication",
                },
            }
            audits.append({
                "schema_version": "1.0",
                "record_kind": "workbench_slot_projection_audit",
                "audit_id": stable_id("projection-audit", identity),
                "fact_record_id": fact["record_id"],
                "status": "passed" if not blockers else "blocked",
                "blocking_reasons": blockers,
                "bindings": {
                    "predicate": fact["predicate"]["canonical_key"],
                    "period": fact["qualifiers"]["reference_period"],
                    "unit": fact["qualifiers"]["normalized_unit"],
                    "pdf_page": fact["evidence"][0]["pdf_page"],
                    "coordinates": fact["evidence"][0]["coordinates"],
                },
                "raw_literal_preserved": True,
                "model_used": False,
            })
            facts.append(fact)
            if blockers:
                failures.append({
                    "record_id": _record_id("wb-failure", fact["record_id"] + "projection"),
                    "record_kind": "workbench_failure_observation",
                    "failure_signature": "SLOT_PROJECTION_INCOMPLETE",
                    "failure_category": "semantic_projection",
                    "diagnostic_status": "quarantined_before_trust_promotion",
                    "parent_fact_record_id": fact["record_id"],
                    "blocking_reasons": blockers,
                    "evidence": fact["evidence"][0],
                })
            else:
                validated.append(fact)
            gates.append(evaluate_promotion_dry_run(fact, blockers, root))
    return facts, validated, failures, gates, audits


def analyze_mineru_output(
    parsed_directory: str | Path,
    output_directory: str | Path,
    *,
    source_sha256: str,
    source_path: str | Path | None = None,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    """Create auditable job-local candidates; never promote them into the trusted KB."""
    parsed = Path(parsed_directory)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    content_files = sorted(
        path
        for path in parsed.rglob("*_content_list.json")
        if not path.name.endswith("_content_list_v2.json")
    )
    candidates: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    seen: set[str] = set()

    for content_path in content_files:
        blocks = json.loads(content_path.read_text(encoding="utf-8"))
        if not isinstance(blocks, list):
            continue
        for block_index, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type", "unknown"))
            text = _block_text(block)
            page = int(block.get("page_idx", 0)) + 1
            bbox = block.get("bbox")
            themes = _themes(text)
            numbers = NUMBER_PATTERN.findall(text)
            fingerprint = json.dumps(
                [page, block_type, bbox, text], ensure_ascii=False, separators=(",", ":")
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            if block_type == "chart" and not text:
                failures.append(
                    {
                        "record_id": _record_id("wb-failure", source_sha256 + fingerprint),
                        "record_kind": "workbench_failure_observation",
                        "failure_signature": "CHART_CONTENT_UNRECOVERED",
                        "failure_category": "parsing_structure",
                        "diagnostic_status": "requires_visual_or_chart_fallback",
                        "evidence": {"pdf_page": page, "bbox": bbox, "block_type": block_type},
                    }
                )
                continue
            if not themes or not numbers or block_type not in {
                "text",
                "aside_text",
                "table",
                "page_footnote",
            }:
                continue
            candidates.append(
                {
                    "record_id": _record_id("wb-candidate", source_sha256 + fingerprint),
                    "record_kind": "workbench_fact_candidate",
                    "knowledge_status": "candidate_not_trusted",
                    "trust_tier": "C",
                    "theme_candidates": themes,
                    "raw_value_literals": numbers[:30],
                    "period_literals": YEAR_PATTERN.findall(text),
                    "table_graphs": (
                        build_two_axis_table_graph(str(block.get("table_body", "")))
                        if block_type == "table"
                        else []
                    ),
                    "evidence": {
                        "pdf_page": page,
                        "bbox": bbox,
                        "block_type": block_type,
                        "block_index": block_index,
                        "quote": text[:2000],
                        "source_artifact": content_path.relative_to(parsed).as_posix(),
                    },
                    "promotion": {
                        "eligible": False,
                        "reason": "requires_slot_projection_and_independent_evidence_validation",
                    },
                }
            )

    if not candidates:
        failures.append(
            {
                "record_id": _record_id("wb-failure", source_sha256 + "no-candidates"),
                "record_kind": "workbench_failure_observation",
                "failure_signature": "PARSED_WITHOUT_ESG_NUMERIC_EVIDENCE",
                "failure_category": "retrieval_or_evidence_selection",
                "diagnostic_status": "requires_page_window_or_lexicon_review",
                "evidence": None,
            }
        )

    (
        atomic_facts,
        validated_facts,
        projection_failures,
        promotion_gates,
        projection_audits,
    ) = _project_atomic_facts(
        candidates,
        source_sha256=source_sha256,
        source_path=Path(source_path).resolve() if source_path else None,
        workspace_root=Path(workspace_root).resolve() if workspace_root else None,
    )
    failures.extend(projection_failures)

    strategy_catalog_path = (
        Path(__file__).resolve().parents[2]
        / "configs/knowledge/repair_strategy_catalog_v0.1.json"
    )
    strategy_catalog = json.loads(strategy_catalog_path.read_text(encoding="utf-8"))
    repair_plans = plan_workbench_repairs(
        failures=failures,
        promotion_gates=promotion_gates,
        strategy_catalog=strategy_catalog,
    )
    resolved_source_path = Path(source_path).resolve() if source_path else None
    resolved_workspace_root = (
        Path(workspace_root).resolve() if workspace_root else Path.cwd()
    )
    repair_dispatches = prepare_workbench_repair_dispatches(
        plans=repair_plans,
        facts=atomic_facts,
        source_path=resolved_source_path,
        workspace_root=resolved_workspace_root,
    )
    repaired_facts, repair_executions = execute_unique_table_bindings(
        facts=atomic_facts,
        candidates=candidates,
        plans=repair_plans,
        dispatches=repair_dispatches,
    )
    promotion_reviews = build_promotion_review_queue(
        repaired_facts=repaired_facts,
        repair_executions=repair_executions,
    )

    _atomic_jsonl(output / "candidate_records.jsonl", candidates)
    _atomic_jsonl(output / "atomic_fact_candidates.jsonl", atomic_facts)
    _atomic_jsonl(output / "projection_validated_candidates.jsonl", validated_facts)
    _atomic_jsonl(output / "projection_audit_records.jsonl", projection_audits)
    _atomic_jsonl(output / "promotion_gate_records.jsonl", promotion_gates)
    _atomic_jsonl(output / "repair_plan_records.jsonl", repair_plans)
    _atomic_jsonl(output / "repair_dispatch_records.jsonl", repair_dispatches)
    _atomic_jsonl(output / "repaired_fact_candidates.jsonl", repaired_facts)
    _atomic_jsonl(output / "repair_execution_records.jsonl", repair_executions)
    _atomic_jsonl(output / "promotion_review_records.jsonl", promotion_reviews)
    _atomic_jsonl(output / "failure_records.jsonl", failures)
    summary = {
        "schema_version": "1.0",
        "record_kind": "workbench_local_analysis_summary",
        "source_sha256": source_sha256,
        "content_files": len(content_files),
        "candidate_records": len(candidates),
        "atomic_fact_candidates": len(atomic_facts),
        "projection_validated_candidates": len(validated_facts),
        "projection_quarantined": len(atomic_facts) - len(validated_facts),
        "projection_audit_records": len(projection_audits),
        "promotion_gate_records": len(promotion_gates),
        "repair_plan_records": len(repair_plans),
        "repair_dispatch_records": len(repair_dispatches),
        "repair_dispatch_ready": sum(
            dispatch["decision"].startswith("ready_for_")
            for dispatch in repair_dispatches
        ),
        "repaired_fact_candidates": len(repaired_facts),
        "repair_executions_postvalidated": sum(
            execution["state"] == "postvalidation_passed"
            for execution in repair_executions
        ),
        "repair_executions_rolled_back": sum(
            execution["state"] == "rolled_back" for execution in repair_executions
        ),
        "promotion_reviews_pending": len(promotion_reviews),
        "repair_plans_blocked": sum(
            plan["decision"] in {"blocked_fail_closed", "no_strategy"}
            for plan in repair_plans
        ),
        "repair_plans_supervised": sum(
            plan["decision"] == "supervised_candidate" for plan in repair_plans
        ),
        "failure_records": len(failures),
        "trusted_promotions": 0,
        "policy": {
            "job_local_staging_only": True,
            "automatic_trust_promotion": False,
            "cloud_model_used": False,
        },
    }
    _atomic_json(output / "analysis_summary.json", summary)
    return summary
