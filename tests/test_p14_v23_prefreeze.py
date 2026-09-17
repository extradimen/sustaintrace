import json
from pathlib import Path

from esg_reliable_discovery.v23_preflight import (
    execute_calculation_plan_v23,
    validate_reference_direction_literals_v23,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(relative_path: str):
    return json.loads((ROOT / relative_path).read_text())


def test_p14_reference_keys_match_frozen_slot_contracts():
    contracts = _load("configs/framework/p14_slot_contracts_v0.1.lock.json")[
        "contracts"
    ]
    reference_dir = ROOT / "data/annotations/p14_simulated"
    for path in sorted(reference_dir.glob("*.json")):
        reference = json.loads(path.read_text())
        task_id = reference["task_id"]
        reference_keys = set(reference["normalized_value"])
        contract_keys = {item["slot_id"] for item in contracts[task_id]}
        assert reference_keys == contract_keys, task_id


def test_p14_target_and_slb_direction_literals_pass_v23_gate():
    contracts = _load("configs/framework/p14_slot_contracts_v0.1.lock.json")[
        "contracts"
    ]
    target_reference = _load(
        "data/annotations/p14_simulated/P14-TARGET-001.json"
    )["normalized_value"]
    slb_reference = _load("data/annotations/p14_simulated/P14-SLB-001.json")[
        "normalized_value"
    ]
    target_bindings = [
        {
            "slot_id": "scope_1_2_2030_reduction_percent",
            "reference_value": target_reference[
                "scope_1_2_2030_reduction_percent"
            ],
            "source_literal": "reduce ... by 57% compared to 2019",
        },
        {
            "slot_id": "scope_3_2030_reduction_percent",
            "reference_value": target_reference["scope_3_2030_reduction_percent"],
            "source_literal": "reduce ... by 28% compared to 2019",
        },
        {
            "slot_id": "overall_2050_reduction_percent",
            "reference_value": target_reference["overall_2050_reduction_percent"],
            "source_literal": "reduce overall emissions by 90%",
        },
    ]
    slb_bindings = [
        {
            "slot_id": "kpi_1b_target_reduction_percent",
            "reference_value": slb_reference["kpi_1b_target_reduction_percent"],
            "source_literal": "will be reduced by 14% per product sold",
        },
        {
            "slot_id": "kpi_1b_published_reduction_percent",
            "reference_value": slb_reference[
                "kpi_1b_published_reduction_percent"
            ],
            "source_literal": "published -5%",
        },
        {
            "slot_id": "kpi_1b_comparable_reduction_percent",
            "reference_value": slb_reference[
                "kpi_1b_comparable_reduction_percent"
            ],
            "source_literal": "comparable -10%",
        },
    ]
    assert (
        validate_reference_direction_literals_v23(
            contracts["P14-TARGET-001"], target_bindings
        )["status"]
        == "passed"
    )
    assert (
        validate_reference_direction_literals_v23(
            contracts["P14-SLB-001"], slb_bindings
        )["status"]
        == "passed"
    )


def test_p14_ghg_calculation_is_framework_owned_and_reconciles_exactly():
    plan = _load("configs/framework/p14_calculation_plans_v0.1.lock.json")[
        "plans"
    ]["P14-GHG-CALC-001"]
    evidence = [
        {"handle": "P213-S1", "verbatim_text": "2025 Scope 1 42,428"},
        {"handle": "P213-S2M", "verbatim_text": "2025 market-based 24,206"},
        {"handle": "P213-S3", "verbatim_text": "2025 Scope 3 6,355,052"},
        {
            "handle": "P213-TOTAL-M",
            "verbatim_text": "2025 market-based total 6,421,686",
        },
    ]
    observations = {
        "scope_1": (42428, "P213-S1"),
        "market_scope_2": (24206, "P213-S2M"),
        "scope_3": (6355052, "P213-S3"),
        "reported_total": (6421686, "P213-TOTAL-M"),
    }
    output = {
        "observations": {
            role: {
                "value": value,
                "evidence_handle": handle,
                "period_year": 2025,
                "unit": "tCO2e",
            }
            for role, (value, handle) in observations.items()
        }
    }
    result = execute_calculation_plan_v23(output, evidence, plan)
    assert result["framework_owned_operation"] is True
    assert result["candidate_selected_operation"] is False
    assert result["values"]["calculated_total"] == 6421686
    assert result["values"]["difference"] == 0


def test_p14_table_graph_contains_required_page_row_column_cell_coordinates():
    graph = _load(
        "configs/framework/p14_two_dimensional_table_graph_v0.1.lock.json"
    )
    pages = {table["pdf_page"] for table in graph["tables"]}
    assert {213, 229, 248, 282, 288}.issubset(pages)
    for table in graph["tables"]:
        assert table["table_id"]
        assert len(table["columns"]) >= 2
        assert table["rows"]
        assert all(len(row) == len(table["columns"]) for row in table["rows"])
