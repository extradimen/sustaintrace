import pytest
from jsonschema import Draft202012Validator

from esg_reliable_discovery.p1_v04 import (
    build_line_evidence_handles,
    execute_registered_calculation,
    finalize_v04_output,
    resolve_evidence_handles,
    task_conditioned_schema,
)


def test_handle_resolution_returns_framework_owned_verbatim_text():
    handles = build_line_evidence_handles("DOC", 7, "Alpha  10\nBeta 20")
    resolved = resolve_evidence_handles(["S007-L0002"], handles)
    assert resolved[0]["verbatim_excerpt"] == "Beta 20"
    assert resolved[0]["page"] == 7


def test_unknown_handle_is_hard_failure():
    with pytest.raises(ValueError, match="unknown_evidence_handle"):
        resolve_evidence_handles(["S007-L9999"], [])


def test_calculation_is_grounded_and_framework_executed():
    handles = build_line_evidence_handles("DOC", 7, "Current 91.64\nPrior 94.49")
    result = execute_registered_calculation(
        {
            "operation": "percentage_change",
            "inputs": [
                {"value": 91.64, "evidence_handle": "S007-L0001", "role": "current"},
                {"value": 94.49, "evidence_handle": "S007-L0002", "role": "prior"},
            ],
        },
        handles,
    )
    assert result["result"] == pytest.approx(-3.01619219)
    assert result["model_result_used"] is False


def test_ungrounded_calculation_value_is_rejected():
    handles = build_line_evidence_handles("DOC", 7, "Current 91.64")
    with pytest.raises(ValueError, match="calculation_value_not_grounded"):
        execute_registered_calculation(
            {
                "operation": "sum",
                "inputs": [
                    {"value": 99, "evidence_handle": "S007-L0001", "role": "addend"},
                    {"value": 99, "evidence_handle": "S007-L0001", "role": "addend"},
                ],
            },
            handles,
        )


def test_calculation_schema_is_task_conditioned():
    calculation = task_conditioned_schema("deterministic_calculation")
    direct = task_conditioned_schema("direct_extraction")
    assert "calculation_request" in calculation["required"]
    assert "calculation_request" not in direct["properties"]
    Draft202012Validator.check_schema(calculation)
    Draft202012Validator.check_schema(direct)


def test_dynamic_schema_enumerates_only_available_handles():
    schema = task_conditioned_schema(
        "deterministic_calculation", ["S007-L0001", "S007-L0002"]
    )
    calculation_handle = schema["properties"]["calculation_request"]["properties"][
        "inputs"
    ]["items"]["properties"]["evidence_handle"]
    assert calculation_handle["enum"] == ["S007-L0001", "S007-L0002"]


def test_dynamic_schema_rejects_empty_handle_universe():
    with pytest.raises(ValueError, match="nonempty_and_unique"):
        task_conditioned_schema("direct_extraction", [])


def test_finalize_preserves_model_output_and_resolves_evidence():
    handles = build_line_evidence_handles("DOC", 7, "Current 91.64\nPrior 94.49")
    output = {
        "task_id": "P1-02-1",
        "subject": "Scope 3",
        "scope_boundary": "financial control",
        "period": "2023-2024",
        "calculation_request": {
            "operation": "percentage_change",
            "inputs": [
                {"value": 91.64, "evidence_handle": "S007-L0001", "role": "current"},
                {"value": 94.49, "evidence_handle": "S007-L0002", "role": "prior"},
            ],
        },
    }
    result = finalize_v04_output(output, "deterministic_calculation", handles)
    assert result["model_output"] is output
    assert result["model_output_modified"] is False
    assert result["resolved_evidence"][0]["verbatim_excerpt"] == "Current 91.64"
    assert result["deterministic_calculation"]["result"] == pytest.approx(-3.01619219)
    assert result["deterministic_calculation"]["direction"] == "decrease"


def test_calculation_contract_rejects_model_authored_answer():
    schema = task_conditioned_schema("deterministic_calculation", ["S007-L0001"])
    output = {
        "task_id": "P1-02-1",
        "subject": "Scope 3",
        "scope_boundary": "financial control",
        "period": "2023-2024",
        "calculation_request": None,
        "answer": "model should not own this",
    }
    assert list(Draft202012Validator(schema).iter_errors(output))


def test_percentage_change_uses_roles_not_model_list_order():
    handles = build_line_evidence_handles("DOC", 7, "Current 91.64\nPrior 94.49")
    result = execute_registered_calculation(
        {
            "operation": "percentage_change",
            "inputs": [
                {"value": 94.49, "evidence_handle": "S007-L0002", "role": "prior"},
                {"value": 91.64, "evidence_handle": "S007-L0001", "role": "current"},
            ],
        },
        handles,
    )
    assert result["inputs"] == [91.64, 94.49]
    assert result["result"] == pytest.approx(-3.01619219)


def test_finalize_rejects_monolithic_schema_aliases():
    with pytest.raises(ValueError, match="task_conditioned_schema_failure"):
        finalize_v04_output(
            {"status": "verified_fact", "excerpt": "something"},
            "direct_extraction",
            [],
        )
