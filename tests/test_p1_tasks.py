import json

import pytest

from esg_reliable_discovery.p1_tasks import P1TaskAllocationError, allocate_p1_task_slots


def _sample():
    return {
        "status": "frozen",
        "selected": [
            {"candidate_id": f"C{i:02d}", "document_id": f"D{i:02d}"}
            for i in range(12)
        ],
    }


def test_allocation_matches_quotas_and_has_distinct_pairs(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(_sample()), encoding="utf-8")
    quotas = {"direct": 6, "calc": 4, "cross": 4, "scope": 4, "conflict": 3, "abstain": 3}
    result = allocate_p1_task_slots(path, quotas, seed=17)
    assert result["quota_check"] == dict(sorted(quotas.items()))
    assert result["task_count"] == 24
    for index in range(0, 24, 2):
        assert result["slots"][index]["task_type"] != result["slots"][index + 1]["task_type"]
    assert all(not slot["model_access_allowed"] for slot in result["slots"])


def test_allocation_rejects_bad_quota_total(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(_sample()), encoding="utf-8")
    with pytest.raises(P1TaskAllocationError, match="sum to 24"):
        allocate_p1_task_slots(path, {"direct": 23}, seed=17)
