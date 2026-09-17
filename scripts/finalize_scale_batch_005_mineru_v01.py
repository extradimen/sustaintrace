from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from esg_reliable_discovery.mineru_text_fallback import semantic_text_from_content_list

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "data/manifests/scale_batch_005_target_pages.lock.json"
ATTEMPTS = tuple(
    ROOT / f"data/results/scale_batch_005_mineru_RESUME0{index}_summary.lock.json"
    for index in (1, 2, 3)
)
ATTEMPT_LABELS = ("RESUME01", "RESUME02", "RESUME03")
OUTPUT = ROOT / "data/results/scale_batch_005_mineru_FINAL_summary.lock.json"
BATCH_ID = "KB-SCALE-BATCH-005-MINERU-FINAL"
REQUIRED_SUFFIXES = (".md", "_content_list.json", "_middle.json", "_model.json")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_files(directory: Path) -> dict[str, Path]:
    markdown = list(directory.rglob("*.md"))
    if len(markdown) != 1:
        raise RuntimeError(f"expected_one_markdown:{directory}:{len(markdown)}")
    base = markdown[0].with_suffix("")
    files = {".md": markdown[0]}
    for suffix in REQUIRED_SUFFIXES[1:]:
        candidate = base.parent / f"{base.name}{suffix}"
        if not candidate.is_file() or candidate.stat().st_size == 0:
            raise RuntimeError(f"missing_or_empty_output:{candidate}")
        files[suffix] = candidate
    if markdown[0].stat().st_size == 0:
        content_list = files["_content_list.json"]
        if not semantic_text_from_content_list(content_list).strip():
            raise RuntimeError(f"empty_mineru_semantic_text:{directory}")
    return files


def main() -> None:
    target_registry = read_json(TARGETS)
    target_keys = {
        (document["document_id"], target["page"])
        for document in target_registry["documents"]
        for target in document["target_pages"]
    }
    attempts = [read_json(path) for path in ATTEMPTS]
    records_by_key: dict[tuple[str, int], list[tuple[int, dict[str, Any]]]] = {
        key: [] for key in target_keys
    }
    for index, summary in enumerate(attempts, start=1):
        if summary["status"] != "complete":
            raise RuntimeError(f"attempt_not_terminal:{ATTEMPTS[index - 1]}")
        for record in summary["records"]:
            key = (record["document_id"], record["page"])
            records_by_key.setdefault(key, []).append((index, record))

    final_records = []
    recovered = []
    for key in sorted(target_keys):
        history = records_by_key[key]
        successful = [(index, item) for index, item in history if item["status"] == "complete"]
        if successful:
            index, item = successful[0]
            files = output_files(ROOT / item["output_directory"])
            final_records.append(
                {
                    **item,
                    "status": "complete",
                    "selected_attempt": ATTEMPT_LABELS[index - 1],
                    "completion_basis": "returncode_zero_and_required_outputs_present",
                    "output_sha256": {suffix: sha256_file(path) for suffix, path in files.items()},
                }
            )
            continue

        if len(history) != 3:
            raise RuntimeError(f"insufficient_recovery_history:{key}:{len(history)}")
        repeated_hashes: list[dict[str, str]] = []
        for index, item in history:
            run = read_json(ROOT / item["output_directory"] / "esg_rd_mineru_run.json")
            if run["returncode"] != -6 or "Completed batch 1/1" not in run["stderr"]:
                raise RuntimeError(
                    f"not_post_completion_shutdown_abort:{key}:{ATTEMPT_LABELS[index - 1]}"
                )
            files = output_files(ROOT / item["output_directory"])
            repeated_hashes.append(
                {suffix: sha256_file(path) for suffix, path in files.items()}
            )
        if len({json.dumps(item, sort_keys=True) for item in repeated_hashes}) != 1:
            raise RuntimeError(f"non_deterministic_recovered_outputs:{key}")
        index, item = history[-1]
        recovery = {
            **item,
            "status": "complete",
            "selected_attempt": ATTEMPT_LABELS[index - 1],
            "completion_basis": (
                "post_completion_shutdown_abort_with_three_identical_required_output_sets"
            ),
            "original_status": "failed",
            "original_returncode": -6,
            "output_sha256": repeated_hashes[-1],
        }
        final_records.append(recovery)
        recovered.append({"document_id": key[0], "page": key[1]})

    if len(final_records) != len(target_keys):
        raise RuntimeError("final_record_count_mismatch")
    payload = {
        "schema_version": "0.1",
        "batch_id": BATCH_ID,
        "updated_at": datetime.now(UTC).isoformat(),
        "status": "complete",
        "cloud_transmission": False,
        "total_target_pages": len(target_keys),
        "complete_pages": len(final_records),
        "failed_pages": 0,
        "pending_pages": 0,
        "post_completion_shutdown_recovered_pages": len(recovered),
        "recovered_pages": recovered,
        "parent_attempts": [path.relative_to(ROOT).as_posix() for path in ATTEMPTS],
        "parent_failures_preserved": True,
        "records": final_records,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "complete_pages": payload["complete_pages"],
                "recovered_pages": payload["post_completion_shutdown_recovered_pages"],
            }
        )
    )


if __name__ == "__main__":
    main()
