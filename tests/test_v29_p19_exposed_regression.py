import inspect
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from esg_reliable_discovery.p1_v07 import task_conditioned_schema_v07
from esg_reliable_discovery.v13_stage_a_runner import run_v13_stage_a_task
from esg_reliable_discovery.v23_preflight import calculation_binding_schema_v23
from esg_reliable_discovery.v29_integrity import (
    bind_exact_task_id_schema_v29,
    calculation_payload_v29,
    execute_calculation_plan_v29,
    validate_candidate_preflight_v29,
)

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_v29_rejects_p19_missing_workforce_plan_before_any_candidate_call():
    pack = load("data/tasks/p19_local_execution_task_pack_v0.1.lock.json")
    plans = load("configs/framework/p19_calculation_plans_v0.1.lock.json")
    with pytest.raises(ValueError, match="v29_calculation_plans_missing.*WORKFORCE"):
        validate_candidate_preflight_v29(pack["tasks"], plans)


def test_v29_preflight_accepts_complete_supported_plan_registry():
    pack = load("data/tasks/p19_local_execution_task_pack_v0.1.lock.json")
    plans = load("configs/framework/p19_calculation_plans_v0.1.lock.json")
    complete = deepcopy(plans)
    complete["plans"]["P19-WORKFORCE-001"] = {
        "roles": [
            {"role_id": "permanent_2025", "unit": "employees"},
            {"role_id": "temporary_2025", "unit": "employees"},
        ],
        "steps": [
            {
                "step_id": "recomputed_2025",
                "operation": "sum",
                "inputs": ["permanent_2025", "temporary_2025"],
            }
        ],
    }
    audit = validate_candidate_preflight_v29(pack["tasks"], complete)
    assert audit["status"] == "passed"
    assert audit["validated_before_candidate_call"] is True
    assert audit["deterministic_task_count"] == 3


@pytest.mark.parametrize(
    "task_type", ["direct_extraction_and_relation", "deterministic_calculation"]
)
def test_v29_request_schema_requires_the_exact_frozen_task_id(task_type):
    if task_type == "deterministic_calculation":
        base = calculation_binding_schema_v23(
            ["H1"], {"roles": [{"role_id": "reported", "unit": "t"}]}
        )
    else:
        base = task_conditioned_schema_v07(task_type, ["H1"])
    schema = bind_exact_task_id_schema_v29(base, "P20-ENERGY-001")
    assert schema["properties"]["task_id"]["const"] == "P20-ENERGY-001"
    assert "task_id" in schema["required"]
    errors = list(Draft202012Validator(schema).iter_errors({}))
    assert any("task_id" in error.message for error in errors)


def test_v29_calculation_envelope_preserves_original_and_only_routes_identity():
    original = {"task_id": "P20-CALC-001", "observations": {"x": {"value": 1}}}
    payload = calculation_payload_v29(original, "P20-CALC-001")
    assert "task_id" not in payload
    assert original["task_id"] == "P20-CALC-001"
    with pytest.raises(ValueError, match="v29_calculation_task_id_mismatch"):
        calculation_payload_v29(original, "P20-CALC-002")


def test_v29_executes_percentage_change_and_share_deterministically():
    evidence = [
        {"handle": "H1", "verbatim_text": "2025 value 120"},
        {"handle": "H2", "verbatim_text": "2024 value 100"},
        {"handle": "H3", "verbatim_text": "category value 30"},
    ]
    plan = {
        "roles": [
            {"role_id": "new", "unit": "t"},
            {"role_id": "old", "unit": "t"},
            {"role_id": "part", "unit": "t"},
        ],
        "steps": [
            {
                "step_id": "change",
                "operation": "percentage_change",
                "inputs": ["new", "old"],
                "rounding_decimals": 2,
            },
            {
                "step_id": "share",
                "operation": "percentage_share",
                "inputs": ["part", "new"],
                "rounding_decimals": 2,
            },
        ],
    }
    output = {
        "observations": {
            "new": {"value": 120, "evidence_handle": "H1", "period_year": 2025, "unit": "t"},
            "old": {"value": 100, "evidence_handle": "H2", "period_year": 2024, "unit": "t"},
            "part": {"value": 30, "evidence_handle": "H3", "period_year": 2025, "unit": "t"},
        }
    }
    result = execute_calculation_plan_v29(output, evidence, plan)
    assert result["values"]["change"] == 20.0
    assert result["values"]["share"] == 25.0
    assert result["candidate_selected_operation"] is False


def test_v29_options_are_wired_into_reusable_stage_a_runner():
    parameters = inspect.signature(run_v13_stage_a_task).parameters
    assert "use_v29_task_id_schema" in parameters
    assert "use_v29_calculation_executor" in parameters
