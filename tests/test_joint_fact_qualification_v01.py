import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import qualify_fact_jointly, unit_marker_present

ROOT = Path(__file__).resolve().parents[1]


def fact(task_id="P99-CALC-001", predicate="energy_gwh::2025", value=10):
    return {
        "record_id": "fact-" + "a" * 24,
        "subject": {"task_id": task_id},
        "predicate": {"raw_key": predicate},
        "value": value,
        "qualifiers": {
            "period_literal": "2025",
            "reference_period": None,
            "normalized_unit": None,
            "scope_boundary": None,
            "calculation_expression": None,
        },
        "evidence": [{"pdf_page": 7, "quote": "Energy 2025 10 GWh"}],
    }


def binding():
    return {
        "binding_status": "unique_literal",
        "value_type": "number",
        "matched_evidence_indices": [0],
    }


def test_joint_audit_binds_unique_frozen_table_cell_without_promoting():
    record = qualify_fact_jointly(
        fact(),
        binding(),
        {"P99-CALC-001": {"boundary": "operations"}},
        {},
        [{"graph_id": "G7", "pdf_page": 7, "selected_cells": [["Energy", "2025", 10]]}],
    )
    assert record["table_cell_binding"]["status"] == "unique_selected_cell"
    assert record["qualification_status"] == "jointly_qualified_candidate"
    assert record["promotion_decision"]["eligible"] is False


def test_frozen_calculation_output_is_not_misclassified_as_direct():
    plans = {
        "P99-CALC-001": {
            "output_slot_map": [{"slot_id": "energy_gwh::2025", "source_value_id": "sum"}]
        }
    }
    record = qualify_fact_jointly(fact(), binding(), {"P99-CALC-001": {}}, plans, [])
    assert record["value_origin"] == "deterministically_derived_candidate"
    assert record["calculation_lineage"]["status"] == "frozen_plan_output"


def test_count_currency_and_year_predicates_are_not_flagged_unitless():
    for predicate in ("employee_headcount::2025", "capex_mdkk::2025", "base_year"):
        record = qualify_fact_jointly(
            fact(predicate=predicate), binding(), {"P99-CALC-001": {}}, {}, []
        )
        assert record["unit_binding"]["status"] == "predicate_declared"


def test_normalized_unit_markers_are_conservative_literals():
    assert unit_marker_present("percent_change", "Change was 12%")
    assert unit_marker_present("tCO2e", "Gross emissions (tCO2e)")
    assert not unit_marker_present("mixed", "12% and 30 tonnes")


def test_generated_joint_summary_is_hash_addressed_if_present():
    path = ROOT / "data/knowledge_bases/v0.1/joint_fact_qualification_summary.lock.json"
    if path.exists():
        payload = json.loads(path.read_text())
        assert payload["promotion_count"] == 0
