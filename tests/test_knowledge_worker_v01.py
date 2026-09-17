import json
import sys
from pathlib import Path

import pytest

from esg_reliable_discovery.worker import KnowledgeWorker, validate_queue


def test_queue_rejects_duplicate_task_ids():
    with pytest.raises(ValueError, match="duplicate"):
        validate_queue(
            {
                "schema_version": "0.1",
                "tasks": [
                    {"task_id": "same", "argv": ["python3", "-V"]},
                    {"task_id": "same", "argv": ["python3", "-V"]},
                ],
            }
        )


def test_worker_checkpoints_and_does_not_repeat(tmp_path: Path):
    queue_path = tmp_path / "queue.json"
    output_path = tmp_path / "result.txt"
    queue_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "tasks": [
                    {
                        "task_id": "write-once",
                        "mode": "deterministic",
                        "argv": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; Path('result.txt').write_text('ok')",
                        ],
                        "expected_outputs": ["result.txt"],
                    }
                ],
            }
        )
    )
    worker = KnowledgeWorker(
        root=tmp_path,
        queue_path=queue_path,
        state_path=tmp_path / "state.json",
        lock_path=tmp_path / "worker.lock",
        stop_path=tmp_path / "STOP",
    )
    assert worker.process_once() == 1
    first_mtime = output_path.stat().st_mtime_ns
    assert worker.process_once() == 0
    assert output_path.stat().st_mtime_ns == first_mtime
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["tasks"]["write-once"]["attempts"] == 1
    assert state["tasks"]["write-once"]["status"] == "complete"


def test_completed_output_hash_mismatch_fails_closed(tmp_path: Path):
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "tasks": [
                    {
                        "task_id": "hash-guard",
                        "argv": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; Path('result.txt').write_text('ok')",
                        ],
                        "expected_outputs": ["result.txt"],
                    }
                ],
            }
        )
    )
    worker = KnowledgeWorker(
        root=tmp_path,
        queue_path=queue_path,
        state_path=tmp_path / "state.json",
        lock_path=tmp_path / "worker.lock",
        stop_path=tmp_path / "STOP",
    )
    worker.process_once()
    (tmp_path / "result.txt").write_text("tampered")
    with pytest.raises(RuntimeError, match="checkpoint mismatch"):
        worker.process_once()
