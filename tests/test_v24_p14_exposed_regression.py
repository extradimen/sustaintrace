import pytest

from esg_reliable_discovery.v23_preflight import execute_calculation_plan_v23
from esg_reliable_discovery.v24_integrity import (
    dry_run_stage_b_contracts_v24,
    normalize_calculation_binding_v24,
    validate_layout_registry_v24,
)


def test_p14_legacy_calculation_request_lowers_to_observations_only():
    plan = {
        "roles": [
            {"role_id": "scope_1", "unit": "tCO2e"},
            {"role_id": "market_scope_2", "unit": "tCO2e"},
            {"role_id": "scope_3", "unit": "tCO2e"},
            {"role_id": "reported_total", "unit": "tCO2e"},
        ],
        "steps": [
            {
                "step_id": "calculated_total",
                "operation": "sum",
                "inputs": ["scope_1", "market_scope_2", "scope_3"],
            },
            {
                "step_id": "difference",
                "operation": "difference",
                "inputs": ["calculated_total", "reported_total"],
            },
        ],
    }
    request = {
        "calculation_request": {
            "operation": "sum_and_compare",
            "unit": "tCO₂eq",
            "inputs": [
                {
                    "metric": "Scope 1 GHG emissions",
                    "value": 42428,
                    "evidence_handle": "E1",
                    "period_year": 2025,
                },
                {
                    "metric": "Market-based Scope 2 GHG emissions",
                    "value": 24206,
                    "evidence_handle": "E2",
                    "period_year": 2025,
                },
                {
                    "metric": "Total Scope 3 GHG emissions",
                    "value": 6355052,
                    "evidence_handle": "E3",
                    "period_year": 2025,
                },
            ],
            "comparison_value": {
                "metric": "Total GHG emissions",
                "value": 6421686,
                "evidence_handle": "E4",
                "period_year": 2025,
            },
            "calculated_sum": 999,
            "difference": 999,
        }
    }
    normalized, audit = normalize_calculation_binding_v24(request, plan)
    evidence = [
        {"handle": "E1", "verbatim_text": "Scope 1 42,428"},
        {"handle": "E2", "verbatim_text": "Scope 2 24,206"},
        {"handle": "E3", "verbatim_text": "Scope 3 6,355,052"},
        {"handle": "E4", "verbatim_text": "Total 6,421,686"},
    ]
    result = execute_calculation_plan_v23(normalized, evidence, plan)
    assert result["values"]["calculated_total"] == 6421686
    assert result["values"]["difference"] == 0
    assert audit["candidate_operation_fields_ignored"] == [
        "operation",
        "calculated_sum",
        "difference",
    ]


@pytest.mark.parametrize(
    "required_terms",
    [
        ["earlier periods", "ESG KPIs"],
        ["sustainability information", "Article 8"],
    ],
)
def test_p14_ordered_span_preflight_covers_required_value_terms(required_terms):
    result = dry_run_stage_b_contracts_v24(
        [
            {
                "slot_id": "subject",
                "predicate_id": "esg_assurance::subject",
                "value_type": "string",
                "string_input_shape": "ordered_span",
                "required_value_terms": required_terms,
            }
        ]
    )
    assert result["status"] == "passed"
    assert result["required_value_terms_in_fixture"] is True


def test_compact_layout_registry_is_rejected_before_candidate():
    with pytest.raises(ValueError, match="v24_layout_registry_compact_task_ids"):
        validate_layout_registry_v24([{"task_ids": ["A"], "pdf_page": 1}])


def test_expanded_layout_registry_passes():
    result = validate_layout_registry_v24(
        [
            {"task_id": "A", "pdf_page": 1},
            {"task_id": "A", "pdf_page": 2},
            {"task_id": "B", "pdf_page": 1},
        ]
    )
    assert result["status"] == "passed"
    assert result["record_count"] == 3
