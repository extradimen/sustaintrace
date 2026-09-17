import json

from esg_reliable_discovery.p1_task_gate import audit_p1_task_exposure


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_exposure_audit_rejects_viewed_page(tmp_path):
    pack = {"slots": [
        {
            "task_id": f"P1-{index:02d}-1",
            "candidate_id": "C1",
            "question_status": "frozen",
            "question": "A sufficiently detailed human-authored question?",
            "target_pages": [7 if index == 1 else 8],
        }
        for index in range(1, 25)
    ]}
    exclusions = {"documents": [{"candidate_id": "C1", "excluded_pages": [7]}]}
    pack_path = tmp_path / "pack.json"
    exclusion_path = tmp_path / "exclusions.json"
    _write(pack_path, pack)
    _write(exclusion_path, exclusions)
    result = audit_p1_task_exposure(pack_path, exclusion_path)
    assert result["passed"] is False
    assert result["exposure_violations"] == [
        {"task_id": "P1-01-1", "excluded_pages_used": [7]}
    ]


def test_exposure_audit_accepts_complete_nonoverlapping_pack(tmp_path):
    pack = {"slots": [
        {
            "task_id": f"P1-{index:02d}-1",
            "candidate_id": "C1",
            "question_status": "frozen",
            "question": "A sufficiently detailed human-authored question?",
            "target_pages": [8],
        }
        for index in range(1, 25)
    ]}
    exclusions = {"documents": [{"candidate_id": "C1", "excluded_pages": [7]}]}
    pack_path = tmp_path / "pack.json"
    exclusion_path = tmp_path / "exclusions.json"
    _write(pack_path, pack)
    _write(exclusion_path, exclusions)
    assert audit_p1_task_exposure(pack_path, exclusion_path)["passed"] is True
