from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P11-V20-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P11-SIEMENS-AR2025"
DOCUMENT_SHA = "a702335f2c2d4f18d3ead4053df2fc3a9be3ad69b062bedd938f3b2551213b27"
PAGES = [160, 169, 170, 176, 177, 178, 214, 215, 257, 258]
MODEL = "qwen3.5:397b-cloud"


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    auth_path = ROOT / "data/manifests/p11_cloud_authorization_2026-09-08.lock.json"
    auth = json.loads(auth_path.read_text())
    assert auth["status"] == "authorized_by_user"
    assert auth["report"] == "Siemens Annual Report 2025"
    assert auth["pages"] == PAGES
    assert auth["model"] == MODEL
    assert auth["scope"] == "P11 Stage A/Stage B single candidate attempts only"

    audit = load("data/results/p11_v20_prefreeze_integrity_audit_v0.1.lock.json")
    assert audit["status"] == "passed_release_blocked_only_by_cloud_authorization"
    frozen = load("data/tasks/p11_task_pack_v0.1.lock.json")
    released = dict(frozen)
    released.update(
        {
            "parent": "data/tasks/p11_task_pack_v0.1.lock.json",
            "status": "released_after_explicit_cloud_authorization",
            "authorization_record": str(auth_path.relative_to(ROOT)),
            "authorization_record_sha256": digest(auth_path),
            "integrity_gate_result": (
                "data/results/p11_v20_prefreeze_integrity_audit_v0.1.lock.json"
            ),
            "inference_allowed": True,
        }
    )
    for task in released["tasks"]:
        task["reference_file"] = (
            f"data/annotations/p11_simulated/{task['task_id']}.json"
        )
    task_output = ROOT / "data/tasks/p11_execution_task_pack_v0.1.lock.json"
    write(task_output, released)

    task_ids_by_page = {page: [] for page in PAGES}
    for task in released["tasks"]:
        for page in task["target_pages"]:
            task_ids_by_page[page].append(task["task_id"])

    parsed = load("data/manifests/p11_mineru_target_registry_RESUME01_v0.1.lock.json")
    parsed_by_page = {item["page"]: item for item in parsed["pages"]}
    targets = []
    executor_root = ROOT / "artifacts/p11/executor_registry_RESUME01"
    for page in PAGES:
        source = ROOT / parsed_by_page[page]["markdown"]
        content = source.with_name("siemens-annual-report-2025_content_list.json")
        assert content.is_file()
        output = executor_root / f"{DOCUMENT}-p{page:04d}"
        output.mkdir(parents=True, exist_ok=True)
        run_path = output / "esg_rd_mineru_run.json"
        if run_path.exists():
            raise RuntimeError(f"refusing_to_overwrite_executor_wrapper:{run_path}")
        run = {
            "schema_version": "1.0",
            "parser": "MinerU",
            "backend": "pipeline",
            "method": "auto",
            "returncode": 0,
            "input_pdf": str(
                ROOT / "data/raw/p11_staging/siemens-annual-report-2025.pdf"
            ),
            "input_sha256": DOCUMENT_SHA,
            "start_page_zero_based": page - 1,
            "end_page_zero_based": page - 1,
            "output_directory": str(output),
            "output_files": [
                {
                    "path": os.path.relpath(content, output),
                    "bytes": content.stat().st_size,
                    "sha256": digest(content),
                }
            ],
            "parser_probe": {
                "available": True,
                "version": "mineru, version 3.4.0",
                "version_source": "frozen_local_run",
            },
            "provenance": {
                "source_registry": (
                    "data/manifests/"
                    "p11_mineru_target_registry_RESUME01_v0.1.lock.json"
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
                "local_path": "data/raw/p11_staging/siemens-annual-report-2025.pdf",
                "pdf_page": page,
                "task_ids": sorted(task_ids_by_page[page]),
                "output_directory": str(output.relative_to(ROOT)),
                "output_file_count": 1,
                "run_record_sha256": digest(run_path),
                "status": "parsed_reused_without_semantic_change",
            }
        )
    registry = {
        "schema_version": "1.0",
        "parser": "MinerU 3.4.0 pipeline",
        "status": "executor_wrappers_frozen_after_authorization_before_inference",
        "parent": (
            "data/manifests/p11_mineru_target_registry_RESUME01_v0.1.lock.json"
        ),
        "unique_target_count": len(targets),
        "targets": targets,
    }
    write(
        ROOT / "data/manifests/p11_mineru_executor_registry_RESUME01_v0.1.lock.json",
        registry,
    )

    layout_targets = [
        {
            "task_id": task["task_id"],
            "document_id": DOCUMENT,
            "document_sha256": DOCUMENT_SHA,
            "pdf_path": "data/raw/p11_staging/siemens-annual-report-2025.pdf",
            "pdf_page": page,
        }
        for task in released["tasks"]
        for page in task["target_pages"]
    ]
    layout = {
        "schema_version": "1.0",
        "status": "executor_layout_registry_frozen_before_candidate_inference",
        "semantic_change": False,
        "selection_rule": "all frozen task pages eligible; references cannot select evidence",
        "two_dimensional_table_graph": (
            "configs/framework/p11_two_dimensional_table_graph_v0.1.lock.json"
        ),
        "targets": layout_targets,
    }
    write(ROOT / "configs/framework/p11_layout_fallback_registry_v0.1.lock.json", layout)
    print("p11_authorized_execution_prepared")


if __name__ == "__main__":
    main()
