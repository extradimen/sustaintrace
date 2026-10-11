import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation/rq1_human_fidelity"


def load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_human_gold_is_complete_and_adjudicated():
    gold = load("SustainTrace_Human_Validation_Gold_v1.0.lock.json")
    assert gold["status"] == "human_gold_locked"
    assert gold["inventory"] == {
        "reports": 20,
        "tasks": 60,
        "task_level_adjudications": 49,
        "slot_adjudications": 134,
        "invalid_tasks": 0,
    }
    assert len(gold["tasks"]) == 60
    assert len({task["task_id"] for task in gold["tasks"]}) == 60
    assert all(task["valid"] for task in gold["tasks"])
    assert all(
        set(task["final_slots"].values()) <= {"Y", "N", "NA"} and len(task["final_slots"]) == 7
        for task in gold["tasks"]
    )


def test_metrics_match_protocol_inventory_and_are_bounded():
    metrics = load("SustainTrace_Human_Validation_Metrics_v1.0.lock.json")
    assert metrics["inventory"]["tasks"] == 60
    assert metrics["rq1_knowledge_fidelity"]["candidate_tasks"] == 40
    assert metrics["rq2_reliability_control"]["promoted_tier_b_candidates"] == 3
    assert metrics["rq2_reliability_control"]["held_tier_c_candidates"] == 37
    assert metrics["rq3_controlled_repair"]["executions"] == 4
    for section in ["rq1_knowledge_fidelity", "rq2_reliability_control"]:
        for value in metrics[section].values():
            if isinstance(value, dict) and "estimate" in value and value["estimate"] is not None:
                assert 0 <= value["estimate"] <= 1


def test_task_csv_and_hash_manifest_are_consistent():
    csv_path = RESULTS / "SustainTrace_Human_Validation_Task_Results_v1.0.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 60
    assert len({row["task_id"] for row in rows}) == 60

    expected = {}
    for line in (RESULTS / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    assert expected
    for name, digest in expected.items():
        assert sha256(RESULTS / name) == digest
