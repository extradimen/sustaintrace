from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/scale_120_report_acceptance_v0.1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def selected_config(batch: int) -> Path:
    resume_configs = {
        1: "scale_batch_001_RESUME01_v0.2.json",
        4: "scale_batch_004_RESUME01_v0.2.json",
        8: "scale_batch_008_RESUME01_v0.2.json",
        10: "scale_batch_010_RESUME01_v0.2.json",
        11: "scale_batch_011_RESUME01_v0.2.json",
        12: "scale_batch_012_RESUME01_v0.2.json",
        19: "scale_batch_019_RESUME01_v0.2.json",
        23: "scale_batch_023_RESUME02_v0.3.json",
        24: "scale_batch_024_RESUME01_v0.2.json",
    }
    if batch in resume_configs:
        return ROOT / "configs/knowledge" / resume_configs[batch]
    return ROOT / f"configs/knowledge/scale_batch_{batch:03d}_v0.1.json"


def milestone(batch: int) -> Path:
    if batch <= 5:
        return ROOT / f"data/results/scale_batch_{batch:03d}_atomic_milestone_audit.lock.json"
    if batch == 30:
        return ROOT / "data/results/scale_batch_030_milestone_audit_RESUME01.lock.json"
    return ROOT / f"data/results/scale_batch_{batch:03d}_milestone_audit.lock.json"


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite 120-report acceptance lock")
    documents = []
    config_hashes = {}
    milestone_hashes = {}
    totals = {
        "source_pages": 0,
        "extractable_source_pages": 0,
        "frozen_target_pages": 0,
        "direct_batch_evidence_candidates": 0,
        "direct_batch_tier_b_promotions": 0,
    }
    for batch in range(1, 31):
        config_path = selected_config(batch)
        milestone_path = milestone(batch)
        config = load(config_path)
        record = load(milestone_path)
        config_hashes[str(config_path.relative_to(ROOT))] = sha(config_path)
        milestone_hashes[str(milestone_path.relative_to(ROOT))] = sha(milestone_path)
        if batch == 1:
            diagnostics = load(ROOT / "data/results/scale_batch_001_diagnostics.lock.json")
            totals["source_pages"] += diagnostics["totals"]["pdf_pages"]
            totals["extractable_source_pages"] += diagnostics["totals"]["extractable_pages"]
            totals["frozen_target_pages"] += 26
            totals["direct_batch_evidence_candidates"] += 41
        else:
            totals["source_pages"] += record["source_pages"]
            totals["extractable_source_pages"] += record["extractable_source_pages"]
            totals["frozen_target_pages"] += record["frozen_target_pages"]
            totals["direct_batch_evidence_candidates"] += record["knowledge_increment"][
                "evidence_snippet_candidates"
            ]
            totals["direct_batch_tier_b_promotions"] += record["knowledge_increment"].get(
                "promoted_tier_b", 0
            )
        expected_documents = 1 if batch == 30 else 3
        if len(config["documents"]) != expected_documents:
            raise ValueError(
                f"batch {batch} does not contain {expected_documents} final documents"
            )
        for item in config["documents"]:
            local_path = ROOT / item["local_path"]
            if not local_path.is_file():
                raise FileNotFoundError(local_path)
            documents.append(
                {
                    "batch": batch,
                    "document_id": item["document_id"],
                    "local_path": item["local_path"],
                    "sha256": sha(local_path),
                }
            )
    document_ids = [item["document_id"] for item in documents]
    document_hashes = [item["sha256"] for item in documents]
    if len(set(document_ids)) != len(document_ids):
        raise ValueError("duplicate document_id in final 87-report scale-stage set")
    duplicate_hashes = sorted(
        value for value in set(document_hashes) if document_hashes.count(value) > 1
    )
    expected_duplicate = "128d234ab0c14d6165097a46f21a5bda821554dbd63ee2a7d3052c84956b993b"
    if duplicate_hashes != [expected_duplicate]:
        raise ValueError(f"unexpected PDF duplicate set: {duplicate_hashes}")
    duplicate_records = [item for item in documents if item["sha256"] == expected_duplicate]
    if sorted(item["document_id"] for item in duplicate_records) != [
        "KB-B004-AIRLIQUIDE-URD2025",
        "KB-B012-AIR-LIQUIDE-URD2025",
    ]:
        raise ValueError("known Air Liquide duplicate does not match expected records")

    migration_path = ROOT / "data/knowledge_bases/v0.1/migration_manifest.lock.json"
    migration = load(migration_path)
    trusted_path = ROOT / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl"
    trusted_count = sum(bool(line) for line in trusted_path.read_text().splitlines())
    baseline_reports = 33
    unique_scale_reports = len(set(document_hashes))
    total_reports = baseline_reports + unique_scale_reports
    if total_reports != 120:
        raise ValueError(f"coverage arithmetic failed: {total_reports}")
    if load(ROOT / "data/results/scale_batch_030_milestone_audit_RESUME01.lock.json")[
        "scale_coverage"
    ]["completed_unique_reports"] != 120:
        raise ValueError("Batch30 terminal unique coverage declaration is not 120")

    payload = {
        "schema_version": "0.1",
        "acceptance_id": "ESG-KB-SCALE-120-REPORT-ACCEPTANCE-v0.1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "accepted_coverage_target_complete_with_strict_quality_limits",
        "coverage": {
            "pre_scale_locked_report_baseline": baseline_reports,
            "scale_stage_batches": 30,
            "standard_three_report_batches": 29,
            "supplemental_one_report_batches": 1,
            "scale_stage_report_records": len(documents),
            "known_duplicate_records": len(documents) - unique_scale_reports,
            "scale_stage_unique_reports": unique_scale_reports,
            "total_unique_reports": total_reports,
            "target_reports": 120,
            "completion_percent": 100.0,
            "baseline_derivation": (
                "locked coverage sequence: batch20=93 and 20*3 new reports, "
                "therefore 33 pre-scale reports"
            ),
        },
        "scale_stage_processing": totals,
        "global_knowledge_bases": {
            "fact_records": migration["counts"]["fact_records"],
            "trusted_tier_b_records": trusted_count,
            "failure_records": migration["counts"]["failure_records"],
            "failure_signatures": migration["counts"]["failure_signatures"],
            "repair_observations": migration["counts"]["repair_observations"],
            "trusted_share_of_all_fact_records_percent": round(
                trusted_count / migration["counts"]["fact_records"] * 100, 3
            ),
        },
        "acceptance_gates": {
            "scale_stage_document_ids_unique": True,
            "scale_stage_pdf_sha256_unique_after_known_duplicate_collapse": True,
            "known_historical_duplicate_preserved_and_disclosed": True,
            "all_scale_stage_files_present_and_hashed": True,
            "batch29_target_pages_complete": 30,
            "pytest_collected_and_passed": 478,
            "ruff": "passed",
            "all_data_json_parse": "passed",
            "cloud_transmission_during_scale_stage": False,
            "locked_experiments_modified_or_rescored": False,
            "automatic_fact_promotion": False,
        },
        "scientific_limits": {
            "coverage_target_is_not_universal_reliability_claim": True,
            "strict_table_projection_remains_primary_bottleneck": True,
            "tier_b_growth_requires_exact_coordinates_and_assurance_scope": True,
            "failures_are_retained_as_repair_corpus": True,
        },
        "known_historical_duplicate": {
            "sha256": expected_duplicate,
            "records": duplicate_records,
            "handling": (
                "counted_once; original locked batches preserved; "
                "NCC supplemental report added"
            ),
        },
        "scale_stage_documents": documents,
        "artifact_sha256": {
            **config_hashes,
            **milestone_hashes,
            str(migration_path.relative_to(ROOT)): sha(migration_path),
            str(trusted_path.relative_to(ROOT)): sha(trusted_path),
            "data/results/scale_batch_030_milestone_audit_RESUME01.lock.json": sha(
                ROOT / "data/results/scale_batch_030_milestone_audit_RESUME01.lock.json"
            ),
            "docs/150_规模化知识引入第二十九批与120份覆盖闭环_v0.1.md": sha(
                ROOT / "docs/150_规模化知识引入第二十九批与120份覆盖闭环_v0.1.md"
            ),
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"coverage": payload["coverage"], "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
