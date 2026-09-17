from __future__ import annotations

from pathlib import Path

import project_scale_batch_atomic_facts_v01 as projector

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    projector.SOURCE_FACTS = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_008_fact_records.jsonl"
    )
    projector.OUTPUT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_008_atomic_fact_records.jsonl"
    )
    projector.GRAPHS = ROOT / "data/manifests/scale_batch_008_table_graphs.lock.json"
    projector.SUMMARY = ROOT / "data/results/scale_batch_008_atomic_projection.lock.json"
    projector.BATCH_ID = "KB-SCALE-BATCH-008"
    projector.main()


if __name__ == "__main__":
    main()
