from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.run_workbench import (
    AlreadyRunningError,
    Component,
    RuntimeLock,
    WorkbenchSupervisor,
    _atomic_json,
    _pid_alive,
    _probe_http,
)


def test_atomic_json_replaces_complete_document(tmp_path: Path) -> None:
    target = tmp_path / "runtime/state.json"
    _atomic_json(target, {"status": "running", "count": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "status": "running",
        "count": 1,
    }
    assert not target.with_suffix(".json.tmp").exists()


def test_runtime_lock_rejects_live_duplicate(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    lock_path = tmp_path / "supervisor.lock.json"
    lock_path.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    lock = RuntimeLock(lock_path, events)
    with pytest.raises(AlreadyRunningError):
        lock.acquire()


def test_runtime_lock_recovers_stale_lock_with_audit_event(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    lock_path = tmp_path / "supervisor.lock.json"
    lock_path.write_text(json.dumps({"pid": 999_999_999}), encoding="utf-8")
    lock = RuntimeLock(lock_path, events)
    lock.acquire()
    assert json.loads(lock_path.read_text(encoding="utf-8"))["pid"] == os.getpid()
    event = json.loads(events.read_text(encoding="utf-8"))
    assert event["event"] == "stale_runtime_lock_recovered"
    assert event["stale_pid"] == 999_999_999
    lock.release()
    assert not lock_path.exists()


def test_restart_budget_is_bounded_per_component(tmp_path: Path) -> None:
    supervisor = WorkbenchSupervisor(
        tmp_path,
        8787,
        5173,
        max_restarts=2,
        restart_window_seconds=10,
    )
    component = Component("test", ["true"], tmp_path)
    assert supervisor._restart_allowed(component, 100)
    component.restart_times.extend([91, 99])
    assert not supervisor._restart_allowed(component, 100)
    assert supervisor._restart_allowed(component, 102)


def test_pid_alive_handles_current_and_invalid_pid() -> None:
    assert _pid_alive(os.getpid())
    assert not _pid_alive(-1)


class _FakeProcess:
    pid = 12345

    def __init__(self) -> None:
        self.terminated = False

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True


def test_health_probe_failure_requests_restart_after_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    supervisor = WorkbenchSupervisor(
        tmp_path,
        8787,
        5173,
        health_interval_seconds=0,
        health_failure_threshold=3,
    )
    process = _FakeProcess()
    component = Component(
        "test",
        ["true"],
        tmp_path,
        process=process,  # type: ignore[arg-type]
        health_url="http://localhost:1/health",
    )
    monkeypatch.setattr(
        "scripts.run_workbench._probe_http",
        lambda _url, _timeout: (False, "connection refused"),
    )
    for tick in (1.0, 2.0, 3.0):
        supervisor._check_component_health(component, tick)
    assert component.consecutive_health_failures == 3
    assert component.pending_restart_reason == "health_probe_failure"
    assert process.terminated
    events = [
        json.loads(line)
        for line in supervisor.events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["event"] == "component_unhealthy_restart_requested"


def test_successful_health_probe_clears_transient_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    supervisor = WorkbenchSupervisor(
        tmp_path,
        8787,
        5173,
        health_interval_seconds=0,
    )
    component = Component(
        "test",
        ["true"],
        tmp_path,
        process=_FakeProcess(),  # type: ignore[arg-type]
        health_url="http://localhost:1/health",
        consecutive_health_failures=1,
    )
    monkeypatch.setattr(
        "scripts.run_workbench._probe_http",
        lambda _url, _timeout: (True, None),
    )
    supervisor._check_component_health(component, 1.0)
    assert component.consecutive_health_failures == 0
    assert component.last_health_ok_at is not None
    assert component.last_health_error is None


def test_http_probe_rejects_unreachable_endpoint() -> None:
    healthy, detail = _probe_http("http://127.0.0.1:1/", 0.1)
    assert healthy is False
    assert detail
