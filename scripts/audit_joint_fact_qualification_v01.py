from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import (
    qualify_fact_jointly,
    sha256_file,
    validate_records,
)

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def phase(path: Path) -> int:
    match = re.search(r"p(\d+)_", path.name)
    return int(match.group(1)) if match else -1


def resume_rank(path: Path) -> tuple[int, str]:
    match = re.search(r"RESUME(\d+)", path.name)
    return (int(match.group(1)) if match else 0, path.name)


def latest_per_phase(pattern: str) -> list[Path]:
    grouped: dict[int, list[Path]] = {}
    for path in (ROOT / "configs/framework").glob(pattern):
        grouped.setdefault(phase(path), []).append(path)
    return [max(paths, key=resume_rank) for _, paths in sorted(grouped.items())]


def load_semantics(paths: list[Path]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in paths:
        payload = json.loads(path.read_text())
        qualifiers = payload.get("qualifiers", {})
        for task_id, value in qualifiers.items():
            if isinstance(task_id, str) and task_id.startswith("P"):
                result[task_id] = value
    return result


def load_calculations(paths: list[Path]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in paths:
        result.update(json.loads(path.read_text()).get("plans", {}))
    return result


def load_graphs(paths: list[Path]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for path in paths:
        for graph in json.loads(path.read_text()).get("graphs", []):
            graph_id = graph.get("graph_id")
            if graph_id not in seen:
                result.append(graph)
                seen.add(graph_id)
    return result


def main() -> None:
    kb_dir = ROOT / "data/knowledge_bases/v0.1"
    fact_path = kb_dir / "fact_records.jsonl"
    binding_path = kb_dir / "field_evidence_bindings.jsonl"
    facts = load_jsonl(fact_path)
    bindings = {item["fact_record_id"]: item for item in load_jsonl(binding_path)}
    semantic_paths = latest_per_phase("p*_semantic_qualifiers*.json")
    calculation_paths = latest_per_phase("p*_calculation_plans*.json")
    graph_paths = latest_per_phase("p*_two_dimensional_table_graph*.json")
    semantics = load_semantics(semantic_paths)
    calculations = load_calculations(calculation_paths)
    graphs = load_graphs(graph_paths)
    replay_path = kb_dir / "calculation_replay_audits.jsonl"
    replays = (
        {(item["task_id"], item["slot_id"]): item for item in load_jsonl(replay_path)}
        if replay_path.exists()
        else {}
    )
    records = [
        qualify_fact_jointly(
            fact,
            bindings[fact["record_id"]],
            semantics,
            calculations,
            graphs,
            replays,
        )
        for fact in facts
    ]
    schema = json.loads(
        (ROOT / "schemas/knowledge/joint-fact-qualification-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output_path = kb_dir / "joint_fact_qualifications.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    counts = Counter(item["qualification_status"] for item in records)
    dimensions = {
        name: dict(sorted(Counter(item[name]["status"] for item in records).items()))
        for name in (
            "period_binding",
            "unit_binding",
            "boundary_binding",
            "calculation_lineage",
            "table_cell_binding",
        )
    }
    source_paths = semantic_paths + calculation_paths + graph_paths
    summary = {
        "schema_version": "0.1",
        "status": "joint_qualification_inventory_complete_no_promotion",
        "records": len(records),
        "qualification_status_counts": dict(sorted(counts.items())),
        "dimension_status_counts": dimensions,
        "promotion_count": 0,
        "policy": (
            "qualification joins existing frozen artifacts but simulated references still "
            "require independent adjudication"
        ),
        "inputs": {
            "facts_sha256": sha256_file(fact_path),
            "field_bindings_sha256": sha256_file(binding_path),
            "calculation_replays_sha256": (
                sha256_file(replay_path) if replay_path.exists() else None
            ),
            "framework_artifacts": [
                {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
                for path in source_paths
            ],
        },
        "output": {
            "path": output_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output_path),
        },
        "next_gate": (
            "independent adjudication and deterministic calculation replay for jointly "
            "qualified candidates"
        ),
    }
    summary_path = kb_dir / "joint_fact_qualification_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary["qualification_status_counts"], sort_keys=True))


if __name__ == "__main__":
    main()
