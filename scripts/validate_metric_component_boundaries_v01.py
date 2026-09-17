from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, validate_records
from esg_reliable_discovery.repair_controller import validate_metric_component_case

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"

P18_GRAPH = "configs/framework/p18_two_dimensional_table_graph_v0.1.lock.json"
P19_GRAPH = "configs/framework/p19_two_dimensional_table_graph_v0.1.lock.json"
P21_GRAPH = "configs/framework/p21_two_dimensional_table_graph_v0.1.lock.json"

SPECS = {
    "fact-e4f210c8a1a8bb4a2294c19b": {
        "graph_path": P18_GRAPH,
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
    },
    "fact-62c71778168057796ee18741": {
        "graph_path": P19_GRAPH,
        "graph_sha256": "8a5e730282a59008157266b7d82d691b48d9fcd7ba5e80e642ff2e9e91e81732",
        "graph_id": "P19-GHG-P066",
        "row": "Category 1",
        "row_alias": "Category 1: Purchased goods and Services",
        "header": "2025",
        "row_values": ["1,383", "1,215", "1,018"],
        "value_index": 0,
        "value_literal": "1,383",
        "component_role": "component",
        "method_role": "not_applicable",
        "footnote": None,
    },
    "fact-40aca017502b9df9b11982d8": {
        "graph_path": P21_GRAPH,
        "graph_sha256": "1a90d91f7884830ed2c001717ad31d3b2bb18d46d30db69fea0810b4f5867b0e",
        "graph_id": "P21-GHG-P194-P195",
        "row": "Category 1",
        "row_alias": "1 – Purchased goods and services",
        "header": "2024 financial adjusted",
        "row_values": ["52.56", "54.39", "51.54"],
        "value_index": 2,
        "value_literal": "51.54",
        "component_role": "component",
        "method_role": "financial",
        "footnote": "c",
    },
    "fact-581342d614c70d3bf9d82e07": {
        "graph_path": P21_GRAPH,
        "graph_sha256": "1a90d91f7884830ed2c001717ad31d3b2bb18d46d30db69fea0810b4f5867b0e",
        "graph_id": "P21-GHG-P194-P195",
        "row": "Category 1",
        "row_alias": "1 – Purchased goods and services",
        "header": "2025 financial",
        "row_values": ["52.56", "54.39", "51.54"],
        "value_index": 0,
        "value_literal": "52.56",
        "component_role": "component",
        "method_role": "financial",
        "footnote": None,
    },
    "fact-8f1c36a0aacaf76887386a80": {
        "graph_path": P21_GRAPH,
        "graph_sha256": "1a90d91f7884830ed2c001717ad31d3b2bb18d46d30db69fea0810b4f5867b0e",
        "graph_id": "P21-GHG-P194-P195",
        "row": "Category 12",
        "row_alias": "12 – End-of-life treatment of sold products",
        "header": "2024 financial adjusted",
        "row_values": ["27.17", "27.79", "25.67"],
        "value_index": 2,
        "value_literal": "25.67",
        "component_role": "component",
        "method_role": "financial",
        "footnote": "c",
    },
    "fact-fd4cd9bfff9f26d98c2b485c": {
        "graph_path": P21_GRAPH,
        "graph_sha256": "1a90d91f7884830ed2c001717ad31d3b2bb18d46d30db69fea0810b4f5867b0e",
        "graph_id": "P21-GHG-P194-P195",
        "row": "Category 12",
        "row_alias": "12 – End-of-life treatment of sold products",
        "header": "2025 financial",
        "row_values": ["27.17", "27.79", "25.67"],
        "value_index": 0,
        "value_literal": "27.17",
        "component_role": "component",
        "method_role": "financial",
        "footnote": None,
    },
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    cases_path = KB / "boundary_semantic_negative_cases.jsonl"
    facts_path = KB / "fact_records.jsonl"
    bindings_path = KB / "source_native_field_bindings.jsonl"
    cases = [
        item for item in load_jsonl(cases_path)
        if item["boundary_class"] == "metric_component_boundary"
    ]
    facts = {item["record_id"]: item for item in load_jsonl(facts_path)}
    bindings = {
        item["fact_record_id"]: item for item in load_jsonl(bindings_path)
    }
    graph_cache = {}
    records = []
    for case in cases:
        spec = SPECS[case["fact_record_id"]]
        graph_path = ROOT / spec["graph_path"]
        graph = graph_cache.setdefault(graph_path, json.loads(graph_path.read_text()))
        records.append(
            validate_metric_component_case(
                case,
                facts[case["fact_record_id"]],
                bindings[case["fact_record_id"]],
                graph,
                graph_path,
                ROOT,
                spec,
            )
        )
    records.sort(key=lambda item: (item["task_id"], item["predicate"]))
    schema_path = (
        ROOT / "schemas/knowledge/metric-component-boundary-validation-v0.1.schema.json"
    )
    validate_records(records, json.loads(schema_path.read_text()))
    output_path = KB / "metric_component_boundary_validations.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    counts = Counter(item["validation_status"] for item in records)
    summary = {
        "schema_version": "0.1",
        "status": "metric_component_boundary_validation_complete",
        "records": len(records),
        "validation_status_counts": dict(sorted(counts.items())),
        "executions_performed": 0,
        "promotions_performed": 0,
        "inputs": {
            "negative_cases_sha256": sha256_file(cases_path),
            "facts_sha256": sha256_file(facts_path),
            "bindings_sha256": sha256_file(bindings_path),
            "graph_sha256": {
                path.relative_to(ROOT).as_posix(): sha256_file(path)
                for path in sorted(graph_cache, key=str)
            },
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "validator_enabled_after_positive_and_destructive_negative_regression; "
            "supervised_execution_only"
        ),
    }
    summary_path = KB / "metric_component_boundary_validation_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
