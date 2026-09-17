# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P22-V31-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P22-BAYER-AR2025"
DOCUMENT_SHA = "0af4a9d19fd9d4cba72c1ec062802199873f2379f84112dc2db5dc9605ce769b"
PAGES = [130, 132, 149, 151, 171, 172, 203, 204, 374, 375, 377]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, payload: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing_to_overwrite:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    readiness_path = ROOT / "data/results/p22_v31_local_readiness_v0.1.lock.json"
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    boundary = readiness["cloud_boundary"]
    if readiness.get("status") != "local_readiness_passed_waiting_for_payload_specific_cloud_authorization" or readiness["document_sha256"] != DOCUMENT_SHA or boundary["authorized_pages_required"] != PAGES or boundary["candidate_model"] != "qwen3.5:397b-cloud":
        raise RuntimeError("p22_frozen_scope_or_readiness_mismatch")
    auth_path = ROOT / "data/manifests/p22_cloud_authorization_exact_2026-09-12_v0.1.lock.json"
    write_new(auth_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "authorized_by_user", "authorized_at": datetime.now(UTC).isoformat(), "authorization_source": "current_thread_exact_user_message", "user_message": "我授权将 Bayer Annual Report 2025 第130、132、149、151、171、172、203、204、374、375、377页的冻结证据发送至 Ollama Cloud 的 qwen3.5:397b-cloud，仅用于 P22 Stage A/Stage B 单次候选推理。", "report": "Bayer Annual Report 2025", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "pages": PAGES, "model": "qwen3.5:397b-cloud", "experiment_scope": "P22 Stage A/Stage B single-attempt candidate inference", "stage_scope": ["Stage A", "Stage B"], "single_attempt_only": True, "silent_retry_allowed": False, "posthoc_semantic_repair_allowed": False, "authorization_does_not_cover_other_reports_or_pages": True})
    pack_path = ROOT / "data/tasks/p22_local_execution_task_pack_v0.1.lock.json"
    release_path = ROOT / "data/tasks/p22_execution_release_RESUME01_v0.1.lock.json"
    write_new(release_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "released_after_exact_cloud_authorization", "resume_generation": "RESUME01", "parent_release": "data/tasks/p22_execution_release_v0.1.lock.json", "parent_release_not_used_for_candidate_inference": True, "inference_allowed": True, "structural_task_pack": str(pack_path.relative_to(ROOT)), "structural_task_pack_sha256": digest(pack_path), "authorization_record": str(auth_path.relative_to(ROOT)), "authorization_record_sha256": digest(auth_path), "integrity_gate_result": str(readiness_path.relative_to(ROOT)), "integrity_gate_result_sha256": digest(readiness_path), "single_attempt_per_stage": True, "silent_retry_allowed": False, "posthoc_semantic_repair_allowed": False})
    print("p22_authorized_execution_prepared")


if __name__ == "__main__":
    main()
