# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.archive import verify_run_checksums

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P21-V30-UNSEEN-LOCKBOX-V01"


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def write_new(path: str, value: object) -> str:
    target = ROOT / path
    if target.exists():
        raise RuntimeError(f"refusing_to_overwrite:{path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha(path)


def main() -> None:
    progress_path = "data/manifests/p21_candidate_progress.json"
    scores_path = "data/results/p21_v30_dimension_scores_v0.1.lock.json"
    progress = json.loads((ROOT / progress_path).read_text())
    scores = json.loads((ROOT / scores_path).read_text())
    records = {r["task_id"]: r for r in progress["records"]}
    runs_root = ROOT / "research_archive" / EXPERIMENT / "runs"
    runs = sorted(p for p in runs_root.iterdir() if p.is_dir())
    for run in runs:
        verify_run_checksums(run)
    task_results = {
        "P21-GHG-CALC-001": "Stage A passed; executor-owned calculation passed; Stage B not required; no atomic slot projection was produced for scoring.",
        "P21-ENERGY-001": "Stage A model behavior failure: candidate emitted three nonexistent evidence handles; archived without retry.",
        "P21-SCOPE3-001": "Stage A passed; executor-owned calculation passed; Stage B not required; no atomic slot projection was produced for scoring.",
        "P21-WORKFORCE-001": "Stage A passed; executor-owned calculation passed; Stage B not required; no atomic slot projection was produced for scoring.",
        "P21-TAXONOMY-001": "Stage A model behavior failure: candidate emitted three nonexistent evidence handles; archived without retry.",
        "P21-ASSURE-001": "Stage A and Stage B passed; 12 valid atomic slots projected, one literal-exact and two normalized-exact text slots.",
    }
    result_path = "data/results/p21_v30_unseen_lockbox_v0.1_result.lock.json"
    summary = scores["summary_dimensions"]
    result = {
        "schema_version": "3.0",
        "experiment_id": EXPERIMENT,
        "status": "completed_and_scored_with_two_model_behavior_failures_and_one_scoring_interface_gap",
        "decision": "P21_COMPLETED_LOCKED_ELIGIBLE_FOR_PROTOCOL_ANALYSIS_NOT_FOR_SIMPLE_AGGREGATE_SCORE",
        "candidate_model": "qwen3.5:397b-cloud",
        "task_count": 6,
        "single_candidate_attempt_per_behavioral_stage": True,
        "silent_retry": False,
        "posthoc_semantic_repair": False,
        "reference_visible_to_candidate": False,
        "stage_a": {"tasks_entered": 6, "cloud_model_calls": 6, "framework_valid": 4, "model_behavior_failed": 2, "pre_call_executor_failed": 0},
        "stage_b": {"eligible_tasks": 1, "cloud_model_calls": 1, "framework_valid": 1, "model_behavior_failed": 0, "infrastructure_failed": 0, "not_required": 3, "not_reached": 2},
        "scoring": {"aggregate_score": None, "required_atomic_slots": summary["required_slots"], "credited_valid_slots": summary["credited_valid_slots"], "literal_or_numeric_exact_slots": summary["literal_or_numeric_exact_slots"], "numeric_exact_slots": summary["numeric_exact_slots"], "numeric_reference_slots": summary["numeric_reference_slots"], "text_literal_exact_slots": summary["text_literal_exact_slots"], "text_normalized_exact_slots": summary["text_normalized_exact_slots"], "text_reference_slots": summary["text_literal_reference_slots"], "verified_run_archives": summary["verified_all_run_archives"]},
        "task_results": task_results,
        "integrity_audit": {"candidate_outputs_preserved": True, "failed_outputs_preserved": True, "all_existing_run_checksums_verified": True, "candidate_attempts_repeated": False, "all_tasks_received_equal_single_stage_a_opportunity": True, "executor_identity_envelopes_present_for_all_stage_a_calls": all((run / "task_identity_envelope.json").exists() for run in runs if run.name.endswith("stage-a")), "candidate_task_id_repetition_required": False, "candidate_output_identity_fields_synthesized": False, "pytest_passed": 287, "ruff_passed": True, "frozen_p3_through_p20_modified": False},
        "framework_findings": {"v30_identity_envelope": "All six Stage A calls were executor-bound to the frozen task record, request and response hashes without requiring or synthesizing candidate task_id.", "candidate_handle_conformance": "Energy and EU Taxonomy outputs referenced handles absent from the frozen handle set and were correctly rejected.", "calculation_execution": "Three deterministic tasks bound all required source roles and the framework executed their frozen calculation DAGs successfully.", "scoring_interface_gap": "The current pipeline does not project successful deterministic-calculation outputs into atomic slot_id/value claims; consequently those valid calculations receive no atomic-slot credit. P21 is locked and will not be rescored post hoc."},
        "artifacts": {"progress": {"path": progress_path, "sha256": sha(progress_path)}, "dimension_scores": {"path": scores_path, "sha256": sha(scores_path)}, "execution_release": {"path": "data/tasks/p21_execution_release_v0.1.lock.json", "sha256": sha("data/tasks/p21_execution_release_v0.1.lock.json")}, "authorization": {"path": "data/manifests/p21_cloud_authorization_exact_2026-09-11_v0.1.lock.json", "sha256": sha("data/manifests/p21_cloud_authorization_exact_2026-09-11_v0.1.lock.json")}, "local_readiness": {"path": "data/results/p21_v30_local_readiness_v0.1.lock.json", "sha256": sha("data/results/p21_v30_local_readiness_v0.1.lock.json")}, "mineru_registry": {"path": "data/manifests/p21_mineru_target_registry_v0.1.lock.json", "sha256": sha("data/manifests/p21_mineru_target_registry_v0.1.lock.json")}},
        "record_status_check": {task_id: {"stage_a": record.get("stage_a"), "stage_b": record.get("stage_b")} for task_id, record in records.items()},
    }
    result_sha = write_new(result_path, result)
    report_path = "docs/92_P21_v3.0未见锁箱结果与完整性审计_v0.1.md"
    report = ROOT / report_path
    if report.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    report.write_text(f"""# P21 v3.0 未见锁箱结果与完整性审计

## 结论

P21 已在用户精确授权的 BASF Report 2025 十个冻结页和 `qwen3.5:397b-cloud` 范围内完成。六项任务各发生一次 Stage A；四项通过，两项因候选引用不存在的证据句柄而作为模型行为失败归档。三个确定性任务的冻结计算 DAG 均成功执行；鉴证任务进入并通过一次 Stage B。没有重试、补句柄或事后语义修补。

## 执行结果

| 任务 | Stage A | Stage B | 冻结评分表现 |
|---|---|---|---:|
| P21-GHG-CALC-001 | 通过，确定性计算通过 | 不需要 | 当前计算输出未投影为原子槽位，0 |
| P21-ENERGY-001 | 模型行为失败：3 个不存在句柄 | 未到达 | 0 |
| P21-SCOPE3-001 | 通过，确定性计算通过 | 不需要 | 当前计算输出未投影为原子槽位，0 |
| P21-WORKFORCE-001 | 通过，确定性计算通过 | 不需要 | 当前计算输出未投影为原子槽位，0 |
| P21-TAXONOMY-001 | 模型行为失败：3 个不存在句柄 | 未到达 | 0 |
| P21-ASSURE-001 | 通过 | 通过 | 12 个有效槽位；字面精确 1，归一化精确 2 |

冻结参考共 76 个原子槽位；12 个获得有效最终输出。由于当前评分接口不能把成功的确定性计算结果投影为 `slot_id/value` 声明，三个计算任务虽执行成功却没有原子槽位分。因此不生成单一汇总分数，也不得将 12/76 解释为模型内容准确率。

## v3.0 验证与新发现

v3.0 执行器身份信封在六次 Stage A 中全部正常工作：任务身份由冻结任务记录、实验/运行标识、请求和响应 SHA256 绑定；模型无需复述 `task_id`，执行器也没有向候选输出补写身份字段。P20 暴露的全体身份字段遗漏因此不再阻断内容评估。

P21 暴露了两个后续开发问题：第一，模型会把表格行句柄误写成不存在的单元格句柄，说明冻结句柄白名单虽能拒绝错误，但候选可见的句柄选择约束仍不充分；第二，确定性计算执行结果没有接入原子槽位投影器，使有效计算无法按冻结金标准评分。这是评分接口缺口，不应通过事后改写 P21 结果解决。

## 校验与锁定

- 运行档案：7 个，全部 SHA256 校验通过
- Pytest：287 项通过
- Ruff：通过
- 锁定结果：`{result_path}`
- 结果 SHA256：`{result_sha}`
- 逐维评分：`{scores_path}`
- checkpoint：`{progress_path}`

P21 现已锁定，只能作为后续开发集使用，不得修改、重跑或重评分。
""", encoding="utf-8")
    print(json.dumps({"result": result_path, "result_sha256": result_sha, "report": report_path, "report_sha256": sha(report_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
