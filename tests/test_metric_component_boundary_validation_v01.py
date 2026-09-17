import copy
import json
from pathlib import Path

import jsonschema

from esg_reliable_discovery.repair_controller import validate_metric_component_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

P18_SPEC = {
    "graph_path": "configs/framework/p18_two_dimensional_table_graph_v0.1.lock.json",
    "graph_sha256": "822e773b3555b4ba1442c41897c282c24fa0d1806f09f098a7fad7e25032251f",
    "graph_id": "P18-ENERGY-P131",
    "row": "fossil",
    "row_alias": "Total fossil energy consumption",
    "header": "2025",
    "row_values": ["812,912", "870,723"],
    "value_index": 0,
    "value_literal": "812,912",
    "component_role": "component",
    "method_role": "not_applicable",
    "footnote": None,
}


def load(name):
    return [json.loads(line) for line in (KB / name).read_text().splitlines() if line]


def test_all_metric_component_cases_pass_spatial_and_role_validation():
    records = load("metric_component_boundary_validations.jsonl")
    schema = json.loads(
        (ROOT / "schemas/knowledge/metric-component-boundary-validation-v0.1.schema.json")
        .read_text()
    )
    assert len(records) == 6
    for record in records:
        jsonschema.validate(record, schema)
        assert record["validation_status"] == "ready_for_supervised_execution"
        assert all(record["checks"].values())
        assert record["execution_performed"] is False
        assert record["promotion_performed"] is False


def test_missing_row_axis_fails_closed_even_when_literal_remains_present():
    case = next(
        item
        for item in load("boundary_semantic_negative_cases.jsonl")
        if item["fact_record_id"] == "fact-e4f210c8a1a8bb4a2294c19b"
    )
    fact = next(
        item
        for item in load("fact_records.jsonl")
        if item["record_id"] == case["fact_record_id"]
    )
    binding = next(
        item for item in load("source_native_field_bindings.jsonl")
        if item["fact_record_id"] == case["fact_record_id"]
    )
    spec = P18_SPEC
    graph_path = ROOT / spec["graph_path"]
    graph = json.loads(graph_path.read_text())
    broken = copy.deepcopy(graph)
    target = next(item for item in broken["graphs"] if item["graph_id"] == spec["graph_id"])
    target["row_axis"].remove(spec["row"])
    record = validate_metric_component_case(
        case, fact, binding, broken, graph_path, ROOT, spec
    )
    assert record["checks"]["literal_in_native_context"] is True
    assert record["checks"]["row_axis_bound"] is False
    assert record["validation_status"] == "not_ready"
    assert record["execution_performed"] is False
