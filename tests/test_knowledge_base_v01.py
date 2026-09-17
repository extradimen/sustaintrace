import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import (
    canonicalize_predicate,
    reference_to_fact_records,
    result_to_failure_records,
    stable_id,
)

ROOT = Path(__file__).resolve().parents[1]


def test_stable_id_is_deterministic_and_order_independent():
    assert stable_id("fact", {"a": 1, "b": 2}) == stable_id("fact", {"b": 2, "a": 1})


def test_period_suffix_is_preserved_as_a_qualifier():
    assert canonicalize_predicate("scope1_tco2e::2025") == ("scope1_tco2e", "2025")
    assert canonicalize_predicate("scope::market_based") == ("scope::market_based", None)


def test_simulated_reference_is_not_automatically_promoted():
    path = ROOT / "data/annotations/p23_simulated/P23-GHG-CALC-001.json"
    records = reference_to_fact_records(path, ROOT)
    assert records
    assert all(record["knowledge_status"] == "reference_candidate" for record in records)
    assert all(record["trust_tier"] == "C" for record in records)
    assert all(record["promotion"]["eligible"] is False for record in records)
    assert {record["qualifiers"]["period_literal"] for record in records} >= {"2024", "2025"}


def test_source_registry_metadata_can_enrich_fact_subject():
    path = ROOT / "data/annotations/p23_simulated/P23-GHG-CALC-001.json"
    index = {
        "P23-GSK-AR2025": {
            "document_id": "P23-GSK-AR2025",
            "company": "GSK plc",
            "sha256": "a" * 64,
        }
    }
    records = reference_to_fact_records(path, ROOT, index)
    assert records[0]["subject"]["document_metadata"][0]["company"] == "GSK plc"


def test_reference_context_is_preserved_for_joint_qualification():
    path = ROOT / "data/annotations/p6_simulated/P6-CALC-001.json"
    record = reference_to_fact_records(path, ROOT)[0]
    assert record["qualifiers"]["normalized_unit"] == "percent"
    assert record["qualifiers"]["calculation_expression"] == "(0.43 - 0.48) / 0.48 * 100"
    assert "reference_period" in record["qualifiers"]
    assert "scope_boundary" in record["qualifiers"]


def test_failed_p23_tasks_become_failure_observations_only():
    path = ROOT / "data/results/p23_v32_unseen_lockbox_v0.1_result.lock.json"
    records = result_to_failure_records(path, ROOT)
    by_task = {record["task_id"]: record for record in records}
    assert set(by_task) == {"P23-ASSURE-001", "P23-BOUNDARY-001", "P23-WORKFORCE-CALC-001"}
    assert by_task["P23-WORKFORCE-CALC-001"]["failure_owner"] == "candidate_model"
    assert by_task["P23-WORKFORCE-CALC-001"]["failure_category"] == "model_behavior"
    assert (
        by_task["P23-WORKFORCE-CALC-001"]["failure_signature"]
        == "CALCULATION_HANDLE_UNMAPPED"
    )
    assert by_task["P23-ASSURE-001"]["failure_owner"] == "framework"
    assert by_task["P23-ASSURE-001"]["failure_signature"] == "EXECUTOR_TYPE_MISMATCH"


def test_legacy_list_shaped_task_results_are_migrated():
    path = ROOT / "data/results/p2_locked_holdout_v0.1_result.lock.json"
    records = result_to_failure_records(path, ROOT)
    assert {record["task_id"] for record in records} >= {
        "P2-DEX-001",
        "P2-DEX-002",
        "P2-CALC-001",
    }
    by_task = {record["task_id"]: record for record in records}
    assert by_task["P2-CONFLICT-001"]["failure_owner"] == "candidate_model"


def test_legacy_parser_and_framework_failures_are_attributed_conservatively():
    p3 = result_to_failure_records(
        ROOT / "data/results/p3_unseen_generalization_v0.1_result.lock.json", ROOT
    )
    p3_by_task = {record["task_id"]: record for record in p3}
    assert p3_by_task["P3-CALC-001"]["failure_owner"] == "document_pipeline"
    assert p3_by_task["P3-DEX-002"]["failure_owner"] == "candidate_model"

    p14 = result_to_failure_records(
        ROOT / "data/results/p14_v23_unseen_lockbox_v0.1_result.lock.json", ROOT
    )
    p14_by_task = {record["task_id"]: record for record in p14}
    assert p14_by_task["P14-ASSURE-001"]["failure_owner"] == "framework"
    assert p14_by_task["P14-ASSURE-001"]["failure_signature"] == "PREFLIGHT_CONTRACT_GATE"


def test_generated_manifest_outputs_are_hash_addressed_if_present():
    manifest_path = ROOT / "data/knowledge_bases/v0.1/migration_manifest.lock.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text())
    assert manifest["trust_policy"]["automatic_fact_promotion"] is False
    assert manifest["trust_policy"]["automatic_repair_execution"] is False
