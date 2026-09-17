from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P12-V21-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P12-VOLKSWAGEN-AR2025"
DOCUMENT_SHA = "6f3f1b606fe771020dad30685ad0140114e0f23fd6f0921bd47f0975e07d4338"
PAGES = [214, 215, 259, 260, 274, 275, 276, 280, 281, 366, 659, 660, 663]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    auth_path = ROOT / "data/manifests/p12_cloud_authorization_2026-09-08.lock.json"
    auth = json.loads(auth_path.read_text())
    assert auth["status"] == "authorized_by_user"
    assert auth["pages"] == PAGES and auth["model"] == "qwen3.5:397b-cloud"
    audit = json.loads(
        (ROOT / "data/results/p12_v21_prefreeze_integrity_audit_v0.1.lock.json").read_text()
    )
    assert audit["status"] == "passed_release_blocked_only_by_cloud_authorization"
    pack_path = ROOT / "data/tasks/p12_task_pack_v0.1.lock.json"
    pack = json.loads(pack_path.read_text())
    released = dict(pack)
    released.update(
        {
            "parent": str(pack_path.relative_to(ROOT)),
            "status": "released_after_explicit_cloud_authorization",
            "authorization_record": str(auth_path.relative_to(ROOT)),
            "authorization_record_sha256": digest(auth_path),
            "integrity_gate_result": (
                "data/results/p12_v21_prefreeze_integrity_audit_v0.1.lock.json"
            ),
            "inference_allowed": True,
        }
    )
    for task in released["tasks"]:
        task["reference_file"] = f"data/annotations/p12_simulated/{task['task_id']}.json"
    write(ROOT / "data/tasks/p12_execution_task_pack_v0.1.lock.json", released)

    tasks_by_page = {page: [] for page in PAGES}
    for task in released["tasks"]:
        for page in task["target_pages"]:
            tasks_by_page[page].append(task["task_id"])
    targets = []
    for page in PAGES:
        source = ROOT / f"artifacts/p12/native_pdf_targets/{DOCUMENT}-p{page:04d}.txt"
        assert source.is_file() and source.stat().st_size > 0
        out = ROOT / f"artifacts/p12/executor_registry/{DOCUMENT}-p{page:04d}"
        out.mkdir(parents=True, exist_ok=True)
        content = out / f"{DOCUMENT}_content_list.json"
        run_path = out / "esg_rd_mineru_run.json"
        if content.exists() or run_path.exists():
            raise RuntimeError(f"refusing_to_overwrite_executor_artifact:{out}")
        blocks = [
            {"type": "text", "text": line.strip(), "bbox": None, "page_idx": 0}
            for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        write(content, blocks)
        run = {
            "schema_version": "1.0",
            "parser": "native_pdf_layout_fallback",
            "backend": "pdftotext-layout",
            "method": "txt",
            "returncode": 0,
            "input_pdf": str(ROOT / "data/raw/p12_staging/volkswagen-group-annual-report-2025.pdf"),
            "input_sha256": DOCUMENT_SHA,
            "start_page_zero_based": page - 1,
            "end_page_zero_based": page - 1,
            "output_directory": str(out),
            "output_files": [
                {"path": content.name, "bytes": content.stat().st_size, "sha256": digest(content)}
            ],
            "parser_probe": {
                "available": True,
                "version": "pdftotext native layout fallback",
                "version_source": "frozen_local_run",
            },
            "provenance": {
                "source_registry": (
                    "data/manifests/p12_mineru_failure_and_native_fallback_v0.1.lock.json"
                ),
                "semantic_change": False,
                "cloud_transmission": False,
            },
        }
        write(run_path, run)
        targets.append(
            {
                "target_id": f"{DOCUMENT}-p{page:04d}",
                "document_id": DOCUMENT,
                "document_sha256": DOCUMENT_SHA,
                "local_path": "data/raw/p12_staging/volkswagen-group-annual-report-2025.pdf",
                "pdf_page": page,
                "task_ids": sorted(tasks_by_page[page]),
                "output_directory": str(out.relative_to(ROOT)),
                "output_file_count": 1,
                "run_record_sha256": digest(run_path),
                "status": "native_pdf_fallback_wrapped_without_semantic_change",
            }
        )
    write(
        ROOT / "data/manifests/p12_executor_registry_v0.1.lock.json",
        {
            "schema_version": "1.0",
            "parser": "native PDF layout fallback",
            "status": "executor_wrappers_frozen_after_authorization_before_inference",
            "parent": "data/manifests/p12_mineru_failure_and_native_fallback_v0.1.lock.json",
            "unique_target_count": len(targets),
            "targets": targets,
        },
    )
    layout_targets = [
        {
            "task_id": task["task_id"],
            "document_id": DOCUMENT,
            "document_sha256": DOCUMENT_SHA,
            "pdf_path": "data/raw/p12_staging/volkswagen-group-annual-report-2025.pdf",
            "pdf_page": page,
        }
        for task in released["tasks"]
        for page in task["target_pages"]
    ]
    write(
        ROOT / "configs/framework/p12_layout_fallback_registry_v0.1.lock.json",
        {
            "schema_version": "1.0",
            "status": "executor_layout_registry_frozen_before_candidate_inference",
            "semantic_change": False,
            "selection_rule": "all frozen task pages eligible; references cannot select evidence",
            "two_dimensional_table_graph": (
                "configs/framework/p12_two_dimensional_table_graph_v0.1.lock.json"
            ),
            "targets": layout_targets,
        },
    )
    print("p12_authorized_execution_prepared")


if __name__ == "__main__":
    main()
