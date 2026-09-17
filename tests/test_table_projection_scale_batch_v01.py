from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.table_projection import (
    build_two_axis_table_graph,
    normalize_numeric_literal,
)

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_001_fact_records.jsonl"


def records() -> list[dict]:
    return [json.loads(line) for line in FACTS.read_text().splitlines() if line]


def find(record_id: str) -> dict:
    return next(record for record in records() if record["record_id"] == record_id)


def test_numeric_literal_normalization_preserves_percent_semantics() -> None:
    assert normalize_numeric_literal("33,184") == {
        "normalized_value": "33184",
        "normalized_unit": None,
    }
    assert normalize_numeric_literal("97.8%") == {
        "normalized_value": "97.8",
        "normalized_unit": "percent",
    }
    assert normalize_numeric_literal("1,044 (8.6)%") is None
    assert normalize_numeric_literal("106,890¹") == {
        "normalized_value": "106890",
        "normalized_unit": None,
        "literal_annotation": "¹",
    }


def test_danone_water_table_builds_auditable_two_axis_cells() -> None:
    table = find("fact-15c228a5d1f5012457ea957d")["value"]
    graph = build_two_axis_table_graph(table)[0]
    assert graph["status"] == "two_axis_graph_built"
    assert len(graph["cells"]) == 8
    target = next(
        cell
        for cell in graph["cells"]
        if cell["row_header"].startswith("Water related") and cell["column_header"] == "2025"
    )
    assert target["raw_value"] == "33,184"
    assert target["normalized_value"] == "33184"
    assert target["row_index"] == 1
    assert target["column_index"] == 2


def test_ambiguous_or_compound_tables_fail_closed() -> None:
    sse = find("fact-07a36e31e73564047ce64350")["value"]
    assert build_two_axis_table_graph(sse)[0]["status"] == "ambiguous_no_two_axis_period_header"
    danone = find("fact-1bc5b9b12b3f75a6cc49f927")["value"]
    graph = build_two_axis_table_graph(danone)[0]
    assert graph["status"] == "two_axis_graph_built"
    assert graph["rejected_rows"]


def test_multi_metadata_columns_bind_indicator_unit_and_period_only() -> None:
    table = (
        "<table><tr><td>EFRAG ID</td><td>Indicator</td><td>Unit</td>"
        "<td>2025</td><td>2024</td><td>2023¹</td></tr>"
        "<tr><td>E1-5_18</td><td>Energy intensity</td><td>GWh/USDm</td>"
        "<td>2.23</td><td>2.18</td><td>2.28</td></tr></table>"
    )
    graph = build_two_axis_table_graph(table)[0]
    assert graph["indicator_column"] == 1
    assert graph["unit_column"] == 2
    assert graph["period_columns"] == [3, 4, 5]
    assert [cell["row_header"] for cell in graph["cells"]] == [
        "Energy intensity",
        "Energy intensity",
        "Energy intensity",
    ]
    assert [cell["unit"] for cell in graph["cells"]] == ["GWh/USDm"] * 3
    assert [cell["normalized_period"] for cell in graph["cells"]] == [2025, 2024, 2023]


def test_blank_indicator_header_uses_narrative_column_not_efrag_id() -> None:
    table = (
        "<table><tr><td>EFRAG ID S1-06_01</td><td></td>"
        "<td>2025 Headcount</td><td>2024 Headcount</td></tr>"
        "<tr><td>S1-6_01</td><td>Total number of employees</td>"
        "<td>108,065</td><td>108,160</td></tr></table>"
    )
    graph = build_two_axis_table_graph(table)[0]
    assert graph["indicator_column"] == 1
    assert [cell["row_header"] for cell in graph["cells"]] == [
        "Total number of employees",
        "Total number of employees",
    ]


def test_fiscal_year_headers_are_controlled_periods() -> None:
    table = (
        "<table><tr><td>Health and safety</td><td>FY24</td><td>FY25</td></tr>"
        "<tr><td>Fatalities: own workforce</td><td>0</td><td>0</td></tr>"
        "<tr><td>Fatalities: other workers</td><td>1</td><td>2</td></tr></table>"
    )
    graph = build_two_axis_table_graph(table)[0]
    assert graph["period_columns"] == [1, 2]
    assert [cell["normalized_period"] for cell in graph["cells"]] == [
        2024,
        2025,
        2024,
        2025,
    ]


def test_unit_column_cannot_outscore_short_metric_labels() -> None:
    table = (
        "<table><tr><td>WORKFORCE OCCUPATIONAL SAFETY METRICS</td>"
        "<td>Unit</td><td>2025</td><td>2024</td></tr>"
        "<tr><td>Total Recordable Injury Rate (TRIR)</td>"
        "<td>(total recordable injuries/worked hours) x 1,000,000</td>"
        "<td>0.55</td><td>0.70</td></tr>"
        "<tr><td>Near Miss</td><td>(number)</td><td>634</td><td>563</td></tr>"
        "</table>"
    )
    graph = build_two_axis_table_graph(table)[0]
    assert graph["indicator_column"] == 0
    assert graph["unit_column"] == 1
    near_miss = [cell for cell in graph["cells"] if cell["row_header"] == "Near Miss"]
    assert [(cell["normalized_period"], cell["normalized_value"]) for cell in near_miss] == [
        (2025, "634"),
        (2024, "563"),
    ]
    assert {cell["unit"] for cell in near_miss} == {"(number)"}
