from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def test_batch_five_final_mineru_inventory_is_complete() -> None:
    final = load("data/results/scale_batch_005_mineru_FINAL_summary.lock.json")
    targets = load("data/manifests/scale_batch_005_target_pages.lock.json")
    assert final["status"] == "complete"
    assert final["complete_pages"] == targets["totals"]["unique_target_pages"] == 27
    assert final["failed_pages"] == 0
    assert final["pending_pages"] == 0


def test_shutdown_abort_recovery_is_narrow_and_auditable() -> None:
    final = load("data/results/scale_batch_005_mineru_FINAL_summary.lock.json")
    assert final["post_completion_shutdown_recovered_pages"] == 2
    assert {(item["document_id"], item["page"]) for item in final["recovered_pages"]} == {
        ("KB-B005-HENKEL-AR2025", 477),
        ("KB-B005-SIKA-SR2025", 21),
    }
    recovered = [item for item in final["records"] if "original_status" in item]
    assert all(item["original_status"] == "failed" for item in recovered)
    assert all(item["original_returncode"] == -6 for item in recovered)
    assert all(len(item["output_sha256"]) == 4 for item in recovered)
