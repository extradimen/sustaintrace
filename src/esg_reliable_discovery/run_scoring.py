from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .archive import refresh_run_checksums, verify_run_checksums
from .hashing import sha256_file
from .scoring import score_finding_card


def score_archived_closed_run(
    run_directory: str | Path,
    gold_directory: str | Path,
    schema_path: str | Path,
) -> dict[str, Any]:
    run_directory = Path(run_directory)
    score_path = run_directory / "score.json"
    if score_path.exists():
        raise FileExistsError(f"Score already exists and cannot be overwritten: {score_path}")
    verify_run_checksums(run_directory)
    context = json.loads((run_directory / "task_context_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((run_directory / "validation.json").read_text(encoding="utf-8"))
    if validation.get("status") != "passed":
        raise ValueError("Only Schema-valid archived model outputs can use the card scorer")
    task_id = context["task_id"]
    gold_path = Path(gold_directory) / f"{task_id}.json"
    if not gold_path.is_file():
        raise ValueError(f"No closed-task gold card exists for {task_id}")
    candidate = json.loads((run_directory / "normalized_output.json").read_text(encoding="utf-8"))
    if not isinstance(candidate, dict):
        raise ValueError("Closed-task scorer requires exactly one Finding Card object")
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    result = score_finding_card(candidate, gold, schema) | {
        "run_directory": str(run_directory),
        "gold_card_sha256": sha256_file(gold_path),
        "scored_at_stage": "post_run_closed_task",
    }
    score_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    refresh_run_checksums(run_directory)
    return result
