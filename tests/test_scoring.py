import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.scoring import score_finding_card

ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "templates/finding_card.schema.json").read_text(encoding="utf-8"))
GOLD_FILES = sorted((ROOT / "data/annotations/p0_gold").glob("*.json"))


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_closed_task_gold_cards_validate_and_self_score():
    assert len(GOLD_FILES) == 6
    for path in GOLD_FILES:
        gold = _load(path)
        Draft202012Validator(SCHEMA).validate(gold)
        result = score_finding_card(gold, gold, SCHEMA)
        assert result["aggregate_score"] is None
        assert all(value == 1 for value in result["dimensions"].values() if value is not None)


def test_wrong_evidence_page_is_isolated_from_answer_score():
    gold = _load(ROOT / "data/annotations/p0_gold/P0-TEXT-001.json")
    candidate = copy.deepcopy(gold)
    candidate["supporting_evidence"][0]["page"] = 17

    result = score_finding_card(candidate, gold, SCHEMA)

    assert result["dimensions"]["answer_correctness"] == 1
    assert result["dimensions"]["evidence_accuracy"] == 0


def test_wrong_calculation_is_detected():
    gold = _load(ROOT / "data/annotations/p0_gold/P0-CALC-001.json")
    candidate = copy.deepcopy(gold)
    candidate["calculation"]["result"] = -5

    result = score_finding_card(candidate, gold, SCHEMA)

    assert result["dimensions"]["calculation_accuracy"] == 0


def test_failed_abstention_is_detected():
    gold = _load(ROOT / "data/annotations/p0_gold/P0-ABSTAIN-001.json")
    candidate = copy.deepcopy(gold)
    candidate["status"] = "contradicted"

    result = score_finding_card(candidate, gold, SCHEMA)

    assert result["dimensions"]["abstention_accuracy"] == 0


def test_closed_gold_lock_matches_artifacts():
    lock = _load(ROOT / "data/annotations/p0_closed_gold.lock.json")
    assert lock["closed_tasks_locked"] is True
    assert lock["open_discovery_locked"] is False
    assert lock["scorer_sha256"] == sha256_file(ROOT / "src/esg_reliable_discovery/scoring.py")
    for card in lock["cards"]:
        assert card["sha256"] == sha256_file(ROOT / card["path"])
