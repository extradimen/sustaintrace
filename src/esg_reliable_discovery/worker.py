from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def command_digest(argv: list[str]) -> str:
    encoded = json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_queue(queue: dict[str, Any]) -> None:
    if queue.get("schema_version") != "0.1":
        raise ValueError("unsupported worker queue schema")
    seen: set[str] = set()
    for task in queue.get("tasks", []):
        task_id = task.get("task_id")
        argv = task.get("argv")
        if not task_id or task_id in seen:
            raise ValueError(f"missing or duplicate task_id: {task_id}")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise ValueError(f"invalid argv for task: {task_id}")
        if task.get("mode", "deterministic") != "deterministic":
            raise ValueError(f"worker only accepts deterministic tasks: {task_id}")
        seen.add(task_id)


class KnowledgeWorker:
    def __init__(
        self,
        root: Path,
        queue_path: Path,
        state_path: Path,
        lock_path: Path,
        stop_path: Path,
    ) -> None:
        self.root = root.resolve()
        self.queue_path = queue_path
        self.state_path = state_path
        self.lock_path = lock_path
        self.stop_path = stop_path
        self.lock_handle: Any | None = None

    def acquire_lock(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_handle = self.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self.lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another knowledge worker already holds the lock") from exc
        self.lock_handle.seek(0)
        self.lock_handle.truncate()
        self.lock_handle.write(f"pid={os.getpid()} started_at={utc_now()}\n")
        self.lock_handle.flush()

    def load_queue(self) -> dict[str, Any]:
        queue = json.loads(self.queue_path.read_text(encoding="utf-8"))
        validate_queue(queue)
        return queue

    def load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "schema_version": "0.1",
            "worker_status": "starting",
            "pid": os.getpid(),
            "updated_at": utc_now(),
            "tasks": {},
        }

    def outputs_valid(self, task: dict[str, Any], record: dict[str, Any]) -> bool:
        recorded = record.get("output_sha256", {})
        for relative in task.get("expected_outputs", []):
            path = self.root / relative
            if not path.is_file() or recorded.get(relative) != sha256_file(path):
                return False
        return True

    def command_allowed(self, argv: list[str]) -> bool:
        executable = Path(argv[0]).name
        return executable.startswith("python") or executable in {"pytest", "ruff"}

    def execute_task(self, task: dict[str, Any], state: dict[str, Any]) -> None:
        task_id = task["task_id"]
        argv = task["argv"]
        digest = command_digest(argv)
        previous = state["tasks"].get(task_id, {})
        if previous.get("status") == "complete":
            if previous.get("command_sha256") != digest or not self.outputs_valid(task, previous):
                raise RuntimeError(f"completed task checkpoint mismatch: {task_id}")
            return
        if not self.command_allowed(argv):
            raise ValueError(f"disallowed worker executable: {argv[0]}")
        attempts = int(previous.get("attempts", 0)) + 1
        log_path = (
            self.root / "artifacts/knowledge_worker/logs" / f"{task_id}.attempt-{attempts}.log"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "status": "running",
            "attempts": attempts,
            "command_sha256": digest,
            "argv": argv,
            "started_at": utc_now(),
            "log_path": log_path.relative_to(self.root).as_posix(),
        }
        state["tasks"][task_id] = record
        state.update(worker_status="running", current_task=task_id, updated_at=utc_now())
        atomic_write_json(self.state_path, state)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(self.root / "src")
        with log_path.open("wb") as log:
            completed = subprocess.run(
                argv,
                cwd=self.root,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        record["exit_code"] = completed.returncode
        record["finished_at"] = utc_now()
        if completed.returncode != 0:
            record["status"] = "failed"
            state.update(worker_status="failed", current_task=task_id, updated_at=utc_now())
            atomic_write_json(self.state_path, state)
            raise RuntimeError(f"worker task failed: {task_id}; see {log_path}")
        output_hashes = {}
        for relative in task.get("expected_outputs", []):
            path = self.root / relative
            if not path.is_file():
                raise RuntimeError(f"expected output missing after task {task_id}: {relative}")
            output_hashes[relative] = sha256_file(path)
        record.update(status="complete", output_sha256=output_hashes)
        state.pop("current_task", None)
        state.update(worker_status="idle", updated_at=utc_now())
        atomic_write_json(self.state_path, state)

    def process_once(self) -> int:
        queue = self.load_queue()
        state = self.load_state()
        state["pid"] = os.getpid()
        state["queue_sha256"] = sha256_file(self.queue_path)
        completed_before = sum(item.get("status") == "complete" for item in state["tasks"].values())
        for task in queue.get("tasks", []):
            self.execute_task(task, state)
        completed_after = sum(item.get("status") == "complete" for item in state["tasks"].values())
        state.update(worker_status="idle", updated_at=utc_now())
        atomic_write_json(self.state_path, state)
        return completed_after - completed_before

    def run(self, poll_seconds: float) -> None:
        self.acquire_lock()
        while not self.stop_path.exists():
            completed = self.process_once()
            if completed == 0:
                state = self.load_state()
                state.update(worker_status="idle", updated_at=utc_now(), pid=os.getpid())
                atomic_write_json(self.state_path, state)
            time.sleep(poll_seconds)
        state = self.load_state()
        state.update(worker_status="stopped", updated_at=utc_now())
        atomic_write_json(self.state_path, state)
