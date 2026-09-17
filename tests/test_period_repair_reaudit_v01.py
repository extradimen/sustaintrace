import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_period_reaudit_never_promotes_directly_if_present():
    path = ROOT / "data/knowledge_bases/v0.1/period_repair_reaudits.jsonl"
    if not path.exists():
        return
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert all(item["promotion_performed"] is False for item in records)
    assert (
        sum(item["qualification_after"] == "jointly_qualified_candidate" for item in records) == 5
    )
