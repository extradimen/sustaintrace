from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any


class P1TaskAllocationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allocate_p1_task_slots(
    sample_manifest_path: str | Path,
    quotas: dict[str, int],
    *,
    seed: int,
) -> dict[str, Any]:
    path = Path(sample_manifest_path)
    sample = json.loads(path.read_text(encoding="utf-8"))
    selected = sample.get("selected", [])
    expected = len(selected) * 2
    if sample.get("status") != "frozen" or len(selected) != 12:
        raise P1TaskAllocationError("Expected a frozen 12-report P1 sample")
    if sum(quotas.values()) != expected:
        raise P1TaskAllocationError(f"Task quotas must sum to {expected}")

    task_types = [name for name, count in sorted(quotas.items()) for _ in range(count)]
    rng = random.Random(seed)
    for _attempt in range(1, 10001):
        rng.shuffle(task_types)
        pairs = [task_types[index : index + 2] for index in range(0, expected, 2)]
        if all(pair[0] != pair[1] for pair in pairs):
            break
    else:
        raise P1TaskAllocationError("Could not allocate two distinct task types per report")

    slots = []
    for report_index, (report, pair) in enumerate(zip(selected, pairs, strict=True), start=1):
        for within_report, task_type in enumerate(pair, start=1):
            slots.append({
                "task_id": f"P1-{report_index:02d}-{within_report}",
                "candidate_id": report["candidate_id"],
                "document_id": report["document_id"],
                "task_type": task_type,
                "question_status": "awaiting_human_task_design",
                "annotation_status": "not_started",
                "model_access_allowed": False,
            })
    return {
        "schema_version": "1.0",
        "allocation_id": "P1-TASK-SLOTS-v0.1",
        "status": "allocation_frozen_questions_pending",
        "algorithm": "seeded_quota_shuffle_distinct_pair_rejection_v1",
        "seed": seed,
        "attempt": _attempt,
        "sample_manifest_sha256": _sha256(path),
        "task_count": len(slots),
        "quota_check": dict(sorted(Counter(slot["task_type"] for slot in slots).items())),
        "slots": slots,
        "inference_allowed": False,
    }
