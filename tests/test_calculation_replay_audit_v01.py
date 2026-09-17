from esg_reliable_discovery.knowledge_base import replay_calculation_plan_from_table_cells


def test_frozen_table_cells_replay_percentage_change():
    plan = {
        "candidate_handle_role_map": {
            "M007-T0001-R0001-C0001": "new",
            "M007-T0001-R0001-C0002": "old",
        },
        "steps": [
            {
                "step_id": "change",
                "operation": "percentage_change",
                "inputs": ["new", "old"],
                "rounding_decimals": 2,
            }
        ],
        "output_slot_map": [{"slot_id": "change_percent", "source_value_id": "change"}],
    }
    graphs = [
        {
            "graph_id": "G7",
            "pdf_page": 7,
            "row_axis": ["Energy"],
            "header_axis": ["2025", "2024"],
            "selected_cells": [["Energy", "2025", 90], ["Energy", "2024", 100]],
        }
    ]
    record = replay_calculation_plan_from_table_cells(
        "P99-CALC", plan, graphs, {"change_percent": -10}
    )[0]
    assert record["status"] == "passed"
    assert record["actual"] == -10


def test_missing_selected_cell_fails_closed():
    plan = {
        "candidate_handle_role_map": {"M007-T0001-R0001-C0001": "value"},
        "steps": [],
        "output_slot_map": [{"slot_id": "out", "source_value_id": "value"}],
    }
    record = replay_calculation_plan_from_table_cells("P99", plan, [], {"out": 1})[0]
    assert record["status"] == "unreplayable_missing_cell"


def test_role_label_fallback_handles_full_table_row_offsets():
    plan = {
        "candidate_handle_role_map": {
            "M007-T0001-R0010-C0001": "total_2025",
            "M007-T0001-R0010-C0002": "total_2024",
        },
        "steps": [
            {
                "step_id": "change",
                "operation": "percentage_change",
                "inputs": ["total_2025", "total_2024"],
                "rounding_decimals": 2,
            }
        ],
        "output_slot_map": [{"slot_id": "change", "source_value_id": "change"}],
    }
    graph = {
        "graph_id": "G7",
        "pdf_page": 7,
        "row_axis": ["total energy"],
        "header_axis": ["2025", "2024"],
        "selected_cells": [["total energy", "2025", 90], ["total energy", "2024", 100]],
    }
    result = replay_calculation_plan_from_table_cells(
        "P99-ENERGY-CALC", plan, [graph], {"change": -10}
    )[0]
    assert result["status"] == "passed"
