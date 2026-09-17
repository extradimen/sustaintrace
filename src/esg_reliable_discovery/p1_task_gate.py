from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def audit_p1_task_exposure(
    task_pack_path: str | Path,
    exclusion_lock_path: str | Path,
) -> dict[str, Any]:
    task_pack = json.loads(Path(task_pack_path).read_text(encoding="utf-8"))
    exclusion_lock = json.loads(Path(exclusion_lock_path).read_text(encoding="utf-8"))
    exclusions = {
        item["candidate_id"]: set(item["excluded_pages"])
        for item in exclusion_lock.get("documents", [])
    }
    violations = []
    incomplete = []
    for slot in task_pack.get("slots", []):
        task_id = slot.get("task_id")
        target_pages = slot.get("target_pages")
        if slot.get("question_status") != "frozen" or not slot.get("question"):
            incomplete.append(task_id)
            continue
        if not isinstance(target_pages, list) or not target_pages:
            incomplete.append(task_id)
            continue
        forbidden = exclusions.get(slot.get("candidate_id"), set())
        overlap = sorted(set(target_pages) & forbidden)
        if overlap:
            violations.append({"task_id": task_id, "excluded_pages_used": overlap})
    passed = not violations and not incomplete and len(task_pack.get("slots", [])) == 24
    return {
        "schema_version": "1.0",
        "task_count": len(task_pack.get("slots", [])),
        "incomplete_task_ids": incomplete,
        "exposure_violations": violations,
        "passed": passed,
        "inference_allowed": False,
    }
