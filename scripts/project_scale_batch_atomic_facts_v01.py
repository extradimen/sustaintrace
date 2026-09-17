from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from esg_reliable_discovery.table_projection import build_two_axis_table_graph

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FACTS = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_001_fact_records.jsonl"
OUTPUT = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_001_atomic_fact_records.jsonl"
GRAPHS = ROOT / "data/manifests/scale_batch_001_table_graphs.lock.json"
SUMMARY = ROOT / "data/results/scale_batch_001_atomic_projection.lock.json"
BATCH_ID = "KB-SCALE-BATCH-001-RESUME01"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def stable_id(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "fact-" + hashlib.sha256(encoded).hexdigest()[:24]


def canonical_key(row_header: str) -> str:
    value = re.sub(r"\([^)]*\)", "", row_header).casefold()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value[:80] or "unnamed_metric"


def infer_unit(row_header: str, raw_value: str, explicit_unit: str | None = None) -> str | None:
    if explicit_unit:
        normalized = " ".join(explicit_unit.split()).casefold()
        controlled = {
            "%": "percent",
            "gwh": "GWh",
            "gwh/usdm": "GWh_per_USD_million",
            "headcount": "people",
        }
        return controlled.get(normalized, explicit_unit)
    lowered = row_header.casefold()
    if raw_value.endswith("%"):
        return "percent"
    if "thousands of m³" in lowered:
        return "thousand_m3"
    if "m³ per million euros" in lowered:
        return "m3_per_million_eur"
    if "m³ per tons produced" in lowered:
        return "m3_per_tonne_produced"
    if "employees" in lowered:
        return "people"
    return None


def main() -> None:
    source_records = load_jsonl(SOURCE_FACTS)
    table_records = [record for record in source_records if "<table>" in str(record["value"])]
    graphs = []
    facts = []
    for source in table_records:
        parsed = build_two_axis_table_graph(source["value"])
        graphs.append(
            {
                "source_fact_record_id": source["record_id"],
                "document_id": source["subject"]["document_ids"][0],
                "pdf_page": source["evidence"][0]["pdf_page"],
                "graphs": parsed,
            }
        )
        for graph in parsed:
            for cell in graph["cells"]:
                period = cell["column_header"]
                identity = [source["record_id"], cell["cell_handle"]]
                facts.append(
                    {
                        "schema_version": "0.1",
                        "record_kind": "fact",
                        "record_id": stable_id(identity),
                        "knowledge_status": "reference_candidate",
                        "trust_tier": "C",
                        "subject": {
                            **source["subject"],
                            "task_id": f"{source['subject']['task_id']}-{cell['cell_handle']}",
                        },
                        "predicate": {
                            "raw_key": cell["row_header"],
                            "canonical_key": canonical_key(cell["row_header"]),
                        },
                        "value": cell["normalized_value"],
                        "qualifiers": {
                            "period_literal": period,
                            "value_origin": "deterministic_two_axis_table_projection",
                            "reference_period": cell["normalized_period"],
                            "normalized_unit": infer_unit(
                                cell["row_header"], cell["raw_value"], cell["unit"]
                            ),
                            "scope_boundary": cell["row_header"],
                            "calculation_expression": None,
                            "answer_status": "atomic_table_cell_candidate",
                        },
                        "evidence": [
                            {
                                **source["evidence"][0],
                                "quote": cell["raw_value"],
                                "table_index": cell["table_index"],
                                "row_index": cell["row_index"],
                                "column_index": cell["column_index"],
                                "row_header": cell["row_header"],
                                "row_header_column_index": cell["row_header_column_index"],
                                "column_header": cell["column_header"],
                                "normalized_period": cell["normalized_period"],
                                "unit": cell["unit"],
                                "unit_column_index": cell["unit_column_index"],
                                "cell_handle": cell["cell_handle"],
                            }
                        ],
                        "provenance": {
                            **source["provenance"],
                            "reference_status": (
                                "deterministic_two_axis_projection_pending_independent_gate"
                            ),
                        },
                        "promotion": {
                            "eligible": False,
                            "reason": "requires_independent_cell_coordinate_corroboration",
                        },
                    }
                )
    schema = json.loads(
        (ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text(encoding="utf-8")
    )
    for fact in facts:
        Draft202012Validator(schema).validate(fact)
    OUTPUT.write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in facts),
        encoding="utf-8",
    )
    graph_payload = {
        "schema_version": "0.1",
        "batch_id": BATCH_ID,
        "status": "table_graphs_built_fail_closed",
        "source_table_candidates": len(table_records),
        "graphs": graphs,
    }
    GRAPHS.write_text(json.dumps(graph_payload, indent=2) + "\n", encoding="utf-8")
    rejected = sum(
        len(graph.get("rejected_rows", []))
        for item in graphs
        for graph in item["graphs"]
    )
    summary = {
        "schema_version": "0.1",
        "batch_id": BATCH_ID,
        "status": "atomic_projection_complete_candidates_not_promoted",
        "source_table_candidates": len(table_records),
        "atomic_fact_candidates": len(facts),
        "rejected_ambiguous_rows": rejected,
        "promoted_tier_b": 0,
        "outputs": {
            "atomic_facts": {
                "path": OUTPUT.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
            },
            "table_graphs": {
                "path": GRAPHS.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(GRAPHS.read_bytes()).hexdigest(),
            },
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
