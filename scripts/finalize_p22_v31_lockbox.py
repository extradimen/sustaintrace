# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.archive import verify_run_checksums

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P22-V31-UNSEEN-LOCKBOX-V01"


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
    progress_path = "data/manifests/p22_candidate_progress.json"
    scores_path = "data/results/p22_v31_dimension_scores_v0.1.lock.json"
    progress = json.loads((ROOT / progress_path).read_text())
    scores = json.loads((ROOT / scores_path).read_text())
    records = {r["task_id"]: r for r in progress["records"]}
    runs_root = ROOT / "research_archive" / EXPERIMENT / "runs"
    runs = sorted(p for p in runs_root.iterdir() if p.is_dir())
    for run in runs:
        verify_run_checksums(run)
    framework_failed = ["P22-ENERGY-CALC-001", "P22-GHG-CALC-001", "P22-WATER-CALC-001", "P22-SAFETY-CALC-001"]
    result_path = "data/results/p22_v31_unseen_lockbox_v0.1_result.lock.json"
    summary = scores["summary_dimensions"]
    result = {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "completed_and_scored_with_four_framework_validation_order_failures", "decision": "P22_COMPLETED_LOCKED_NOT_ELIGIBLE_FOR_MODEL_PERFORMANCE_OR_CROSS_VERSION_AGGREGATE_SCORE", "candidate_model": "qwen3.5:397b-cloud", "task_count": 6, "candidate_stage_a_calls": 6, "candidate_stage_b_calls": 2, "single_candidate_attempt_per_behavioral_stage": True, "silent_retry": False, "posthoc_semantic_repair": False, "reference_visible_to_candidate": False, "stage_a": {"recorded_passed": 2, "recorded_failed": 4, "framework_integrity_review_passed": 2, "framework_integrity_review_failed": 4, "model_behavior_failed": 0}, "stage_b": {"eligible_tasks": 2, "passed": 2, "failed": 0}, "scoring": {"aggregate_score": None, "required_atomic_slots": summary["required_slots"], "credited_valid_slots": summary["credited_valid_slots"], "literal_or_numeric_exact_slots": summary["literal_or_numeric_exact_slots"], "numeric_exact_slots": summary["numeric_exact_slots"], "text_literal_exact_slots": summary["text_literal_exact_slots"], "text_normalized_exact_slots": summary["text_normalized_exact_slots"], "verified_run_archives": summary["verified_all_run_archives"]}, "integrity_finding": {"affected_tasks": framework_failed, "root_cause": "After v3.1 exact alias decoding and a successful canonical handle audit, the calculation adapter received the alias handle set instead of the canonical handle set and rejected the decoded canonical handles.", "candidate_conduct": "All four affected candidates emitted schema-valid exact aliases; alias decoding passed and the outer canonical-handle audit reported no invalid handles.", "recorded_taxonomy_limitation": "The run wrapper recorded these as model_behavior because the runner raised a generic OllamaError after the model call. The locked progress record is preserved; this final audit supersedes only the responsibility interpretation, not the raw result.", "recovery_policy": "No cloud retry and no posthoc completion of P22. Use the exposed failure only to develop v3.2, then evaluate on a new unseen lockbox."}, "task_results": {task_id: {"stage_a": record.get("stage_a"), "stage_b": record.get("stage_b"), "integrity_owner": "framework" if task_id in framework_failed else "none"} for task_id, record in records.items()}, "artifacts": {"progress": {"path": progress_path, "sha256": sha(progress_path)}, "dimension_scores": {"path": scores_path, "sha256": sha(scores_path)}, "execution_release": {"path": "data/tasks/p22_execution_release_RESUME01_v0.1.lock.json", "sha256": sha("data/tasks/p22_execution_release_RESUME01_v0.1.lock.json")}, "authorization": {"path": "data/manifests/p22_cloud_authorization_exact_2026-09-12_v0.1.lock.json", "sha256": sha("data/manifests/p22_cloud_authorization_exact_2026-09-12_v0.1.lock.json")}, "local_readiness": {"path": "data/results/p22_v31_local_readiness_v0.1.lock.json", "sha256": sha("data/results/p22_v31_local_readiness_v0.1.lock.json")}, "mineru_registry": {"path": "data/manifests/p22_mineru_target_registry_v0.1.lock.json", "sha256": sha("data/manifests/p22_mineru_target_registry_v0.1.lock.json")}}}
    result_sha = write_new(result_path, result)
    report_path = "docs/95_P22_v3.1未见锁箱结果与完整性审计_v0.1.md"
    report = ROOT / report_path
    if report.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    report.write_text(f"""# P22 v3.1 未见锁箱结果与完整性审计

## 结论

P22 已完成全部授权范围内的候选调用并锁定，但不能用于模型性能或跨版本总分比较。六项 Stage A 各调用一次，Taxonomy 与鉴证任务通过并各进入一次 Stage B；四项计算任务被 v3.1 的框架验证顺序缺陷阻断。没有云重试、静默重试或事后语义修补。

## 关键发现

四个计算任务的候选均输出了 JSON Schema 允许的精确短别名。短别名被精确解码为规范长句柄，外层 v2.6 句柄审计也全部通过；随后计算适配器错误地使用短别名集合再次校验已解码的长句柄，因此把有效句柄判为无效。运行包装器因模型调用已经发生而把通用 `OllamaError` 记成了 `model_behavior`，但证据证明责任属于框架。

冻结 checkpoint 和失败分类记录不修改；最终完整性审计仅纠正责任解释。P22 不补跑、不重评分，暴露失败只用于 v3.2 开发，并在新的未见锁箱上验证。

## 执行概况

| 任务 | Stage A | Stage B | 完整性结论 |
|---|---|---|---|
| P22-TAXONOMY-001 | 通过 | 通过 | 有效 |
| P22-ENERGY-CALC-001 | 记录为失败 | 不适用 | 框架验证顺序缺陷 |
| P22-GHG-CALC-001 | 记录为失败 | 不适用 | 框架验证顺序缺陷 |
| P22-WATER-CALC-001 | 记录为失败 | 不适用 | 框架验证顺序缺陷 |
| P22-SAFETY-CALC-001 | 记录为失败 | 不适用 | 框架验证顺序缺陷 |
| P22-ASSURE-001 | 通过 | 通过 | 有效 |

冻结参考共 {summary['required_slots']} 个原子槽位；有效最终输出覆盖 {summary['credited_valid_slots']} 个。由于四项被框架缺陷阻断，不生成汇总分数。

## 锁定

- 云调用：Stage A 6 次，Stage B 2 次
- 运行档案：{summary['verified_all_run_archives']} 个，SHA256 全部验证
- 结果：`{result_path}`
- 结果 SHA256：`{result_sha}`
- 逐维评分：`{scores_path}`
- checkpoint：`{progress_path}`

P22 现已锁定，不得修改、重跑或重评分。
""", encoding="utf-8")
    print(json.dumps({"result": result_path, "result_sha256": result_sha, "report": report_path, "report_sha256": sha(report_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
