from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def create_task_identity_envelope_v30(
    *,
    task_pack_path: str | Path,
    task_id: str,
    experiment_id: str,
    run_id: str,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    """Bind task identity to frozen execution metadata, outside model semantics."""
    task_pack_path = Path(task_pack_path)
    task_pack_bytes = task_pack_path.read_bytes()
    task_pack = json.loads(task_pack_bytes)
    matches = [task for task in task_pack.get("tasks", []) if task.get("task_id") == task_id]
    if len(matches) != 1:
        raise ValueError(f"v30_task_identity_not_unique:{task_id}:{len(matches)}")
    if not experiment_id or not run_id:
        raise ValueError("v30_execution_identity_empty")
    return {
        "schema_version": "3.0",
        "status": "executor_attested_before_candidate_call",
        "task_id": task_id,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "task_record_sha256": _canonical_sha256(matches[0]),
        "task_pack_sha256": hashlib.sha256(task_pack_bytes).hexdigest(),
        "request_payload_sha256": _canonical_sha256(request_payload),
        "identity_owner": "executor",
        "candidate_required_to_repeat_task_id": False,
        "candidate_output_modified": False,
        "posthoc_semantic_repair_applied": False,
    }


def bind_response_to_identity_v30(
    envelope: dict[str, Any], response_payload: dict[str, Any]
) -> dict[str, Any]:
    """Create an auditable response link without inserting identity into model output."""
    if envelope.get("status") != "executor_attested_before_candidate_call":
        raise ValueError("v30_identity_envelope_not_attested")
    linked = deepcopy(envelope)
    linked.update(
        {
            "status": "response_linked",
            "response_payload_sha256": _canonical_sha256(response_payload),
            "candidate_output_identity_field_required": False,
            "candidate_output_identity_field_synthesized": False,
            "candidate_output_modified": False,
            "posthoc_semantic_repair_applied": False,
        }
    )
    return linked
