import json
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.evidence_repair_triage import index_evidence_contracts
from esg_reliable_discovery.repair_controller import plan_evidence_repair_with_contract

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    catalog = json.loads(
        (ROOT / "configs/knowledge/evidence_repair_contract_catalog_v0.1.json").read_text()
    )
    schema = json.loads(
        (ROOT / "schemas/knowledge/evidence-repair-contract-v0.1.schema.json").read_text()
    )
    failures = [
        json.loads(line)
        for line in (ROOT / "data/knowledge_bases/v0.1/failure_records.jsonl")
        .read_text()
        .splitlines()
        if line
        and json.loads(line)["failure_signature"]
        in {
            "EVIDENCE_GROUNDING_MISMATCH",
            "EVIDENCE_SELECTION_GAP",
            "TARGET_ASSURANCE_WINDOW_INCOMPLETE",
        }
    ]
    return catalog, schema, failures


def test_contract_catalog_validates_and_covers_all_observed_causal_subtypes():
    catalog, schema, failures = fixtures()
    validator = Draft202012Validator(schema)
    for contract in catalog["contracts"]:
        assert not list(validator.iter_errors(contract))
        assert contract["candidate_output_rewrite_allowed"] is False
    index = index_evidence_contracts(catalog)
    for failure in failures:
        plan, binding = plan_evidence_repair_with_contract(
            failure, catalog, mode="locked_evaluation"
        )
        assert plan["causal_subtype"] in index
        assert binding["decision"] == "archive_only"
        assert binding["execution_performed"] is False


def test_operational_truncated_quote_is_blocked_not_rewritten():
    catalog, _, failures = fixtures()
    failure = next(
        item
        for item in failures
        if "truncated" in json.dumps(item["observed_stage_states"]).casefold()
    )
    _, binding = plan_evidence_repair_with_contract(failure, catalog, mode="operational")
    assert binding["decision"] == "blocked_by_contract"
    assert binding["candidate_output_rewrite_allowed"] is False


def test_operational_period_window_requires_supervised_contract_validation():
    catalog, _, failures = fixtures()
    failure = next(
        item for item in failures if item["failure_signature"] == "EVIDENCE_SELECTION_GAP"
    )
    plan, binding = plan_evidence_repair_with_contract(failure, catalog, mode="operational")
    assert plan["new_lineage_required"] is True
    assert binding["decision"] == "contract_ready_for_supervised_validation"
    assert "new_run_lineage" in binding["validation_gates"]
