from pathlib import Path

import pytest
from jsonschema import validate

from esg_reliable_discovery.knowledge_query import query_facts

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def test_default_query_returns_only_curated_tier_b_facts():
    result = query_facts(KB)
    total_facts = sum(1 for line in (KB / "fact_records.jsonl").read_text().splitlines() if line)
    trusted_ids = {
        __import__("json").loads(line)["record_id"]
        for line in (KB / "trusted_fact_records.jsonl").read_text().splitlines()
        if line
    }
    assert result["policy"]["default_scope"] == "promoted_tier_b_only"
    assert result["inventory"]["trusted_tier_b"] == 149
    assert result["inventory"]["candidates_not_trusted"] == total_facts - 149
    assert result["pagination"]["matched"] == 149
    assert all(item["effective_trust"] == "trusted_tier_b" for item in result["records"])
    assert all(item["fact"]["record_id"] in trusted_ids for item in result["records"])
    assert all(not item["unresolved_gaps"] for item in result["records"])


def test_candidate_query_exposes_trust_and_gaps():
    result = query_facts(KB, task_id="P23-GHG-CALC-001", include_candidates=True)
    assert result["records"]
    trust_states = {item["effective_trust"] for item in result["records"]}
    assert trust_states == {"candidate_not_trusted", "trusted_tier_b"}
    promoted = [item for item in result["records"] if item["effective_trust"] == "trusted_tier_b"]
    assert len(promoted) == 1
    assert promoted[0]["fact"]["predicate"]["canonical_key"] == "issuer_reduction_percent"
    assert all("unresolved_gaps" in item for item in result["records"])
    assert all("tier_b_adjudication" in item for item in result["records"])
    assert all("independent_adjudication" in item for item in result["records"])
    assert all(
        item["fact"]["subject"]["task_id"] == "P23-GHG-CALC-001" for item in result["records"]
    )
    schema = __import__("json").loads(
        (ROOT / "schemas/knowledge/fact-query-response-v0.1.schema.json").read_text()
    )
    validate(result, schema)


def test_query_filters_by_company_and_predicate():
    result = query_facts(
        KB,
        company="GSK",
        predicate="scope1_energy_thousand_tco2e",
        include_candidates=True,
    )
    assert result["pagination"]["matched"] >= 1
    assert all(
        item["fact"]["predicate"]["canonical_key"] == "scope1_energy_thousand_tco2e"
        for item in result["records"]
    )


def test_query_rejects_unsafe_pagination():
    with pytest.raises(ValueError, match="limit"):
        query_facts(KB, limit=0)
    with pytest.raises(ValueError, match="offset"):
        query_facts(KB, offset=-1)
