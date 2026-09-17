import json
from pathlib import Path

from esg_reliable_discovery.hashing import sha256_file

ROOT = Path(__file__).parents[1]


def test_prompt_lock_matches_artifacts_and_does_not_claim_task_freeze():
    lock = json.loads(
        (ROOT / "prompts/p0_evidence_discovery_v0.1.lock.json").read_text(encoding="utf-8")
    )
    assert lock["prompt_locked"] is True
    assert lock["task_pack_frozen"] is False
    assert lock["leakage_audit"]["passed"] is True
    for artifact in lock["artifacts"].values():
        assert sha256_file(ROOT / artifact["path"]) == artifact["sha256"]
