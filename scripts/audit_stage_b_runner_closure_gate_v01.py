from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/stage_b_runner_closure_gate_v0.1.lock.json"
RUNNERS = [
    "src/esg_reliable_discovery/p1_stage_b_runner.py",
    "src/esg_reliable_discovery/v1_stage_b_runner.py",
    "src/esg_reliable_discovery/v11_stage_b_runner.py",
    "src/esg_reliable_discovery/v13_stage_b_runner.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_runner(relative_path: str) -> dict[str, object]:
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"))
    phases = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "enforce_stage_b_handle_closure":
            continue
        for keyword in node.keywords:
            if keyword.arg == "gate_phase" and isinstance(keyword.value, ast.Constant):
                phases.append(keyword.value.value)
    return {
        "path": relative_path,
        "sha256": sha256(path),
        "gate_phases": sorted(phases),
        "complete": set(phases) == {"pre_model", "pre_knowledge_write"},
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing_to_overwrite_locked_result:{OUTPUT}")
    runners = [audit_runner(path) for path in RUNNERS]
    callers = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "scripts").glob("*.py")
        if path.resolve() != Path(__file__).resolve()
        if "run_v13_stage_b_task(" in path.read_text(encoding="utf-8")
    )
    payload = {
        "schema_version": "0.1",
        "result_id": "ESG-STAGE-B-RUNNER-CLOSURE-GATE-v0.1",
        "status": (
            "all_reusable_entry_points_fail_closed"
            if all(item["complete"] for item in runners)
            else "incomplete"
        ),
        "runner_entry_points": runners,
        "v13_caller_scripts": callers,
        "counts": {
            "runner_entry_points": len(runners),
            "fully_gated_entry_points": sum(bool(item["complete"]) for item in runners),
            "v13_caller_scripts_covered_by_central_entry_point": len(callers),
        },
        "boundaries": ["pre_model", "pre_knowledge_write"],
        "model_execution_performed": False,
        "cloud_transmission_performed": False,
        "historical_output_modified_or_rescored": False,
        "next_gate": "build the second repair queue from knowledge gaps and repair rankings",
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
