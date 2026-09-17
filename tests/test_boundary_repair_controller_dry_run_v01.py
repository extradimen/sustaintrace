import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def test_only_class_validated_boundary_plans_become_supervised_candidates():
    records = [
        json.loads(line)
        for line in (KB / "boundary_repair_controller_dry_run.jsonl").read_text().splitlines()
        if line
    ]
    assert len(records) == 28
    assert sum(r["decision"] == "supervised_candidate" for r in records) == 26
    assert sum(r["decision"] == "blocked_missing_class_validator" for r in records) == 0
    assert sum(r["decision"] == "blocked_validation_missing_or_failed" for r in records) == 2
    assert all(r["execution_performed"] is False for r in records)
    assert all(r["promotion_performed"] is False for r in records)
