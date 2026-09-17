from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from esg_reliable_discovery.mineru_adapter import MinerUError, parse_with_mineru

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/manifests/scale_batch_001_target_pages.lock.json"
OUTPUT_ROOT = ROOT / "artifacts/scale_batch_001/mineru_targets"
SUMMARY = ROOT / "data/results/scale_batch_001_mineru_summary.lock.json"
CONFIG = ROOT / "configs/parsers/scale-batch-001-mineru-3.4.0-runtime.json"
RESUME_FROM: Path | None = None
BATCH_ID = "KB-SCALE-BATCH-001-RESUME01"


def write_summary(records: list[dict[str, Any]], total: int) -> None:
    complete = sum(record["status"] == "complete" for record in records)
    failed = sum(record["status"] == "failed" for record in records)
    payload = {
        "schema_version": "0.1",
        "batch_id": BATCH_ID,
        "updated_at": datetime.now(UTC).isoformat(),
        "status": "complete" if complete + failed == total else "in_progress",
        "cloud_transmission": False,
        "total_target_pages": total,
        "complete_pages": complete,
        "failed_pages": failed,
        "pending_pages": total - complete - failed,
        "records": records,
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    temporary = SUMMARY.with_suffix(SUMMARY.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(SUMMARY)


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    retry_keys: set[tuple[str, int]] | None = None
    if RESUME_FROM is not None:
        parent = json.loads(RESUME_FROM.read_text(encoding="utf-8"))
        if parent["status"] != "complete":
            raise RuntimeError("parent_mineru_attempt_not_terminal")
        retry_keys = {
            (record["document_id"], record["page"])
            for record in parent["records"]
            if record["status"] == "failed"
        }
    total = len(retry_keys) if retry_keys is not None else registry["totals"]["unique_target_pages"]
    records: list[dict[str, Any]] = []
    for document in registry["documents"]:
        source = ROOT / document["local_path"]
        for target in document["target_pages"]:
            page = target["page"]
            if retry_keys is not None and (document["document_id"], page) not in retry_keys:
                continue
            destination = OUTPUT_ROOT / f"{document['document_id']}-p{page:04d}"
            record_path = destination / "esg_rd_mineru_run.json"
            item = {
                "document_id": document["document_id"],
                "page": page,
                "themes": target["themes"],
                "output_directory": str(destination.relative_to(ROOT)),
            }
            if record_path.is_file():
                run_record = json.loads(record_path.read_text(encoding="utf-8"))
                item["status"] = "complete" if run_record.get("returncode") == 0 else "failed"
                item["checkpoint_reused"] = True
                records.append(item)
                write_summary(records, total)
                print(f"SKIP checkpoint {document['document_id']} page {page}", flush=True)
                continue
            if destination.exists() and any(destination.iterdir()):
                item["status"] = "failed"
                item["error"] = "uncheckpointed_output_requires_RESUME"
                records.append(item)
                write_summary(records, total)
                print(f"FAIL uncheckpointed {document['document_id']} page {page}", flush=True)
                continue
            print(f"START {document['document_id']} page {page}", flush=True)
            started_at = datetime.now(UTC).isoformat()
            started = time.perf_counter()
            try:
                parse_with_mineru(
                    source,
                    destination,
                    executable=str(ROOT / ".mineru-venv/bin/mineru"),
                    backend="pipeline",
                    method="auto",
                    start_page=page - 1,
                    end_page=page - 1,
                    tools_config=CONFIG,
                )
            except MinerUError as error:
                item["status"] = "failed"
                item["error"] = str(error)
                print(f"FAIL {document['document_id']} page {page}: {error}", flush=True)
            else:
                item["status"] = "complete"
                print(f"DONE {document['document_id']} page {page}", flush=True)
            item["started_at"] = started_at
            item["completed_at"] = datetime.now(UTC).isoformat()
            item["wall_seconds"] = round(time.perf_counter() - started, 6)
            records.append(item)
            write_summary(records, total)
    write_summary(records, total)


if __name__ == "__main__":
    main()
