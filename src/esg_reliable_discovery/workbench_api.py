from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import threading
import uuid
from collections import Counter
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from .hashing import sha256_file
from .knowledge_query import query_facts
from .mineru_adapter import (
    MinerUError,
    audit_mineru_assets,
    parse_with_mineru,
    probe_mineru,
)
from .release_runtime import initialize_workspace
from .workbench_native_fallback import NativePDFFallbackError, parse_with_native_pdf_layout
from .workbench_pipeline import analyze_mineru_output
from .workbench_promotion_overlay import (
    active_overlay_records,
    commit_staged_overlay,
    withdraw_overlay,
)
from .workbench_promotion_review import decide_promotion_review
from .workbench_promotion_staging import stage_approved_promotion

MAX_UPLOAD_BYTES = 250 * 1024 * 1024


def _venv_executable(workspace: Path, name: str) -> Path:
    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return workspace / ".mineru-venv" / scripts / f"{name}{suffix}"


def _fact_company(fact: dict[str, Any]) -> str:
    subject = fact.get("subject", {})
    if subject.get("entity_label"):
        return str(subject["entity_label"])
    metadata = subject.get("document_metadata", [])
    if metadata and metadata[0].get("company"):
        return str(metadata[0]["company"])
    return "Unknown entity"


def _fact_category(predicate: str) -> str:
    value = predicate.casefold()
    rules = (
        ("Emissions", ("emission", "scope_1", "scope_2", "scope_3", "ghg", "co2")),
        ("Energy", ("energy", "electricity", "fuel", "renewable")),
        ("Water", ("water", "withdrawal", "discharge")),
        ("Waste & circularity", ("waste", "circular", "recycl", "landfill")),
        ("Workforce & safety", ("employee", "workforce", "fatal", "injury", "safety")),
        ("Targets & progress", ("target", "baseline", "progress", "sbti")),
        ("EU Taxonomy", ("taxonomy", "capex", "opex", "turnover", "aligned", "eligible")),
        ("Assurance", ("assurance", "auditor", "governing_standard")),
        ("Boundaries & methods", ("boundary", "exclusion", "method", "scope", "reference_page")),
    )
    for category, needles in rules:
        if any(needle in value for needle in needles):
            return category
    return "Other disclosures"


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace(",", "").replace("%", "")
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cleaned):
        return float(cleaned)
    return None


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid PNG preview")
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _atomic_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    os.replace(temporary, path)


class WorkbenchService:
    """Local-first bridge between the browser workbench and the audited core."""

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).resolve()
        initialize_workspace(self.workspace)
        self.knowledge_root = self.workspace / "data/knowledge_bases/v0.1"
        self.jobs_root = self.workspace / "data/workbench/jobs"
        self._review_lock = threading.Lock()
        self._overlay_lock = threading.Lock()
        bundled_mineru = _venv_executable(self.workspace, "mineru")
        self.mineru_executable = str(bundled_mineru) if bundled_mineru.exists() else "mineru"
        self.mineru_tools_config = self.workspace / "configs/parsers/mineru-tools-huggingface.json"
        self.mineru_asset_manifest = (
            self.workspace / "model_manifests/mineru-pdf-extract-kit-1.0-ed6b654c.lock.json"
        )
        self._mineru_asset_audit: dict[str, Any] | None = None
        self._mineru_asset_lock = threading.Lock()
        self._preview_jobs: set[str] = set()
        self._preview_lock = threading.Lock()
        self._reconcile_promotion_staging()

    def _ensure_mineru_asset_audit(self) -> dict[str, Any]:
        with self._mineru_asset_lock:
            if self._mineru_asset_audit is None:
                self._mineru_asset_audit = audit_mineru_assets(
                    self.mineru_tools_config,
                    self.mineru_asset_manifest,
                )
            return self._mineru_asset_audit

    def summary(self) -> dict[str, Any]:
        facts = _load_jsonl(self.knowledge_root / "fact_records.jsonl")
        trusted = _load_jsonl(self.knowledge_root / "trusted_fact_records.jsonl")
        failures = _load_jsonl(self.knowledge_root / "failure_records.jsonl")
        signatures = {
            item.get("failure_signature") for item in failures if item.get("failure_signature")
        }
        acceptance = self.workspace / "data/results/scale_120_report_acceptance_v0.1.lock.json"
        accepted: dict[str, Any] = {}
        if acceptance.exists():
            accepted = json.loads(acceptance.read_text(encoding="utf-8"))
        source_manifest_path = self.knowledge_root / "source_distribution_manifest.lock.json"
        source_manifest = (
            json.loads(source_manifest_path.read_text(encoding="utf-8"))
            if source_manifest_path.exists()
            else {}
        )
        accepted_coverage = accepted.get("coverage", {})
        unique_reports = accepted_coverage.get("total_unique_reports") or len(
            source_manifest.get("records", [])
        )
        return {
            "schema_version": "1.0",
            "record_kind": "workbench_summary",
            "generated_at": _now(),
            "inventory": {
                "unique_reports": unique_reports,
                "fact_records": len(facts) if facts else len(trusted),
                "trusted_tier_b": len(trusted),
                "failure_records": len(failures),
                "failure_signatures": len(signatures),
            },
            "acceptance": accepted,
            "engine": {"mineru": probe_mineru(self.mineru_executable)},
            "policy": {
                "locked_experiments_are_read_only": True,
                "cloud_transfer_requires_explicit_scope": True,
                "candidates_never_masquerade_as_trusted": True,
            },
        }

    def failures(self, *, limit: int = 100, signature: str | None = None) -> dict[str, Any]:
        records = _load_jsonl(self.knowledge_root / "failure_records.jsonl")
        counts = Counter(item.get("failure_signature", "UNCLASSIFIED") for item in records)
        if signature:
            records = [item for item in records if item.get("failure_signature") == signature]
        return {
            "schema_version": "1.0",
            "record_kind": "failure_query_response",
            "matched": len(records),
            "returned": min(limit, len(records)),
            "signature_counts": dict(counts.most_common()),
            "records": records[:limit],
        }

    def trusted_facts(self, *, limit: int = 500) -> dict[str, Any]:
        records = _load_jsonl(self.knowledge_root / "trusted_fact_records.jsonl")
        return {
            "schema_version": "1.0",
            "record_kind": "trusted_fact_browser_response",
            "matched": len(records),
            "returned": min(limit, len(records)),
            "records": [
                {"fact": fact, "effective_trust": "trusted_tier_b"} for fact in records[:limit]
            ],
            "policy": {
                "source": "promoted_trusted_fact_layer",
                "candidates_included": False,
            },
        }

    def entities(self, *, limit: int = 500) -> dict[str, Any]:
        records = _load_jsonl(self.knowledge_root / "entity_registry.jsonl")
        return {
            "schema_version": "0.1",
            "record_kind": "entity_query_response",
            "matched": len(records),
            "returned": min(limit, len(records)),
            "records": records[:limit],
            "policy": {"fuzzy_merge": False, "controlled_aliases_only": True},
        }

    def relations(
        self,
        *,
        limit: int = 500,
        entity_id: str | None = None,
        predicate: str | None = None,
    ) -> dict[str, Any]:
        records = _load_jsonl(self.knowledge_root / "relation_edges.jsonl")
        if entity_id:
            records = [row for row in records if row.get("subject_entity_id") == entity_id]
        if predicate:
            records = [row for row in records if row.get("predicate") == predicate]
        return {
            "schema_version": "0.1",
            "record_kind": "relation_query_response",
            "matched": len(records),
            "returned": min(limit, len(records)),
            "records": records[:limit],
            "policy": {"trusted_tier_b_only": True, "candidate_edges_included": False},
        }

    def analytics(self, *, company: str | None = None) -> dict[str, Any]:
        """Aggregate only promoted Tier-B records for user-facing analysis."""
        facts = _load_jsonl(self.knowledge_root / "trusted_fact_records.jsonl")
        if company:
            target = company.casefold()
            facts = [item for item in facts if target in _fact_company(item).casefold()]
        companies = Counter(_fact_company(item) for item in facts)
        predicates = Counter(
            str(item.get("predicate", {}).get("canonical_key", "unknown")) for item in facts
        )
        years = Counter(
            str(item.get("qualifiers", {}).get("reference_period"))
            for item in facts
            if item.get("qualifiers", {}).get("reference_period") is not None
        )
        units = Counter(
            str(item.get("qualifiers", {}).get("normalized_unit"))
            for item in facts
            if item.get("qualifiers", {}).get("normalized_unit")
        )
        categories = Counter(
            _fact_category(str(item.get("predicate", {}).get("canonical_key", "unknown")))
            for item in facts
        )
        profiles = []
        for name, count in companies.most_common():
            selected = [item for item in facts if _fact_company(item) == name]
            profiles.append(
                {
                    "company": name,
                    "fact_count": count,
                    "predicate_count": len(
                        {item.get("predicate", {}).get("canonical_key") for item in selected}
                    ),
                    "years": sorted(
                        {
                            item.get("qualifiers", {}).get("reference_period")
                            for item in selected
                            if item.get("qualifiers", {}).get("reference_period") is not None
                        }
                    ),
                    "category_counts": dict(
                        Counter(
                            _fact_category(
                                str(item.get("predicate", {}).get("canonical_key", "unknown"))
                            )
                            for item in selected
                        )
                    ),
                    "evidence_items": sum(len(item.get("evidence", [])) for item in selected),
                }
            )
        series: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for fact in facts:
            qualifiers = fact.get("qualifiers", {})
            year = qualifiers.get("reference_period")
            number = _numeric_value(fact.get("value"))
            if year is None or number is None:
                continue
            predicate = str(fact.get("predicate", {}).get("canonical_key", "unknown"))
            unit = str(qualifiers.get("normalized_unit") or "unspecified")
            series.setdefault((predicate, unit), []).append(
                {
                    "company": _fact_company(fact),
                    "year": year,
                    "value": number,
                    "record_id": fact.get("record_id"),
                    "pdf_page": (fact.get("evidence") or [{}])[0].get("pdf_page"),
                }
            )
        return {
            "schema_version": "1.0",
            "record_kind": "trusted_knowledge_analytics",
            "filters": {"company": company},
            "inventory": {"fact_count": len(facts), "company_count": len(companies)},
            "facets": {
                "companies": dict(companies.most_common()),
                "predicates": dict(predicates.most_common()),
                "years": dict(sorted(years.items())),
                "units": dict(units.most_common()),
                "categories": dict(categories.most_common()),
            },
            "company_profiles": profiles,
            "series": [
                {"predicate": key[0], "unit": key[1], "points": points}
                for key, points in sorted(series.items())
                if len(points) >= 2
            ],
            "policy": {
                "trusted_tier_b_only": True,
                "issuer_disclosure_not_external_truth": True,
                "missing_values_not_imputed": True,
            },
        }

    def knowledge_schema(self) -> dict[str, Any]:
        facts = _load_jsonl(self.knowledge_root / "trusted_fact_records.jsonl")
        grouped: dict[str, Counter[str]] = {}
        for fact in facts:
            predicate = str(fact.get("predicate", {}).get("canonical_key", "unknown"))
            grouped.setdefault(_fact_category(predicate), Counter())[predicate] += 1
        return {
            "schema_version": "1.0",
            "record_kind": "knowledge_schema_browser",
            "categories": [
                {
                    "category": category,
                    "fact_count": sum(predicates.values()),
                    "predicate_count": len(predicates),
                    "predicates": dict(predicates.most_common()),
                }
                for category, predicates in sorted(grouped.items())
            ],
        }

    def repair_lifecycle(self) -> dict[str, Any]:
        failures = _load_jsonl(self.knowledge_root / "failure_records.jsonl")
        plans = _load_jsonl(self.knowledge_root / "repair_controller_dry_run.jsonl")
        states = _load_jsonl(self.knowledge_root / "repair_execution_states.jsonl")
        events = _load_jsonl(self.knowledge_root / "repair_execution_events.jsonl")
        observations = _load_jsonl(self.knowledge_root / "repair_observations.jsonl")
        return {
            "schema_version": "1.0",
            "record_kind": "repair_lifecycle_summary",
            "counts": {
                "failures": len(failures),
                "plans": len(plans),
                "executions": len(states),
                "events": len(events),
                "observations": len(observations),
            },
            "states": dict(
                Counter(str(item.get("state", "unknown")) for item in states).most_common()
            ),
            "strategies": dict(
                Counter(
                    str(item.get("strategy_id", item.get("selected_strategy_id", "unassigned")))
                    for item in plans
                ).most_common()
            ),
            "recent_events": sorted(
                events,
                key=lambda item: str(item.get("occurred_at", item.get("at", ""))),
                reverse=True,
            )[:50],
            "policy": {
                "silent_retry": False,
                "postvalidation_required": True,
                "rollback_preserved": True,
            },
        }

    def _fact_record(self, record_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"fact-[a-zA-Z0-9_-]+", record_id):
            raise FileNotFoundError(record_id)
        for filename in ("trusted_fact_records.jsonl", "fact_records.jsonl"):
            for fact in _load_jsonl(self.knowledge_root / filename):
                if fact.get("record_id") == record_id:
                    return fact
        raise FileNotFoundError(record_id)

    def _registered_pdf(self, fact: dict[str, Any], evidence: dict[str, Any]) -> Path:
        raw = (
            evidence.get("local_artifact")
            or fact.get("provenance", {}).get("source_artifact")
            or ((fact.get("subject", {}).get("document_metadata") or [{}])[0]).get("local_path")
        )
        if not raw:
            raise FileNotFoundError("registered PDF path is unavailable")
        path = Path(str(raw))
        if not path.is_absolute():
            path = self.workspace / path
        path = path.resolve()
        try:
            path.relative_to(self.workspace)
        except ValueError as exc:
            raise FileNotFoundError("registered PDF is outside the workspace") from exc
        if path.suffix.casefold() != ".pdf" or not path.is_file():
            raise FileNotFoundError("registered PDF is unavailable")
        return path

    def evidence_preview(self, record_id: str, evidence_index: int) -> dict[str, Any]:
        fact = self._fact_record(record_id)
        evidence_items = fact.get("evidence", [])
        if evidence_index < 0 or evidence_index >= len(evidence_items):
            raise FileNotFoundError("evidence index is unavailable")
        evidence = evidence_items[evidence_index]
        source = self._registered_pdf(fact, evidence)
        page = int(evidence.get("pdf_page", 1))
        source_sha256 = sha256_file(source)
        cache = (
            self.workspace
            / "data/workbench/previews"
            / source_sha256
            / f"{record_id}-{evidence_index}.json"
        )
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        payload = {
            "record_id": record_id,
            "evidence_index": evidence_index,
            "pdf_page": page,
            "quote": evidence.get("quote"),
            "coordinates": None,
            "coordinate_space": None,
            "highlight_precision": "resolving",
            "source_sha256": source_sha256,
            "image_url": (f"/facts/{record_id}/evidence/{evidence_index}/page.png"),
        }
        job_key = f"{record_id}:{evidence_index}"
        with self._preview_lock:
            if job_key not in self._preview_jobs:
                self._preview_jobs.add(job_key)
                threading.Thread(
                    target=self._resolve_evidence_preview,
                    args=(job_key, cache, payload, source, evidence),
                    daemon=True,
                ).start()
        return payload

    def _resolve_evidence_preview(
        self,
        job_key: str,
        cache: Path,
        payload: dict[str, Any],
        source: Path,
        evidence: dict[str, Any],
    ) -> None:
        resolved = dict(payload)
        try:
            coordinates = evidence.get("coordinates") or evidence.get("bbox")
            precision = "parser_coordinates" if coordinates else "page_only"
            coordinate_height: float | None = None
            if not coordinates:
                coordinates, precision, coordinate_height = self._text_match_bbox(
                    source, int(payload["pdf_page"]), evidence
                )
            if coordinates and coordinate_height is None:
                image = self.evidence_page_png(
                    str(payload["record_id"]), int(payload["evidence_index"])
                )
                _, coordinate_height = _png_dimensions(image)
            resolved.update(
                coordinates=coordinates,
                coordinate_space=(
                    {"width": 1000, "height": coordinate_height}
                    if coordinates and coordinate_height
                    else None
                ),
                highlight_precision=precision,
            )
            _atomic_json(cache, resolved)
        finally:
            with self._preview_lock:
                self._preview_jobs.discard(job_key)

    def _text_match_bbox(
        self, source: Path, page: int, evidence: dict[str, Any]
    ) -> tuple[list[float] | None, str, float | None]:
        """Recover a highlight from the source text without inventing coordinates."""
        row_header = str(evidence.get("row_header") or "").strip()
        quote = str(evidence.get("quote") or "").strip()
        target = row_header or quote
        if not target:
            return None, "page_only", None
        try:
            result = subprocess.run(
                ["pdftotext", "-f", str(page), "-l", str(page), "-bbox", str(source), "-"],
                check=True,
                capture_output=True,
                timeout=30,
            )
            root = ElementTree.fromstring(result.stdout)
        except (
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            ElementTree.ParseError,
        ):
            return None, "page_only", None
        page_node = next(
            (node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "page"),
            None,
        )
        if page_node is None:
            return None, "page_only", None
        words = [node for node in page_node.iter() if node.tag.rsplit("}", 1)[-1] == "word"]

        def normalize(text: str) -> str:
            return re.sub(r"[^a-z0-9%]+", "", text.casefold())

        target_tokens = [normalize(token) for token in target.split() if normalize(token)][:12]
        word_tokens = [normalize(node.text or "") for node in words]
        matched: list[Any] = []
        if target_tokens:
            for index in range(len(words) - len(target_tokens) + 1):
                if word_tokens[index : index + len(target_tokens)] == target_tokens:
                    matched = words[index : index + len(target_tokens)]
                    break
        if not matched and quote:
            quote_token = normalize(quote)
            matched = [
                node for node, token in zip(words, word_tokens, strict=True) if token == quote_token
            ]
        if not matched:
            return None, "page_only", None
        page_width = float(page_node.attrib["width"])
        page_height = float(page_node.attrib["height"])
        scale = 1000 / page_width
        x_min = min(float(node.attrib["xMin"]) for node in matched) * scale
        y_min = min(float(node.attrib["yMin"]) for node in matched) * scale
        x_max = max(float(node.attrib["xMax"]) for node in matched) * scale
        y_max = max(float(node.attrib["yMax"]) for node in matched) * scale
        if row_header:
            x_min, x_max = 24.0, 976.0
        padding = 5.0
        return (
            [
                max(0.0, x_min - padding),
                max(0.0, y_min - padding),
                min(1000.0, x_max + padding),
                min(page_height * scale, y_max + padding),
            ],
            "row_text_match" if row_header else "quote_text_match",
            page_height * scale,
        )

    def evidence_page_png(self, record_id: str, evidence_index: int) -> Path:
        fact = self._fact_record(record_id)
        evidence_items = fact.get("evidence", [])
        if evidence_index < 0 or evidence_index >= len(evidence_items):
            raise FileNotFoundError("evidence index is unavailable")
        evidence = evidence_items[evidence_index]
        source = self._registered_pdf(fact, evidence)
        page = int(evidence.get("pdf_page", 1))
        if page < 1:
            raise ValueError("PDF page must be one-based")
        cache = (
            self.workspace
            / "data/workbench/previews"
            / sha256_file(source)
            / f"page-{page:05d}.png"
        )
        if cache.exists():
            return cache
        cache.parent.mkdir(parents=True, exist_ok=True)
        output_stem = cache.with_suffix("")
        try:
            subprocess.run(
                [
                    "pdftocairo",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-png",
                    "-singlefile",
                    "-scale-to-x",
                    "1000",
                    "-scale-to-y",
                    "-1",
                    str(source),
                    str(output_stem),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError("PDF page rendering failed") from exc
        if not cache.exists():
            raise ValueError("PDF page renderer produced no image")
        return cache

    def create_job(
        self,
        stream: BinaryIO,
        *,
        content_length: int,
        filename: str,
    ) -> dict[str, Any]:
        if content_length < 5 or content_length > MAX_UPLOAD_BYTES:
            raise ValueError("PDF size must be between 5 bytes and 250 MB")
        job_id = f"WB-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        job_root = self.jobs_root / job_id
        job_root.mkdir(parents=True, exist_ok=False)
        source = job_root / "source.pdf"
        remaining = content_length
        with source.open("xb") as destination:
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                destination.write(chunk)
                remaining -= len(chunk)
        if remaining or source.read_bytes()[:5] != b"%PDF-":
            source.unlink(missing_ok=True)
            raise ValueError("Upload is incomplete or is not a PDF")
        manifest = {
            "schema_version": "1.0",
            "record_kind": "workbench_analysis_job",
            "job_id": job_id,
            "state": "source_frozen",
            "stage_index": 1,
            "stage_count": 5,
            "created_at": _now(),
            "updated_at": _now(),
            "source": {
                "original_filename": Path(filename).name or "report.pdf",
                "local_path": source.relative_to(self.workspace).as_posix(),
                "bytes": source.stat().st_size,
                "sha256": sha256_file(source),
            },
            "policy": {"cloud_transfer_authorized": False, "locked_results_mutable": False},
            "events": [{"at": _now(), "event": "source_frozen"}],
        }
        _atomic_json(job_root / "job.json", manifest)
        return manifest

    def get_job(self, job_id: str) -> dict[str, Any]:
        if not job_id.startswith("WB-") or "/" in job_id or ".." in job_id:
            raise FileNotFoundError(job_id)
        path = self.jobs_root / job_id / "job.json"
        if not path.exists():
            raise FileNotFoundError(job_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def list_jobs(self, *, limit: int = 100) -> dict[str, Any]:
        jobs = []
        for path in sorted(self.jobs_root.glob("WB-*/job.json"), reverse=True):
            try:
                jobs.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return {
            "schema_version": "1.0",
            "record_kind": "workbench_job_list",
            "matched": len(jobs),
            "records": jobs[:limit],
        }

    def job_fact_details(self, job_id: str, *, limit: int = 100) -> dict[str, Any]:
        job = self.get_job(job_id)
        analysis_root = self.jobs_root / job_id / "analysis"
        facts = _load_jsonl(analysis_root / "atomic_fact_candidates.jsonl")
        audits = {
            item.get("fact_record_id"): item
            for item in _load_jsonl(analysis_root / "projection_audit_records.jsonl")
        }
        gates = {
            item.get("fact_record_id"): item
            for item in _load_jsonl(analysis_root / "promotion_gate_records.jsonl")
        }
        repair_plans = {
            item.get("fact_record_id"): item
            for item in _load_jsonl(analysis_root / "repair_plan_records.jsonl")
        }
        repair_dispatches = {
            item.get("fact_record_id"): item
            for item in _load_jsonl(analysis_root / "repair_dispatch_records.jsonl")
        }
        repaired_facts = {
            item.get("record_id"): item
            for item in _load_jsonl(analysis_root / "repaired_fact_candidates.jsonl")
        }
        repair_executions: dict[str, list[dict[str, Any]]] = {}
        promotion_reviews = {
            item.get("fact_record_id"): item
            for item in _load_jsonl(analysis_root / "promotion_review_records.jsonl")
        }
        promotion_staging = {
            item.get("fact_record_id"): item
            for item in _load_jsonl(analysis_root / "promotion_staging_records.jsonl")
        }
        active_overlays = {
            item.get("provenance", {}).get("promotion_staging_id"): item
            for item in active_overlay_records(
                _load_jsonl(self.knowledge_root / "workbench_tier_b_overlay_events.jsonl")
            )
        }
        for item in _load_jsonl(analysis_root / "repair_execution_records.jsonl"):
            parent_id = item.get("parent_fact_record_id")
            if parent_id:
                repair_executions.setdefault(parent_id, []).append(
                    {
                        **item,
                        "derived_fact": repaired_facts.get(item.get("derived_fact_record_id")),
                        "promotion_review": promotion_reviews.get(
                            item.get("derived_fact_record_id")
                        ),
                        "promotion_staging": promotion_staging.get(
                            item.get("derived_fact_record_id")
                        ),
                        "promotion_overlay": active_overlays.get(
                            (promotion_staging.get(item.get("derived_fact_record_id")) or {}).get(
                                "staging_id"
                            )
                        ),
                    }
                )
        failures: dict[str, list[dict[str, Any]]] = {}
        for item in _load_jsonl(analysis_root / "failure_records.jsonl"):
            parent_id = item.get("parent_fact_record_id")
            if parent_id:
                failures.setdefault(parent_id, []).append(item)
        records = [
            {
                "fact": fact,
                "projection_audit": audits.get(fact["record_id"]),
                "promotion_gate": gates.get(fact["record_id"]),
                "repair_plan": repair_plans.get(fact["record_id"]),
                "repair_dispatch": repair_dispatches.get(fact["record_id"]),
                "repair_executions": repair_executions.get(fact["record_id"], []),
                "failures": failures.get(fact["record_id"], []),
            }
            for fact in facts[:limit]
        ]
        return {
            "schema_version": "1.0",
            "record_kind": "workbench_job_fact_details",
            "job_id": job_id,
            "source": job["source"],
            "analysis": job.get("analysis", {}),
            "matched": len(facts),
            "returned": len(records),
            "records": records,
            "policy": {
                "read_only": True,
                "trusted_layer_modified": False,
                "cloud_model_used": False,
            },
        }

    def promotion_reviews(self, job_id: str) -> dict[str, Any]:
        self.get_job(job_id)
        records = _load_jsonl(self.jobs_root / job_id / "analysis/promotion_review_records.jsonl")
        return {
            "schema_version": "1.0",
            "record_kind": "workbench_promotion_review_list",
            "job_id": job_id,
            "matched": len(records),
            "records": records,
            "policy": {
                "approval_is_staging_only": True,
                "automatic_trust_promotion": False,
                "trusted_layer_modified": False,
            },
        }

    def _ensure_promotion_staging_unlocked(self, job_id: str) -> list[dict[str, Any]]:
        analysis_root = self.jobs_root / job_id / "analysis"
        reviews = _load_jsonl(analysis_root / "promotion_review_records.jsonl")
        facts = {
            item["record_id"]: item
            for item in _load_jsonl(analysis_root / "repaired_fact_candidates.jsonl")
        }
        trusted = _load_jsonl(self.knowledge_root / "trusted_fact_records.jsonl")
        existing = {
            (item.get("review_id"), item.get("review_version")): item
            for item in _load_jsonl(analysis_root / "promotion_staging_records.jsonl")
        }
        records = []
        for review in reviews:
            if review.get("state") != "approved_for_promotion_staging":
                continue
            key = (review.get("review_id"), review.get("version"))
            if key in existing:
                records.append(existing[key])
                continue
            fact = facts.get(review.get("fact_record_id"))
            if fact is None:
                continue
            records.append(
                stage_approved_promotion(
                    review=review,
                    fact=fact,
                    trusted_facts=trusted,
                    workspace_root=self.workspace,
                )
            )
        _atomic_jsonl(analysis_root / "promotion_staging_records.jsonl", records)
        return records

    def _reconcile_promotion_staging(self) -> None:
        for review_path in self.jobs_root.glob("WB-*/analysis/promotion_review_records.jsonl"):
            job_id = review_path.parents[1].name
            try:
                self._ensure_promotion_staging_unlocked(job_id)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue

    def promotion_staging(self, job_id: str) -> dict[str, Any]:
        self.get_job(job_id)
        records = _load_jsonl(self.jobs_root / job_id / "analysis/promotion_staging_records.jsonl")
        return {
            "schema_version": "1.0",
            "record_kind": "workbench_promotion_staging_list",
            "job_id": job_id,
            "matched": len(records),
            "records": records,
            "policy": {
                "job_local_staging_only": True,
                "automatic_trust_promotion": False,
                "trusted_layer_modified": False,
            },
        }

    def promotion_overlays(self) -> dict[str, Any]:
        events = _load_jsonl(self.knowledge_root / "workbench_tier_b_overlay_events.jsonl")
        active = active_overlay_records(events)
        return {
            "schema_version": "1.0",
            "record_kind": "workbench_tier_b_overlay_list",
            "active_count": len(active),
            "event_count": len(events),
            "records": active,
            "events": events,
            "policy": {
                "append_only_event_history": True,
                "base_trusted_layer_modified": False,
                "withdrawal_is_reversible_overlay_deactivation": True,
            },
        }

    def commit_promotion_staging(
        self, job_id: str, staging_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.get_job(job_id)
        staging_path = self.jobs_root / job_id / "analysis/promotion_staging_records.jsonl"
        with self._overlay_lock:
            staging = next(
                (
                    item
                    for item in _load_jsonl(staging_path)
                    if item.get("staging_id") == staging_id
                ),
                None,
            )
            if staging is None:
                raise FileNotFoundError(staging_id)
            events_path = self.knowledge_root / "workbench_tier_b_overlay_events.jsonl"
            events = _load_jsonl(events_path)
            event = commit_staged_overlay(
                staging=staging,
                existing_events=events,
                actor=str(payload.get("actor", "")),
                rationale=str(payload.get("rationale", "")),
                occurred_at=_now(),
            )
            events.append(event)
            active = active_overlay_records(events)
            _atomic_jsonl(events_path, events)
            _atomic_jsonl(self.knowledge_root / "workbench_tier_b_active_overlays.jsonl", active)
        return {"event": event, "active_overlays": active}

    def withdraw_promotion_overlay(
        self, overlay_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self._overlay_lock:
            events_path = self.knowledge_root / "workbench_tier_b_overlay_events.jsonl"
            events = _load_jsonl(events_path)
            event = withdraw_overlay(
                overlay_id=overlay_id,
                existing_events=events,
                actor=str(payload.get("actor", "")),
                rationale=str(payload.get("rationale", "")),
                occurred_at=_now(),
            )
            events.append(event)
            active = active_overlay_records(events)
            _atomic_jsonl(events_path, events)
            _atomic_jsonl(self.knowledge_root / "workbench_tier_b_active_overlays.jsonl", active)
        return {"event": event, "active_overlays": active}

    def decide_promotion_review(
        self,
        job_id: str,
        review_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.get_job(job_id)
        path = self.jobs_root / job_id / "analysis/promotion_review_records.jsonl"
        with self._review_lock:
            records = _load_jsonl(path)
            index = next(
                (
                    position
                    for position, item in enumerate(records)
                    if item.get("review_id") == review_id
                ),
                None,
            )
            if index is None:
                raise FileNotFoundError(review_id)
            updated = decide_promotion_review(
                records[index],
                decision=str(payload.get("decision", "")),
                reviewer=str(payload.get("reviewer", "")),
                rationale=str(payload.get("rationale", "")),
                expected_version=int(payload.get("expected_version", 0)),
            )
            records[index] = updated
            _atomic_jsonl(path, records)
            self._ensure_promotion_staging_unlocked(job_id)
        return updated

    def start_parse(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job["state"] not in {"source_frozen", "parse_failed"}:
            return job
        probe = probe_mineru(self.mineru_executable)
        if not probe["available"] and job["state"] != "parse_failed":
            job.update(state="blocked_parser_unavailable", updated_at=_now())
            job["events"].append({"at": _now(), "event": "parser_unavailable", "probe": probe})
            _atomic_json(self.jobs_root / job_id / "job.json", job)
            return job
        job.update(state="parsing", stage_index=2, updated_at=_now())
        job["events"].append({"at": _now(), "event": "parser_started"})
        _atomic_json(self.jobs_root / job_id / "job.json", job)
        threading.Thread(target=self._parse_job, args=(job_id,), daemon=True).start()
        return job

    def _parse_job(self, job_id: str) -> None:
        job_root = self.jobs_root / job_id
        job = self.get_job(job_id)
        try:
            mineru_audit = job_root / "parsed/esg_rd_mineru_run.json"
            prior_mineru_failure = mineru_audit.exists() and job.get("state") in {
                "parsing",
                "parse_failed",
            }
            try:
                if prior_mineru_failure:
                    raise MinerUError("Resuming from preserved MinerU failure audit")
                asset_audit = self._ensure_mineru_asset_audit()
                job["mineru_asset_audit"] = asset_audit
                job["events"].append(
                    {
                        "at": _now(),
                        "event": "mineru_assets_verified",
                        "asset_count": asset_audit["asset_count"],
                        "asset_manifest_sha256": asset_audit["asset_manifest_sha256"],
                    }
                )
                record = parse_with_mineru(
                    job_root / "source.pdf",
                    job_root / "parsed",
                    executable=self.mineru_executable,
                    tools_config=self.mineru_tools_config,
                )
                parsed_root = job_root / "parsed"
                job.update(state="parsed", stage_index=2, updated_at=_now())
                job["parser_record"] = mineru_audit.relative_to(self.workspace).as_posix()
                job["parser_output_files"] = len(record["output_files"])
                job["events"].append({"at": _now(), "event": "parser_completed"})
            except MinerUError as exc:
                if mineru_audit.exists():
                    job["parser_record"] = mineru_audit.relative_to(self.workspace).as_posix()
                if not any(item.get("event") == "parser_failed" for item in job["events"]):
                    job["events"].append(
                        {
                            "at": _now(),
                            "event": "parser_failed",
                            "error": type(exc).__name__,
                            "detail": str(exc),
                        }
                    )
                job["events"].append({"at": _now(), "event": "native_pdf_fallback_started"})
                parsed_root = job_root / "parsed_native_fallback"
                fallback = parse_with_native_pdf_layout(job_root / "source.pdf", parsed_root)
                job.update(state="parsed_with_native_fallback", stage_index=2, updated_at=_now())
                job["parser_fallback_record"] = (
                    (parsed_root / "native_pdf_fallback_run.json")
                    .relative_to(self.workspace)
                    .as_posix()
                )
                job["parser_output_files"] = len(fallback["output_files"])
                job["events"].append({"at": _now(), "event": "native_pdf_fallback_completed"})
            summary = analyze_mineru_output(
                parsed_root,
                job_root / "analysis",
                source_sha256=job["source"]["sha256"],
                source_path=job_root / "source.pdf",
                workspace_root=self.workspace,
            )
            job.update(state="local_analysis_completed", stage_index=5, updated_at=_now())
            job["analysis"] = summary
            job["events"].append({"at": _now(), "event": "local_analysis_completed"})
        except (
            MinerUError,
            NativePDFFallbackError,
            OSError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            failed_state = "parse_failed" if "parser_record" not in job else "analysis_failed"
            job.update(state=failed_state, updated_at=_now())
            job["events"].append(
                {
                    "at": _now(),
                    "event": (
                        "parser_failed" if failed_state == "parse_failed" else "analysis_failed"
                    ),
                    "error": type(exc).__name__,
                    "detail": str(exc),
                }
            )
        _atomic_json(job_root / "job.json", job)


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "SustainTrace/0.1"

    @property
    def service(self) -> WorkbenchService:
        return self.server.service  # type: ignore[attr-defined]

    def _origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if origin and (
            origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:")
        ):
            return origin
        return None

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _png(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=86400")
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, request_path: str) -> None:
        static_root = self.server.static_root  # type: ignore[attr-defined]
        if not static_root.is_dir():
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "frontend_unavailable", "detail": "packaged frontend is missing"},
            )
            return
        relative = request_path.lstrip("/") or "index.html"
        candidate = (static_root / relative).resolve()
        try:
            candidate.relative_to(static_root)
        except ValueError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not candidate.is_file():
            candidate = static_root / "index.html"
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Cache-Control",
            "no-cache" if candidate.name == "index.html" else "public, max-age=31536000, immutable",
        )
        self.end_headers()
        self.wfile.write(body)

    def _request_json(self, *, max_bytes: int = 64 * 1024) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > max_bytes:
            raise ValueError("JSON request body has an invalid size")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object")
        return payload

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Filename")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/v1/health":
                self._json(HTTPStatus.OK, {"status": "ok", "time": _now()})
            elif parsed.path == "/api/v1/summary":
                self._json(HTTPStatus.OK, self.service.summary())
            elif parsed.path == "/api/v1/analytics":
                self._json(
                    HTTPStatus.OK,
                    self.service.analytics(company=query.get("company", [None])[0]),
                )
            elif parsed.path == "/api/v1/knowledge-schema":
                self._json(HTTPStatus.OK, self.service.knowledge_schema())
            elif parsed.path == "/api/v1/trusted-facts":
                self._json(
                    HTTPStatus.OK,
                    self.service.trusted_facts(
                        limit=min(int(query.get("limit", ["500"])[0]), 1000)
                    ),
                )
            elif parsed.path == "/api/v1/entities":
                self._json(
                    HTTPStatus.OK,
                    self.service.entities(limit=min(int(query.get("limit", ["500"])[0]), 1000)),
                )
            elif parsed.path == "/api/v1/relations":
                self._json(
                    HTTPStatus.OK,
                    self.service.relations(
                        limit=min(int(query.get("limit", ["500"])[0]), 1000),
                        entity_id=query.get("entity_id", [None])[0],
                        predicate=query.get("predicate", [None])[0],
                    ),
                )
            elif parsed.path == "/api/v1/repair-lifecycle":
                self._json(HTTPStatus.OK, self.service.repair_lifecycle())
            elif parsed.path == "/api/v1/facts":
                self._json(
                    HTTPStatus.OK,
                    query_facts(
                        self.service.knowledge_root,
                        company=query.get("company", [None])[0],
                        predicate=query.get("predicate", [None])[0],
                        include_candidates=query.get("include_candidates", ["false"])[0] == "true",
                        limit=min(int(query.get("limit", ["100"])[0]), 1000),
                    ),
                )
            elif parsed.path == "/api/v1/failures":
                self._json(
                    HTTPStatus.OK,
                    self.service.failures(
                        limit=min(int(query.get("limit", ["100"])[0]), 1000),
                        signature=query.get("signature", [None])[0],
                    ),
                )
            elif parsed.path == "/api/v1/jobs":
                self._json(
                    HTTPStatus.OK,
                    self.service.list_jobs(limit=min(int(query.get("limit", ["100"])[0]), 1000)),
                )
            elif parsed.path == "/api/v1/promotion-overlays":
                self._json(HTTPStatus.OK, self.service.promotion_overlays())
            elif match := re.fullmatch(
                r"/api/v1/facts/(fact-[a-zA-Z0-9_-]+)/evidence/(\d+)/preview",
                parsed.path,
            ):
                self._json(
                    HTTPStatus.OK,
                    self.service.evidence_preview(match.group(1), int(match.group(2))),
                )
            elif match := re.fullmatch(
                r"/api/v1/facts/(fact-[a-zA-Z0-9_-]+)/evidence/(\d+)/page\.png",
                parsed.path,
            ):
                self._png(self.service.evidence_page_png(match.group(1), int(match.group(2))))
            elif parsed.path.startswith("/api/v1/jobs/") and parsed.path.endswith("/facts"):
                job_id = parsed.path.removeprefix("/api/v1/jobs/").removesuffix("/facts")
                self._json(
                    HTTPStatus.OK,
                    self.service.job_fact_details(
                        job_id,
                        limit=min(int(query.get("limit", ["100"])[0]), 1000),
                    ),
                )
            elif parsed.path.startswith("/api/v1/jobs/") and parsed.path.endswith(
                "/promotion-reviews"
            ):
                job_id = parsed.path.removeprefix("/api/v1/jobs/").removesuffix(
                    "/promotion-reviews"
                )
                self._json(HTTPStatus.OK, self.service.promotion_reviews(job_id))
            elif parsed.path.startswith("/api/v1/jobs/") and parsed.path.endswith(
                "/promotion-staging"
            ):
                job_id = parsed.path.removeprefix("/api/v1/jobs/").removesuffix(
                    "/promotion-staging"
                )
                self._json(HTTPStatus.OK, self.service.promotion_staging(job_id))
            elif parsed.path.startswith("/api/v1/jobs/"):
                self._json(HTTPStatus.OK, self.service.get_job(parsed.path.rsplit("/", 1)[-1]))
            elif parsed.path.startswith("/api/"):
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            else:
                self._static(parsed.path)
        except (ValueError, FileNotFoundError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": type(exc).__name__, "detail": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == "/api/v1/jobs":
                if self.headers.get_content_type() != "application/pdf":
                    raise ValueError("Content-Type must be application/pdf")
                length = int(self.headers.get("Content-Length", "0"))
                job = self.service.create_job(
                    self.rfile,
                    content_length=length,
                    filename=self.headers.get("X-Filename", "report.pdf"),
                )
                job = self.service.start_parse(job["job_id"])
                self._json(HTTPStatus.CREATED, job)
            elif self.path.endswith("/parse") and self.path.startswith("/api/v1/jobs/"):
                job_id = self.path.removeprefix("/api/v1/jobs/").removesuffix("/parse")
                self._json(HTTPStatus.ACCEPTED, self.service.start_parse(job_id))
            elif self.path.startswith("/api/v1/jobs/") and self.path.endswith("/decision"):
                relative = self.path.removeprefix("/api/v1/jobs/").removesuffix("/decision")
                parts = relative.split("/promotion-reviews/")
                if len(parts) != 2 or not all(parts):
                    raise ValueError("invalid promotion review decision path")
                job_id, review_id = parts
                self._json(
                    HTTPStatus.OK,
                    self.service.decide_promotion_review(
                        job_id,
                        review_id,
                        self._request_json(),
                    ),
                )
            elif self.path.startswith("/api/v1/jobs/") and self.path.endswith("/commit"):
                relative = self.path.removeprefix("/api/v1/jobs/").removesuffix("/commit")
                parts = relative.split("/promotion-staging/")
                if len(parts) != 2 or not all(parts):
                    raise ValueError("invalid promotion staging commit path")
                job_id, staging_id = parts
                self._json(
                    HTTPStatus.OK,
                    self.service.commit_promotion_staging(job_id, staging_id, self._request_json()),
                )
            elif self.path.startswith("/api/v1/promotion-overlays/") and self.path.endswith(
                "/withdraw"
            ):
                overlay_id = self.path.removeprefix("/api/v1/promotion-overlays/").removesuffix(
                    "/withdraw"
                )
                if not overlay_id:
                    raise ValueError("invalid promotion overlay withdrawal path")
                self._json(
                    HTTPStatus.OK,
                    self.service.withdraw_promotion_overlay(overlay_id, self._request_json()),
                )
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except (ValueError, FileNotFoundError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": type(exc).__name__, "detail": str(exc)})


def serve(
    workspace: str | Path,
    host: str = "127.0.0.1",
    port: int = 8787,
    static_root: str | Path | None = None,
) -> None:
    server = ThreadingHTTPServer((host, port), WorkbenchHandler)
    server.service = WorkbenchService(workspace)  # type: ignore[attr-defined]
    server.static_root = (  # type: ignore[attr-defined]
        Path(static_root).resolve()
        if static_root is not None
        else Path(__file__).with_name("workbench_static").resolve()
    )
    print(f"SustainTrace listening on http://{host}:{port}", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local SustainTrace knowledge workbench")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    parser.add_argument("--static-root")
    args = parser.parse_args()
    serve(args.workspace, args.host, args.port, args.static_root)


if __name__ == "__main__":
    main()
