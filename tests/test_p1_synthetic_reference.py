import json
from pathlib import Path

from jsonschema import Draft202012Validator


def test_all_p1_synthetic_references_match_schema():
    schema = json.loads(
        Path("templates/p1_synthetic_reference.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    references = sorted(Path("data/annotations/p1_synthetic").glob("P1-*.json"))
    assert references
    for reference in references:
        instance = json.loads(reference.read_text(encoding="utf-8"))
        assert list(validator.iter_errors(instance)) == [], reference
        assert instance["provenance_attestation"] == {
            "is_human": False,
            "is_ai_simulation": True,
            "candidate_model_excluded": True,
        }


def test_synthetic_task_targets_do_not_use_eligibility_exposure_pages():
    pack = json.loads(
        Path("data/tasks/p1_synthetic_task_pack_v0.1.draft.json").read_text(encoding="utf-8")
    )
    lock = json.loads(
        Path("data/manifests/p1_eligibility_exposure_exclusions.lock.json").read_text(
            encoding="utf-8"
        )
    )
    exclusions = {
        item["candidate_id"]: set(item["excluded_pages"]) for item in lock["documents"]
    }
    for task in pack["tasks"]:
        assert not set(task["target_pages"]) & exclusions[task["candidate_id"]]
