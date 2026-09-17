import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[1]


def test_p0_task_pack_schema_and_references():
    schema = json.loads((ROOT / "templates/task_manifest.schema.json").read_text(encoding="utf-8"))
    pack = json.loads((ROOT / "data/tasks/p0_task_pack_v0.1.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(pack)

    lock = json.loads((ROOT / "data/manifests/p0_manifest.lock.json").read_text(encoding="utf-8"))
    locked = {document["document_id"]: document["sha256"] for document in lock["documents"]}
    task_ids = [task["task_id"] for task in pack["tasks"]]
    assert len(task_ids) == len(set(task_ids))
    for task in pack["tasks"]:
        assert task["expected_card_count"]["minimum"] <= task["expected_card_count"]["maximum"]
        for source in task["source_documents"]:
            assert locked[source["document_id"]] == source["sha256"]


def test_controlled_intervention_is_explicitly_synthetic():
    intervention = json.loads(
        (ROOT / "data/controlled_interventions/P0-CI-001.json").read_text(encoding="utf-8")
    )
    assert intervention["known_source_value"] != 55
    assert intervention["expected_relation"] == "contradicted_by_source"
    assert "not a company statement" in intervention["construction_note"]
