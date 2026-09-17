import json
from collections import Counter
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_semantic_boundary_negative_cases_are_complete_and_fail_closed():
    records = load_jsonl(KB / "boundary_semantic_negative_cases.jsonl")
    schema = json.loads(
        (ROOT / "schemas/knowledge/boundary-semantic-negative-case-v0.1.schema.json").read_text()
    )
    assert len(records) == 28
    assert Counter(r["boundary_class"] for r in records) == {
        "assurance_scope_metadata": 9,
        "metric_component_boundary": 6,
        "taxonomy_classification_boundary": 7,
        "organizational_population_boundary": 2,
        "target_and_performance_boundary": 4,
    }
    for record in records:
        validate(record, schema)
        assert record["current_status"] == "supervised_block"
        assert record["automatic_action"] == "report_unresolved_and_do_not_promote"
        assert record["source_fact_modified"] is False
        assert record["promotion_performed"] is False


def test_ontology_forbids_promotion_from_classification_alone():
    ontology = json.loads(
        (ROOT / "configs/knowledge/boundary_semantic_ontology_v0.1.json").read_text()
    )
    assert ontology["policy"]["default"] == "supervised_block"
    assert ontology["policy"]["promotion_from_classification_alone"] is False
    assert set(ontology["classes"]) == {
        "assurance_scope_metadata",
        "metric_component_boundary",
        "taxonomy_classification_boundary",
        "organizational_population_boundary",
        "target_and_performance_boundary",
    }
