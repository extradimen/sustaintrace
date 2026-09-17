from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def audit_synthetic_benchmark(
    task_pack_path: str | Path,
    reference_schema_path: str | Path,
    acquisition_manifest_path: str | Path,
    exclusion_lock_path: str | Path,
    repository_root: str | Path = ".",
) -> dict[str, Any]:
    root = Path(repository_root)
    pack = json.loads(Path(task_pack_path).read_text(encoding="utf-8"))
    schema = json.loads(Path(reference_schema_path).read_text(encoding="utf-8"))
    acquisition = json.loads(Path(acquisition_manifest_path).read_text(encoding="utf-8"))
    exclusion_lock = json.loads(Path(exclusion_lock_path).read_text(encoding="utf-8"))
    documents = {item["document_id"]: item for item in acquisition["documents"]}
    exclusions = {
        item["candidate_id"]: set(item["excluded_pages"])
        for item in exclusion_lock["documents"]
    }
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    tasks = pack.get("tasks", [])
    if pack.get("status") != "frozen":
        errors.append("task_pack_not_frozen")
    if pack.get("verified_reference_count") != 24:
        errors.append("declared_verified_reference_count_failed")
    task_ids = [task.get("task_id") for task in tasks]
    if len(tasks) != 24 or len(set(task_ids)) != 24:
        errors.append("task_count_or_uniqueness_failed")
    expected_quotas = {
        "abstention": 3,
        "controlled_conflict": 3,
        "cross_page_relation": 4,
        "deterministic_calculation": 4,
        "direct_extraction": 6,
        "scope_subject_boundary": 4,
    }
    if dict(sorted(Counter(task.get("task_type") for task in tasks).items())) != expected_quotas:
        errors.append("task_quota_failed")

    verified_references = 0
    for task in tasks:
        task_id = task["task_id"]
        if task.get("question_status") != "frozen":
            errors.append(f"{task_id}:question_not_frozen")
        document = documents.get(task["document_id"])
        if not document or document.get("ingestion_status") != "verified":
            errors.append(f"{task_id}:document_not_verified")
            continue
        overlap = set(task.get("target_pages", [])) & exclusions.get(task["candidate_id"], set())
        if overlap:
            errors.append(f"{task_id}:excluded_target_pages:{sorted(overlap)}")
        if any(page < 1 or page > document["page_count"] for page in task.get("target_pages", [])):
            errors.append(f"{task_id}:target_page_out_of_range")
        reference_path = root / task["reference_file"]
        if not reference_path.exists():
            errors.append(f"{task_id}:reference_missing")
            continue
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        validation_errors = list(validator.iter_errors(reference))
        if validation_errors:
            errors.append(f"{task_id}:reference_schema_failed")
            continue
        if reference["task_id"] != task_id or reference["question"] != task["question"]:
            errors.append(f"{task_id}:reference_identity_failed")
        if reference.get("reference_status") != "verified":
            errors.append(f"{task_id}:reference_not_verified")
            continue
        for evidence in reference["evidence"]:
            if evidence["document_id"] != task["document_id"]:
                errors.append(f"{task_id}:evidence_document_failed")
            if evidence["document_sha256"] != document["sha256"]:
                errors.append(f"{task_id}:evidence_hash_failed")
            if evidence["pdf_page"] not in task["target_pages"]:
                errors.append(f"{task_id}:evidence_outside_target_pages")
        intervention_id = task.get("controlled_intervention_id")
        if intervention_id:
            intervention_path = root / "data/controlled_interventions" / f"{intervention_id}.json"
            if not intervention_path.exists():
                errors.append(f"{task_id}:intervention_missing")
            else:
                intervention = json.loads(intervention_path.read_text(encoding="utf-8"))
                if intervention.get("source_document_sha256") != document["sha256"]:
                    errors.append(f"{task_id}:intervention_source_hash_failed")
        verified_references += 1
    return {
        "schema_version": "1.0",
        "benchmark_type": pack.get("benchmark_type"),
        "task_count": len(tasks),
        "verified_reference_count": verified_references,
        "task_quotas": dict(sorted(Counter(task.get("task_type") for task in tasks).items())),
        "errors": errors,
        "passed": not errors,
        "human_gold_standard": False,
        "inference_allowed": False,
    }
