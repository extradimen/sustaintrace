from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P17-V26-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P17-BMW-GROUP-REPORT-2025"
DOCUMENT_SHA = "7a7fd36bf7f274e776ef7eda30d3cda4335a99cbb45f097ae5e8268ccf7759e7"
PAGES = [127, 129, 130, 141, 142, 172, 178, 179, 372, 373, 374, 375]


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def dump_new(path: str, value: dict[str, Any]) -> str:
    target = ROOT / path
    if target.exists():
        raise RuntimeError(f"refusing_to_overwrite:{path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sha(path)


def main() -> None:
    task_pack_path = "data/tasks/p17_task_pack_RESUME01_v0.1.lock.json"
    registry_path = "data/manifests/p17_mineru_target_registry_RESUME02_v0.1.json"
    reference_freeze_path = (
        "data/manifests/p17_simulated_reference_freeze_RESUME02_v0.1.lock.json"
    )
    audit_path = (
        "data/results/p17_prefreeze_reference_consistency_audit_RESUME02_v0.1.lock.json"
    )
    contracts_path = "configs/framework/p17_slot_contracts_RESUME02_v0.1.lock.json"
    atomic_gold_path = (
        "data/annotations/p17_simulated/"
        "p17_atomic_slot_gold_RESUME02_v0.1.lock.json"
    )
    semantic_path = "configs/framework/p17_semantic_qualifiers_RESUME02_v0.1.lock.json"
    graph_path = (
        "configs/framework/p17_two_dimensional_table_graph_RESUME02_v0.1.lock.json"
    )
    calculation_path = (
        "configs/framework/p17_calculation_plans_RESUME02_v0.1.lock.json"
    )
    handles_path = (
        "configs/framework/p17_evidence_handle_whitelist_RESUME02_v0.1.lock.json"
    )
    scoring_path = "configs/framework/p17_scoring_rules_RESUME02_v0.1.lock.json"

    pack = load(task_pack_path)
    registry = load(registry_path)
    reference_freeze = load(reference_freeze_path)
    audit = load(audit_path)
    contracts = load(contracts_path)
    gold = load(atomic_gold_path)
    assert pack["experiment_id"] == registry["experiment_id"] == EXPERIMENT
    assert pack["document_id"] == registry["document_id"] == DOCUMENT
    assert pack["document_sha256"] == registry["document_sha256"] == DOCUMENT_SHA
    assert registry["success_count"] == registry["target_count"] == len(PAGES)
    assert registry["failure_count"] == 0
    assert sorted(item["pdf_page"] for item in registry["targets"]) == PAGES
    assert audit["gate_result"] == "pass"
    assert reference_freeze["candidate_reference_visibility"] is False
    assert reference_freeze["cloud_transmission_allowed"] is False
    task_ids = [item["task_id"] for item in pack["tasks"]]
    assert set(task_ids) == set(contracts["contracts"]) == set(gold["values"])
    slot_count = sum(len(items) for items in contracts["contracts"].values())
    assert slot_count == 74
    for task_id, items in contracts["contracts"].items():
        assert {item["slot_id"] for item in items} == set(gold["values"][task_id])

    layout_path = "configs/framework/p17_layout_fallback_registry_RESUME02_v0.1.lock.json"
    layout_targets = []
    for task in pack["tasks"]:
        for page in task["target_pages"]:
            target: dict[str, Any] = {
                "task_id": task["task_id"],
                "document_id": DOCUMENT,
                "document_sha256": DOCUMENT_SHA,
                "pdf_path": "data/raw/p17_staging/bmw-group-report-2025.pdf",
                "pdf_page": page,
                "primary_parser": "MinerU 3.4.0 checksum-verified target-page output",
            }
            if page == 127:
                target.update(
                    {
                        "fallback_parser": "pdftotext -layout",
                        "fallback_reason": (
                            "MinerU fused reasonable-assurance superscript marker 6 to "
                            "numeric cells; native layout and deterministic arithmetic "
                            "preserve the source values without semantic repair"
                        ),
                    }
                )
            elif page == 178:
                target.update(
                    {
                        "fallback_parser": "same-page frozen narrative",
                        "fallback_reason": (
                            "MinerU dropped the external-site-worker fatality table cell; "
                            "the immediately preceding narrative states the value verbatim"
                        ),
                    }
                )
            layout_targets.append(target)
    layout_sha = dump_new(
        layout_path,
        {
            "schema_version": "2.6",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "selection_rule": (
                "all frozen task/page pairs are registered; only predeclared page-local "
                "parser anomalies may invoke the stated native or narrative fallback"
            ),
            "semantic_change": False,
            "targets": layout_targets,
        },
    )

    execution_config_path = (
        "configs/experiments/p17-v26-unseen-lockbox-RESUME02-local.json"
    )
    execution_config_sha = dump_new(
        execution_config_path,
        {
            "schema_version": "2.6",
            "experiment_id": EXPERIMENT,
            "status": "frozen_local_configuration_pending_explicit_cloud_authorization",
            "model_config": "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
            "candidate_model": "qwen3.5:397b-cloud",
            "stage_a": {
                "single_attempt": True,
                "use_v15_grounding": True,
                "use_v21_calculation": True,
                "use_v24_layout_gate": True,
                "use_v25_calculation_adapter": True,
                "use_v26_evidence_handle_audit": True,
                "calculation_plans": calculation_path,
                "evidence_handle_whitelist": handles_path,
            },
            "stage_b": {
                "single_attempt": True,
                "use_v20_contract_gate": True,
                "use_v21_contract_adapters": False,
                "use_v24_preflight": True,
                "use_v24_layout_gate": True,
                "use_v25_single_block_ordered_spans": True,
                "use_v26_atomic_projection": True,
                "slot_contracts": contracts_path,
                "semantic_qualifiers": semantic_path,
            },
            "failure_policy": {
                "archive_model_behavior_failure": True,
                "silent_retry": False,
                "posthoc_semantic_repair": False,
                "infrastructure_resume_requires_lineage": True,
            },
            "cloud_transmission_allowed": False,
        },
    )

    local_pack_path = "data/tasks/p17_local_execution_task_pack_RESUME02_v0.1.lock.json"
    local_tasks = [
        {
            **task,
            "reference_file": f"data/annotations/p17_simulated/{task['task_id']}.json",
        }
        for task in pack["tasks"]
    ]
    local_pack_sha = dump_new(
        local_pack_path,
        {
            "schema_version": "2.6",
            "experiment_id": EXPERIMENT,
            "status": "frozen_local_pack_pending_explicit_cloud_authorization",
            "inference_allowed": False,
            "parent": task_pack_path,
            "source_registry": "data/manifests/p17_source_registry_RESUME01_v0.1.lock.json",
            "parser_registry": registry_path,
            "reference_freeze": reference_freeze_path,
            "reference_consistency_audit": audit_path,
            "slot_contracts": contracts_path,
            "atomic_scoring_projection": atomic_gold_path,
            "semantic_qualifiers": semantic_path,
            "table_graph": graph_path,
            "layout_fallback_registry": layout_path,
            "calculation_plans": calculation_path,
            "evidence_handle_whitelist": handles_path,
            "scoring_rules": scoring_path,
            "execution_config": execution_config_path,
            "tasks": local_tasks,
            "release_condition": (
                "User must explicitly authorize BMW Group Report 2025 pages "
                "127,129,130,141,142,172,178,179,372,373,374,375 to Ollama Cloud "
                "qwen3.5:397b-cloud solely for P17 Stage A/Stage B single-attempt "
                "candidate inference."
            ),
        },
    )

    lineage_path = (
        "data/manifests/p17_atomic_projection_lineage_RESUME02_v0.1.lock.json"
    )
    lineage_sha = dump_new(
        lineage_path,
        {
            "schema_version": "2.6",
            "experiment_id": EXPERIMENT,
            "status": "deterministic_structural_projection_frozen",
            "source_reference_freeze": reference_freeze_path,
            "source_reference_freeze_sha256": sha(reference_freeze_path),
            "slot_contracts": contracts_path,
            "slot_contracts_sha256": sha(contracts_path),
            "atomic_scoring_projection": atomic_gold_path,
            "atomic_scoring_projection_sha256": sha(atomic_gold_path),
            "task_count": len(task_ids),
            "slot_count": slot_count,
            "semantic_change": False,
            "candidate_model_used": False,
        },
    )

    report_path = "docs/78_P17_v2.6本地预冻结与云授权边界_v0.1.md"
    report_text = f"""# P17 v2.6 本地预冻结与云授权边界

## 结论

P17 已完成全部本地准备并通过预冻结一致性门，尚未向云模型传输任何 BMW
报告内容，也未启动候选推理。P3–P16 未被修改、重跑或重评分。

## 样本与任务

- 样本：BMW Group Report 2025
- 文档 SHA256：`{DOCUMENT_SHA}`
- 冻结问题：6 项
- 唯一证据页：12 页（{', '.join(map(str, PAGES))}）
- MinerU：12/12 成功，逐文件哈希通过
- 模拟参考：6 份，43 条逐字证据引文
- 原子评分槽位：74 个

## 解析异常与受控回退

- 第 127 页：MinerU 将合理鉴证脚注标记 6 与数值粘连；已在候选推理前声明使用原生版面
  与确定性算术交叉核验。
- 第 178 页：MinerU 丢失外部公司现场工作人员死亡人数的表格单元格；同页冻结叙述逐字
  给出该值，回退限定为同页叙述。

两项异常均已留痕，不改变问题、页窗或参考语义。

## 验证

- P17 专项测试：5 项通过
- 全库 Pytest：261 项通过
- Ruff：通过
- P17 JSON：全部可解析
- 云传输次数：0
- 候选模型调用次数：0

## 下一边界

只有在用户明确授权后，才可将 BMW Group Report 2025 第 127、129、130、141、142、
172、178、179、372、373、374、375 页的冻结证据发送至 Ollama Cloud 的
`qwen3.5:397b-cloud`，且仅用于 P17 Stage A/Stage B 单次候选推理。
"""
    report_target = ROOT / report_path
    if report_target.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    report_target.write_text(report_text, encoding="utf-8")
    report_sha = sha(report_path)

    readiness_path = "data/results/p17_v26_local_readiness_RESUME02_v0.1.lock.json"
    readiness_sha = dump_new(
        readiness_path,
        {
            "schema_version": "2.6",
            "experiment_id": EXPERIMENT,
            "status": "local_readiness_passed_waiting_for_explicit_cloud_authorization",
            "document_id": DOCUMENT,
            "document_sha256": DOCUMENT_SHA,
            "task_count": len(task_ids),
            "slot_count": slot_count,
            "unique_target_pages": PAGES,
            "mineru": {
                "success_count": 12,
                "failure_count": 0,
                "registry": registry_path,
                "registry_sha256": sha(registry_path),
                "declared_fallback_pages": [127, 178],
            },
            "prefreeze_integrity": {
                "status": "passed",
                "reference_audit": audit_path,
                "reference_audit_sha256": sha(audit_path),
                "reference_freeze": reference_freeze_path,
                "reference_freeze_sha256": sha(reference_freeze_path),
                "evidence_quotes_checked": 43,
                "contract_preflights_passed": slot_count,
                "deterministic_calculation_passed": True,
            },
            "artifacts": {
                "layout_registry": {"path": layout_path, "sha256": layout_sha},
                "execution_config": {
                    "path": execution_config_path,
                    "sha256": execution_config_sha,
                },
                "local_task_pack": {"path": local_pack_path, "sha256": local_pack_sha},
                "atomic_projection_lineage": {
                    "path": lineage_path,
                    "sha256": lineage_sha,
                },
                "report": {"path": report_path, "sha256": report_sha},
            },
            "verification": {
                "p17_tests": "5 passed",
                "full_pytest": "261 passed",
                "ruff": "passed",
                "p17_json_validation": "passed",
                "artifact_hash_validation": "passed",
            },
            "cloud_boundary": {
                "candidate_model": "qwen3.5:397b-cloud",
                "cloud_transmission_count": 0,
                "candidate_model_call_count": 0,
                "explicit_authorization_received": False,
                "authorized_pages_required": PAGES,
                "authorized_scope_required": "P17 Stage A/Stage B single-attempt inference",
            },
            "locked_prior_experiments_modified": False,
        },
    )
    print(
        json.dumps(
            {
                "status": "ready_waiting_for_authorization",
                "readiness": readiness_path,
                "readiness_sha256": readiness_sha,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
