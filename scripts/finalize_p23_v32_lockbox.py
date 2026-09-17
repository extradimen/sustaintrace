# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.archive import verify_run_checksums

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P23-V32-UNSEEN-LOCKBOX-V01"


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
    progress_path = "data/manifests/p23_candidate_progress.json"
    scores_path = "data/results/p23_v32_dimension_scores_v0.1.lock.json"
    progress = json.loads((ROOT / progress_path).read_text())
    scores = json.loads((ROOT / scores_path).read_text())
    records = {r["task_id"]: r for r in progress["records"]}
    runs = sorted(p for p in (ROOT / "research_archive" / EXPERIMENT / "runs").iterdir() if p.is_dir())
    for run in runs:
        verify_run_checksums(run)
    summary = scores["summary_dimensions"]
    result_path = "data/results/p23_v32_unseen_lockbox_v0.1_result.lock.json"
    result = {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "completed_and_scored_with_two_framework_stage_b_failures_and_one_model_behavior_failure", "decision": "P23_COMPLETED_LOCKED_NOT_ELIGIBLE_FOR_MODEL_PERFORMANCE_OR_CROSS_VERSION_AGGREGATE_SCORE", "candidate_model": "qwen3.5:397b-cloud", "task_count": 6, "candidate_stage_a_calls": 6, "candidate_stage_b_calls_started": 0, "single_candidate_attempt_per_behavioral_stage": True, "silent_retry": False, "posthoc_semantic_repair": False, "reference_visible_to_candidate": False, "stage_a": {"passed": 5, "failed": 1, "model_behavior_failed": 1}, "stage_b": {"eligible_tasks": 2, "passed": 0, "framework_failed_before_model_call": 2}, "scoring": {"aggregate_score": None, "required_atomic_slots": summary["required_slots"], "credited_valid_slots": summary["credited_valid_slots"], "literal_or_numeric_exact_slots": summary["literal_or_numeric_exact_slots"], "numeric_exact_slots": summary["numeric_exact_slots"], "text_literal_exact_slots": summary["text_literal_exact_slots"], "text_normalized_exact_slots": summary["text_normalized_exact_slots"], "verified_run_archives": summary["verified_all_run_archives"]}, "integrity_finding": {"framework_affected_tasks": ["P23-BOUNDARY-001", "P23-ASSURE-001"], "framework_error": "AttributeError:'str' object has no attribute 'get'", "framework_stage": "Stage B pre-model execution", "candidate_affected_task": "P23-WORKFORCE-CALC-001", "candidate_error": records["P23-WORKFORCE-CALC-001"]["stage_a_error"], "recovery_policy": "No cloud retry and no posthoc completion of P23. Preserve P23 as an integrity-bearing terminal lockbox result; any fix belongs to a future development phase and a new unseen lockbox."}, "task_results": {task_id: {"stage_a": record.get("stage_a"), "stage_b": record.get("stage_b"), "failure_owner": (record.get("stage_b_failure_taxonomy") or record.get("stage_a_failure_taxonomy") or {}).get("owner", "none")} for task_id, record in records.items()}, "artifacts": {"progress": {"path": progress_path, "sha256": sha(progress_path)}, "dimension_scores": {"path": scores_path, "sha256": sha(scores_path)}, "execution_release": {"path": "data/tasks/p23_execution_release_v0.1.lock.json", "sha256": sha("data/tasks/p23_execution_release_v0.1.lock.json")}, "authorization": {"path": "data/manifests/p23_cloud_authorization_exact_2026-09-12_v0.1.lock.json", "sha256": sha("data/manifests/p23_cloud_authorization_exact_2026-09-12_v0.1.lock.json")}, "local_readiness": {"path": "data/results/p23_v32_local_readiness_v0.1.lock.json", "sha256": sha("data/results/p23_v32_local_readiness_v0.1.lock.json")}, "mineru_registry": {"path": "data/manifests/p23_mineru_target_registry_v0.1.lock.json", "sha256": sha("data/manifests/p23_mineru_target_registry_v0.1.lock.json")}}}
    result_sha = write_new(result_path, result)
    report_path = "docs/98_P23_v3.2未见锁箱结果与完整性审计_v0.1.md"
    report = ROOT / report_path
    if report.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    report.write_text(f"""# P23 v3.2 未见锁箱结果与完整性审计

## 结论

P23 已完成授权范围内的单次候选运行、冻结评分和档案校验，现已锁定。六项 Stage A 中五项通过；Workforce 任务因候选输出包含未映射计算句柄而判为模型行为失败。两项需要 Stage B 的任务均在模型调用开始前触发相同框架异常，因此未产生 Stage B 云调用。

P23 不补跑、不重评分。由于两项框架失败，P23 不适合用于模型性能或跨版本汇总分比较；它仍是有效的框架完整性与失败发现记录。

## 执行概况

| 任务 | Stage A | Stage B | 责任分类 |
|---|---|---|---|
| P23-BOUNDARY-001 | 通过 | 调用前失败 | 框架 |
| P23-GHG-CALC-001 | 通过 | 不适用 | 无失败 |
| P23-ENERGY-CALC-001 | 通过 | 不适用 | 无失败 |
| P23-WATER-CALC-001 | 通过 | 不适用 | 无失败 |
| P23-WORKFORCE-CALC-001 | 失败 | 未进入 | 候选模型行为 |
| P23-ASSURE-001 | 通过 | 调用前失败 | 框架 |

冻结参考共 {summary['required_slots']} 个原子槽位；有效确定性投影覆盖 {summary['credited_valid_slots']} 个，精确匹配 {summary['literal_or_numeric_exact_slots']} 个。完整聚合分数不生成。

## 协议合规

- Stage A 云调用 6 次；Stage B 云调用 0 次。
- 无静默重试、无失败后重试、无事后语义修补。
- 模拟参考未进入候选上下文。
- {summary['verified_all_run_archives']} 个运行档案的 SHA256 已验证。

## 锁定产物

- 结果：`{result_path}`
- 结果 SHA256：`{result_sha}`
- 逐维评分：`{scores_path}`
- checkpoint：`{progress_path}`

P23 以及 P3–P22 既有结果保持锁定，不修改、不重跑、不重评分。
""", encoding="utf-8")
    print(json.dumps({"result": result_path, "result_sha256": result_sha, "report": report_path, "report_sha256": sha(report_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
