import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[1]


def test_gemma_registration_and_qualification_plan_validate():
    registration_schema = json.loads(
        (ROOT / "templates/model_registration.schema.json").read_text(encoding="utf-8")
    )
    registration = json.loads(
        (ROOT / "model_manifests/gemma4-12b.registration.json").read_text(encoding="utf-8")
    )
    plan_schema = json.loads(
        (ROOT / "templates/model_qualification_plan.schema.json").read_text(encoding="utf-8")
    )
    plan = json.loads(
        (ROOT / "configs/experiments/p0-model-qualification-v0.1.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(registration_schema)
    Draft202012Validator.check_schema(plan_schema)
    Draft202012Validator(registration_schema).validate(registration)
    Draft202012Validator(plan_schema).validate(plan)
    assert registration["registration_status"] == "locked"
    assert registration["qualification_results_observed"] is True
    assert registration["observed_local_artifact"]["resolved_digest"] == (
        "4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c"
    )
    assert plan["selection_rule"]["aggregate_score"] is None
    assert plan["repetitions_per_task"] >= 5
    assert len({task["task_id"] for task in plan["tasks"]}) == 7
