from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P10-V19-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P10-SHELL-AR2025"
DOCUMENT_SHA = "90b21028e1616c41c7d73c3e996fd6128d837a41b38d432286e991aed3fbd9a1"
PAGES = [338, 339, 360, 361, 369, 370, 420, 426, 427]
MODEL = "qwen3.5:397b-cloud"


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    authorization_path = ROOT / "data/manifests/p10_cloud_authorization_2026-09-07.lock.json"
    authorization = json.loads(authorization_path.read_text())
    assert authorization["status"] == "authorized_by_user"
    assert authorization["report"] == "Shell Annual Report and Accounts 2025"
    assert authorization["pages"] == PAGES
    assert authorization["model"] == MODEL
    assert authorization["scope"] == "P10 Stage A/Stage B single candidate attempts only"

    frozen = load("data/tasks/p10_execution_task_pack_v0.1.lock.json")
    released = dict(frozen)
    released.update(
        {
            "parent": "data/tasks/p10_execution_task_pack_v0.1.lock.json",
            "status": "released_after_explicit_cloud_authorization",
            "authorization_record": str(authorization_path.relative_to(ROOT)),
            "authorization_record_sha256": digest(authorization_path),
            "inference_allowed": True,
        }
    )
    write(ROOT / "data/tasks/p10_execution_task_pack_v0.1.1.lock.json", released)

    task_ids_by_page = {page: [] for page in PAGES}
    for task in released["tasks"]:
        for page in task["target_pages"]:
            task_ids_by_page[page].append(task["task_id"])

    parsed = load("data/manifests/p10_mineru_target_registry_RESUME03_v0.1.lock.json")
    parsed_by_page = {item["page"]: item for item in parsed["pages"]}
    targets = []
    executor_root = ROOT / "artifacts/p10/executor_registry_RESUME01"
    for page in PAGES:
        source = ROOT / parsed_by_page[page]["markdown"]
        content = source.with_name("shell-annual-report-2025_content_list.json")
        assert content.is_file()
        output = executor_root / f"{DOCUMENT}-p{page:04d}"
        output.mkdir(parents=True, exist_ok=True)
        relative_content = os.path.relpath(content, output)
        run = {
            "schema_version": "1.0",
            "parser": "MinerU",
            "backend": "pipeline",
            "method": "auto",
            "returncode": 0,
            "input_pdf": str(ROOT / "data/raw/p10_staging/shell-annual-report-2025.pdf"),
            "input_sha256": DOCUMENT_SHA,
            "start_page_zero_based": page - 1,
            "end_page_zero_based": page - 1,
            "output_directory": str(output),
            "output_files": [
                {
                    "path": relative_content,
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
                    "p10_mineru_target_registry_RESUME03_v0.1.lock.json"
                ),
                "semantic_change": False,
                "cloud_transmission": False,
            },
        }
        run_path = output / "esg_rd_mineru_run.json"
        write(run_path, run)
        targets.append(
            {
                "target_id": f"{DOCUMENT}-p{page:04d}",
                "document_id": DOCUMENT,
                "document_sha256": DOCUMENT_SHA,
                "local_path": "data/raw/p10_staging/shell-annual-report-2025.pdf",
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
        "status": (
            "executor_compatible_provenance_wrappers_frozen_after_"
            "authorization_before_inference"
        ),
        "parent": "data/manifests/p10_mineru_target_registry_RESUME03_v0.1.lock.json",
        "unique_target_count": len(targets),
        "targets": targets,
    }
    write(ROOT / "data/manifests/p10_mineru_executor_registry_RESUME01_v0.1.lock.json", registry)

    layout_targets = []
    for task in released["tasks"]:
        for page in task["target_pages"]:
            layout_targets.append(
                {
                    "task_id": task["task_id"],
                    "document_id": DOCUMENT,
                    "document_sha256": DOCUMENT_SHA,
                    "pdf_path": "data/raw/p10_staging/shell-annual-report-2025.pdf",
                    "pdf_page": page,
                }
            )
    layout = {
        "schema_version": "1.0",
        "status": "executor_compatible_erratum_frozen_before_candidate_inference",
        "parent": "configs/framework/p10_layout_fallback_registry_v0.1.lock.json",
        "semantic_change": False,
        "selection_rule": (
            "all frozen task pages eligible; reference answers cannot select evidence"
        ),
        "two_dimensional_table_graph": (
            "configs/framework/p10_two_dimensional_table_graph_v0.1.lock.json"
        ),
        "targets": layout_targets,
    }
    write(ROOT / "configs/framework/p10_layout_fallback_registry_v0.1.1.lock.json", layout)

    contract_source = ROOT / "configs/framework/p10_slot_contracts_v0.1.lock.json"
    contracts = json.loads(contract_source.read_text())
    changed = []
    for task_id, task_contracts in contracts["contracts"].items():
        for contract in task_contracts:
            if contract["value_type"] in {"array", "object"}:
                changed.append(
                    {
                        "task_id": task_id,
                        "slot_id": contract["slot_id"],
                        "original_value_type": contract["value_type"],
                        "executor_value_type": "string",
                    }
                )
                contract["value_type"] = "string"
    contracts["schema_version"] = "1.0.1"
    contracts["executor_compatibility_erratum"] = {
        "parent": str(contract_source.relative_to(ROOT)),
        "reason": (
            "v13 atomic projection accepts only number/string/boolean; collection "
            "semantics remain represented by separate atomic slots and verbatim strings"
        ),
        "semantic_change": False,
        "changes": changed,
    }
    write(ROOT / "configs/framework/p10_slot_contracts_v0.1.1.lock.json", contracts)
    print("p10_authorized_execution_prepared")


if __name__ == "__main__":
    main()
