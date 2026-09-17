from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = json.loads((ROOT / "data/tasks/p10_task_pack_v0.1.lock.json").read_text())
    tasks = []
    for task in source["tasks"]:
        record = dict(task)
        record["reference_file"] = f"data/annotations/p10_simulated/{task['task_id']}.json"
        tasks.append(record)
    pack = {
        "schema_version": "1.0",
        "experiment_id": source["experiment_id"],
        "status": "frozen_but_not_released_pending_specific_cloud_authorization",
        "inference_allowed": False,
        "required_authorization": {
            "report": "Shell Annual Report and Accounts 2025",
            "pages": [338, 339, 360, 361, 369, 370, 420, 426, 427],
            "model": "qwen3.5:397b-cloud",
            "scope": "P10 Stage A/Stage B single candidate attempts only",
        },
        "integrity_gate_result": ("data/results/p10_v19_prefreeze_integrity_audit_v0.1.lock.json"),
        "tasks": tasks,
    }
    output = ROOT / "data/tasks/p10_execution_task_pack_v0.1.lock.json"
    output.write_text(json.dumps(pack, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
