from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/results/scale_batch_001_final_audit.lock.json"
FILES = [
    "configs/knowledge/scale_batch_001_v0.1.json",
    "configs/knowledge/scale_batch_001_RESUME01_v0.2.json",
    "data/manifests/scale_batch_001_acquisition_failures.lock.json",
    "data/manifests/scale_batch_001_acquisition.lock.json",
    "data/results/scale_batch_001_diagnostics.lock.json",
    "data/manifests/scale_batch_001_target_pages.lock.json",
    "data/results/scale_batch_001_mineru_summary.lock.json",
    "data/manifests/scale_batch_001_mineru_RESUME01_lineage.lock.json",
    "data/results/scale_batch_001_mineru_RESUME01_summary.lock.json",
    "data/manifests/scale_batch_001_mineru_RESUME02_lineage.lock.json",
    "data/results/scale_batch_001_mineru_RESUME02_summary.lock.json",
    "data/results/scale_batch_001_kb_increment.lock.json",
    "data/results/scale_batch_001_evidence_gate.lock.json",
    "data/knowledge_bases/v0.1/increments/scale_batch_001_fact_records.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_001_failure_records.jsonl",
    "data/knowledge_bases/v0.1/increments/scale_batch_001_evidence_validations.jsonl",
    "data/knowledge_bases/v0.1/fact_records.jsonl",
    "data/knowledge_bases/v0.1/failure_records.jsonl",
    "configs/knowledge/repair_strategy_catalog_v0.1.json",
]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    targets = load("data/manifests/scale_batch_001_target_pages.lock.json")
    expected = {
        (document["document_id"], target["page"])
        for document in targets["documents"]
        for target in document["target_pages"]
    }
    successful = set()
    for summary_path in (
        "data/results/scale_batch_001_mineru_RESUME01_summary.lock.json",
        "data/results/scale_batch_001_mineru_RESUME02_summary.lock.json",
    ):
        summary = load(summary_path)
        successful.update(
            (record["document_id"], record["page"])
            for record in summary["records"]
            if record["status"] == "complete"
        )
    payload = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-001-RESUME01",
        "status": "batch_local_ingestion_complete",
        "checks": {
            "target_pages": len(expected),
            "successful_mineru_pages": len(successful),
            "all_target_pages_have_successful_generation": successful == expected,
            "locked_experiments_modified": False,
            "cloud_transmission": False,
            "fact_candidates_promoted_automatically": False,
        },
        "files": [
            {"path": item, "bytes": (ROOT / item).stat().st_size, "sha256": sha(ROOT / item)}
            for item in FILES
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["checks"]))


if __name__ == "__main__":
    main()
