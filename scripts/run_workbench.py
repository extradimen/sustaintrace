from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _append_event(path: Path, event: str, **details: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"time": _now(), "event": event, **details}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _probe_http(url: str, timeout_seconds: float) -> tuple[bool, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
            status = int(response.status)
            if 200 <= status < 400:
                return True, None
            return False, f"HTTP {status}"
    except (OSError, urllib.error.URLError, ValueError) as error:
        return False, f"{type(error).__name__}: {error}"


class AlreadyRunningError(RuntimeError):
    pass


class RuntimeLock:
    def __init__(self, path: Path, events_path: Path) -> None:
        self.path = path
        self.events_path = events_path
        self.acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                existing = json.loads(self.path.read_text(encoding="utf-8"))
                existing_pid = int(existing.get("pid", 0))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                existing_pid = 0
            if _pid_alive(existing_pid):
                raise AlreadyRunningError(
                    f"Workbench supervisor already running with PID {existing_pid}"
                ) from None
            _append_event(
                self.events_path,
                "stale_runtime_lock_recovered",
                stale_pid=existing_pid or None,
                lock_path=str(self.path),
            )
            self.path.unlink(missing_ok=True)
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "acquired_at": _now()}, handle)
            handle.write("\n")
        self.acquired = True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
        if current.get("pid") == os.getpid():
            self.path.unlink(missing_ok=True)
        self.acquired = False


@dataclass
class Component:
    name: str
    command: list[str]
    cwd: Path
    process: subprocess.Popen[Any] | None = None
    restart_times: deque[float] = field(default_factory=deque)
    restart_count: int = 0
    last_exit_code: int | None = None
    started_at: str | None = None
    health_url: str | None = None
    health_grace_seconds: float = 20
    next_health_check: float = 0
    health_grace_until: float = 0
    consecutive_health_failures: int = 0
    last_health_check_at: str | None = None
    last_health_ok_at: str | None = None
    last_health_error: str | None = None
    pending_restart_reason: str | None = None


class WorkbenchSupervisor:
    def __init__(
        self,
        workspace: Path,
        api_port: int,
        ui_port: int,
        *,
        max_restarts: int = 8,
        restart_window_seconds: float = 300,
        restart_backoff_seconds: float = 1,
        health_interval_seconds: float = 3,
        health_timeout_seconds: float = 2,
        health_failure_threshold: int = 3,
    ) -> None:
        self.workspace = workspace
        self.runtime = workspace / "data/workbench/runtime"
        self.state_path = self.runtime / "supervisor_state.json"
        self.events_path = self.runtime / "supervisor_events.jsonl"
        self.lock = RuntimeLock(self.runtime / "supervisor.lock.json", self.events_path)
        self.max_restarts = max_restarts
        self.restart_window_seconds = restart_window_seconds
        self.restart_backoff_seconds = restart_backoff_seconds
        self.health_interval_seconds = health_interval_seconds
        self.health_timeout_seconds = health_timeout_seconds
        self.health_failure_threshold = health_failure_threshold
        self.stop_requested = False
        self.started_at = _now()
        python = workspace / ".venv/bin/python"
        if not python.exists():
            python = Path(sys.executable)
        self.components = [
            Component(
                name="api",
                command=[
                    str(python),
                    "-m",
                    "esg_reliable_discovery.workbench_api",
                    "--workspace",
                    str(workspace),
                    "--port",
                    str(api_port),
                ],
                cwd=workspace,
                health_url=f"http://127.0.0.1:{api_port}/api/v1/health",
                health_grace_seconds=15,
            ),
            Component(
                name="ui",
                command=["npm", "run", "dev", "--", "--port", str(ui_port)],
                cwd=workspace / "workbench-ui",
                health_url=f"http://localhost:{ui_port}/",
                health_grace_seconds=45,
            ),
        ]

    def _write_state(self, status: str) -> None:
        _atomic_json(
            self.state_path,
            {
                "schema_version": "1.0",
                "status": status,
                "supervisor_pid": os.getpid(),
                "started_at": self.started_at,
                "updated_at": _now(),
                "policy": {
                    "max_restarts": self.max_restarts,
                    "restart_window_seconds": self.restart_window_seconds,
                    "restart_backoff_seconds": self.restart_backoff_seconds,
                    "health_interval_seconds": self.health_interval_seconds,
                    "health_timeout_seconds": self.health_timeout_seconds,
                    "health_failure_threshold": self.health_failure_threshold,
                    "completed_jobs_are_never_restarted": True,
                },
                "components": {
                    component.name: {
                        "pid": component.process.pid if component.process else None,
                        "running": bool(component.process and component.process.poll() is None),
                        "started_at": component.started_at,
                        "restart_count": component.restart_count,
                        "last_exit_code": component.last_exit_code,
                        "health_url": component.health_url,
                        "health_status": (
                            "unhealthy"
                            if component.consecutive_health_failures
                            >= self.health_failure_threshold
                            else "healthy"
                            if component.last_health_ok_at
                            else "starting"
                        ),
                        "consecutive_health_failures": component.consecutive_health_failures,
                        "last_health_check_at": component.last_health_check_at,
                        "last_health_ok_at": component.last_health_ok_at,
                        "last_health_error": component.last_health_error,
                    }
                    for component in self.components
                },
            },
        )

    def _start_component(self, component: Component, reason: str) -> None:
        component.process = subprocess.Popen(component.command, cwd=component.cwd)
        component.started_at = _now()
        monotonic_now = time.monotonic()
        component.health_grace_until = monotonic_now + component.health_grace_seconds
        component.next_health_check = component.health_grace_until
        component.consecutive_health_failures = 0
        component.last_health_check_at = None
        component.last_health_ok_at = None
        component.last_health_error = None
        component.pending_restart_reason = None
        _append_event(
            self.events_path,
            "component_started",
            component=component.name,
            pid=component.process.pid,
            reason=reason,
            restart_count=component.restart_count,
        )

    def _check_component_health(
        self, component: Component, monotonic_now: float
    ) -> None:
        process = component.process
        if (
            not component.health_url
            or not process
            or process.poll() is not None
            or component.pending_restart_reason
            or monotonic_now < component.next_health_check
        ):
            return
        component.next_health_check = monotonic_now + self.health_interval_seconds
        component.last_health_check_at = _now()
        healthy, detail = _probe_http(
            component.health_url, self.health_timeout_seconds
        )
        if healthy:
            recovered = component.consecutive_health_failures > 0
            component.consecutive_health_failures = 0
            component.last_health_ok_at = component.last_health_check_at
            component.last_health_error = None
            if recovered:
                _append_event(
                    self.events_path,
                    "component_health_recovered",
                    component=component.name,
                    health_url=component.health_url,
                )
            return
        component.consecutive_health_failures += 1
        component.last_health_error = detail
        _append_event(
            self.events_path,
            "component_health_probe_failed",
            component=component.name,
            health_url=component.health_url,
            consecutive_failures=component.consecutive_health_failures,
            failure_threshold=self.health_failure_threshold,
            detail=detail,
        )
        if component.consecutive_health_failures >= self.health_failure_threshold:
            component.pending_restart_reason = "health_probe_failure"
            _append_event(
                self.events_path,
                "component_unhealthy_restart_requested",
                component=component.name,
                pid=process.pid,
                health_url=component.health_url,
                consecutive_failures=component.consecutive_health_failures,
            )
            process.terminate()

    def _restart_allowed(self, component: Component, monotonic_now: float) -> bool:
        cutoff = monotonic_now - self.restart_window_seconds
        while component.restart_times and component.restart_times[0] < cutoff:
            component.restart_times.popleft()
        return len(component.restart_times) < self.max_restarts

    def _stop_components(self) -> None:
        for component in self.components:
            process = component.process
            if process and process.poll() is None:
                process.terminate()
        for component in self.components:
            process = component.process
            if not process:
                continue
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def request_stop(self, _signum: int, _frame: object | None) -> None:
        self.stop_requested = True

    def run(self) -> int:
        self.lock.acquire()
        signal.signal(signal.SIGINT, self.request_stop)
        signal.signal(signal.SIGTERM, self.request_stop)
        _append_event(self.events_path, "supervisor_started", pid=os.getpid())
        try:
            for component in self.components:
                self._start_component(component, "initial_start")
            self._write_state("running")
            while not self.stop_requested:
                for component in self.components:
                    process = component.process
                    if process and process.poll() is None:
                        self._check_component_health(component, time.monotonic())
                        continue
                    if not process:
                        continue
                    component.last_exit_code = process.returncode
                    _append_event(
                        self.events_path,
                        "component_exited",
                        component=component.name,
                        pid=process.pid,
                        exit_code=process.returncode,
                    )
                    now = time.monotonic()
                    if not self._restart_allowed(component, now):
                        _append_event(
                            self.events_path,
                            "restart_budget_exhausted",
                            component=component.name,
                            max_restarts=self.max_restarts,
                            window_seconds=self.restart_window_seconds,
                        )
                        self._write_state("failed_restart_budget_exhausted")
                        return 2
                    component.restart_times.append(now)
                    component.restart_count += 1
                    delay = min(
                        self.restart_backoff_seconds * (2 ** (component.restart_count - 1)),
                        30,
                    )
                    _append_event(
                        self.events_path,
                        "component_restart_scheduled",
                        component=component.name,
                        delay_seconds=delay,
                        restart_count=component.restart_count,
                    )
                    time.sleep(delay)
                    if not self.stop_requested:
                        self._start_component(
                            component,
                            component.pending_restart_reason or "unexpected_exit",
                        )
                self._write_state("stopping" if self.stop_requested else "running")
                time.sleep(0.5)
        finally:
            self._write_state("stopping")
            self._stop_components()
            self._write_state("stopped")
            _append_event(self.events_path, "supervisor_stopped", pid=os.getpid())
            self.lock.release()
        return 0


def _runtime_paths(workspace: Path) -> tuple[Path, Path, Path]:
    runtime = workspace / "data/workbench/runtime"
    return (
        runtime / "supervisor_state.json",
        runtime / "supervisor.lock.json",
        runtime / "workbench.log",
    )


def _read_supervisor_pid(lock_path: Path) -> int | None:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        pid = int(payload["pid"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return pid if _pid_alive(pid) else None


def _detach(workspace: Path, argv: list[str]) -> int:
    state_path, lock_path, log_path = _runtime_paths(workspace)
    existing_pid = _read_supervisor_pid(lock_path)
    if existing_pid:
        print(f"Workbench supervisor already running with PID {existing_pid}")
        return 0
    log_path.parent.mkdir(parents=True, exist_ok=True)
    foreground_args = [argument for argument in argv if argument != "--detach"]
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), *foreground_args],
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if _read_supervisor_pid(lock_path) == process.pid:
            print(f"Workbench supervisor started with PID {process.pid}")
            print(f"Runtime state: {state_path}")
            print(f"Runtime log: {log_path}")
            return 0
        if process.poll() is not None:
            print(f"Workbench supervisor failed to start; see {log_path}", file=sys.stderr)
            return process.returncode or 1
        time.sleep(0.1)
    print(f"Workbench supervisor startup timed out; see {log_path}", file=sys.stderr)
    return 1


def _status(workspace: Path) -> int:
    state_path, lock_path, _ = _runtime_paths(workspace)
    pid = _read_supervisor_pid(lock_path)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {"status": "unknown"}
    state["supervisor_alive"] = pid is not None
    state["supervisor_pid"] = pid or state.get("supervisor_pid")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if pid else 1


def _stop(workspace: Path) -> int:
    _, lock_path, _ = _runtime_paths(workspace)
    pid = _read_supervisor_pid(lock_path)
    if not pid:
        print("Workbench supervisor is not running")
        return 0
    os.kill(pid, signal.SIGTERM)
    print(f"Stop requested for workbench supervisor PID {pid}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ESG knowledge workbench locally")
    parser.add_argument("--api-port", type=int, default=8787)
    parser.add_argument("--ui-port", type=int, default=5173)
    parser.add_argument("--max-restarts", type=int, default=8)
    parser.add_argument("--restart-window-seconds", type=float, default=300)
    parser.add_argument("--restart-backoff-seconds", type=float, default=1)
    parser.add_argument("--health-interval-seconds", type=float, default=3)
    parser.add_argument("--health-timeout-seconds", type=float, default=2)
    parser.add_argument("--health-failure-threshold", type=int, default=3)
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args(argv)
    workspace = Path(__file__).resolve().parents[1]
    if args.status:
        return _status(workspace)
    if args.stop:
        return _stop(workspace)
    if args.detach:
        raw_args = list(argv) if argv is not None else sys.argv[1:]
        return _detach(workspace, raw_args)
    print(f"Workbench: http://localhost:{args.ui_port}", flush=True)
    print(f"Local API: http://127.0.0.1:{args.api_port}/api/v1/health", flush=True)
    supervisor = WorkbenchSupervisor(
        workspace,
        args.api_port,
        args.ui_port,
        max_restarts=args.max_restarts,
        restart_window_seconds=args.restart_window_seconds,
        restart_backoff_seconds=args.restart_backoff_seconds,
        health_interval_seconds=args.health_interval_seconds,
        health_timeout_seconds=args.health_timeout_seconds,
        health_failure_threshold=args.health_failure_threshold,
    )
    try:
        return supervisor.run()
    except AlreadyRunningError as error:
        print(str(error), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
