from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from esg_reliable_discovery.knowledge_base import (
    replay_calculation_plan_from_table_cells,
    sha256_file,
    validate_records,
)

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main() -> None:
    kb_dir = ROOT / "data/knowledge_bases/v0.1"
    plans_path = ROOT / "configs/framework/p23_calculation_plans_v0.1.lock.json"
    graphs_path = ROOT / "configs/framework/p23_two_dimensional_table_graph_v0.1.lock.json"
    plans = json.loads(plans_path.read_text())["plans"]
    graphs = json.loads(graphs_path.read_text())["graphs"]
    completion_path = kb_dir / "p23_table_cell_completions.jsonl"
    if completion_path.exists():
        graph_index = {item["graph_id"]: item for item in graphs}
        for item in load_jsonl(completion_path):
            cell = [item["row"], item["column"], item["value"]]
            selected = graph_index[item["graph_id"]].setdefault("selected_cells", [])
            if cell not in selected:
                selected.append(cell)
    records = []
    reference_paths = []
    for task_id, plan in plans.items():
        if not plan.get("output_slot_map"):
            continue
        reference_path = ROOT / f"data/annotations/p23_simulated/{task_id}.json"
        reference = json.loads(reference_path.read_text())
        expected = reference.get("normalized_value", {})
        records.extend(replay_calculation_plan_from_table_cells(task_id, plan, graphs, expected))
        reference_paths.append(reference_path)

    schema = json.loads(
        (ROOT / "schemas/knowledge/calculation-replay-audit-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output_path = kb_dir / "calculation_replay_audits.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        )
    )
    counts = Counter(record["status"] for record in records)
    summary = {
        "schema_version": "0.1",
        "status": "p23_frozen_calculation_replay_complete",
        "scope": "P23 output slots with explicit frozen selected table cells",
        "counts": dict(sorted(counts.items())),
        "promotion_count": 0,
        "policy": "replay validation does not independently adjudicate simulated references",
        "inputs": {
            "calculation_plans": {
                "path": plans_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(plans_path),
            },
            "table_graph": {
                "path": graphs_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(graphs_path),
            },
            "derived_cell_completions": (
                {
                    "path": completion_path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(completion_path),
                }
                if completion_path.exists()
                else None
            ),
            "references": [
                {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
                for path in reference_paths
            ],
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "independent fact adjudication; P22 remains unreplayed because its frozen "
            "graphs lack selected cell values"
        ),
    }
    summary_path = kb_dir / "calculation_replay_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
