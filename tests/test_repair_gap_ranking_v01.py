import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repair_ranking_never_marks_semantic_boundary_automatic_if_present():
    path = ROOT / "data/knowledge_bases/v0.1/repair_gap_rankings.jsonl"
    if not path.exists():
        return
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert [item["rank"] for item in records] == list(range(1, len(records) + 1))
    boundary = next(
        item for item in records if item["gap_signature"] == "BOUNDARY_ATTACHMENT_INCOMPLETE"
    )
    assert boundary["execution_decision"] == "blocked"
