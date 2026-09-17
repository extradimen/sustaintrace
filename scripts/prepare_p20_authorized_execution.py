from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P20-V29-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P20-HOLCIM-SS2025"
DOCUMENT_SHA = "55b975cd13fc361638ed13bf32856a2629e46e88bdfc6ad9208bd8807992a599"
PAGES = [85, 86, 87, 111, 112, 113, 114, 120, 121, 134, 135, 136]
USER_MESSAGE = (
    "我授权将 Holcim《2025 Sustainability Statement》第85、86、87、111、112、113、"
    "114、120、121、134、135、136页的冻结证据发送至 Ollama Cloud 的 "
    "qwen3.5:397b-cloud，仅用于 P20 Stage A/Stage B 单次候选推理。"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, payload: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing_to_overwrite:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    validation_path = ROOT / "data/results/p20_v29_local_validation_v0.1.lock.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    expected = "local_validation_passed_waiting_for_payload_specific_cloud_authorization"
    if validation.get("status") != expected:
        raise RuntimeError("p20_prefreeze_audit_not_passed")
    readiness_path = ROOT / "data/results/p20_v29_local_readiness_v0.1.lock.json"
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    boundary = readiness["cloud_boundary"]
    if (
        readiness["document_sha256"] != DOCUMENT_SHA
        or boundary["authorized_pages_required"] != PAGES
        or boundary["candidate_model"] != "qwen3.5:397b-cloud"
    ):
        raise RuntimeError("p20_frozen_scope_mismatch")

    auth_path = ROOT / "data/manifests/p20_cloud_authorization_exact_2026-09-11_v0.1.lock.json"
    write_new(
        auth_path,
        {
            "schema_version": "2.9",
            "experiment_id": EXPERIMENT,
            "status": "authorized_by_user",
            "authorized_at": datetime.now(UTC).isoformat(),
            "authorization_source": "current_thread_exact_user_message",
            "user_message": USER_MESSAGE,
            "report": "Holcim 2025 Sustainability Statement",
            "document_id": DOCUMENT,
            "document_sha256": DOCUMENT_SHA,
            "pages": PAGES,
            "model": "qwen3.5:397b-cloud",
            "experiment_scope": "P20 Stage A/Stage B single-attempt candidate inference",
            "stage_scope": ["Stage A", "Stage B"],
            "single_attempt_only": True,
            "silent_retry_allowed": False,
            "posthoc_semantic_repair_allowed": False,
            "authorization_does_not_cover_other_reports_or_pages": True,
        },
    )

    pack_path = ROOT / "data/tasks/p20_local_execution_task_pack_v0.1.lock.json"
    release_path = ROOT / "data/tasks/p20_execution_release_v0.1.lock.json"
    write_new(
        release_path,
        {
            "schema_version": "2.9",
            "experiment_id": EXPERIMENT,
            "status": "released_after_exact_cloud_authorization",
            "inference_allowed": True,
            "structural_task_pack": str(pack_path.relative_to(ROOT)),
            "structural_task_pack_sha256": digest(pack_path),
            "exact_authorization_record": str(auth_path.relative_to(ROOT)),
            "exact_authorization_record_sha256": digest(auth_path),
            "integrity_gate_result": str(validation_path.relative_to(ROOT)),
            "integrity_gate_result_sha256": digest(validation_path),
            "single_attempt_per_stage": True,
            "silent_retry_allowed": False,
            "posthoc_semantic_repair_allowed": False,
        },
    )
    print("p20_authorized_execution_prepared")


if __name__ == "__main__":
    main()
