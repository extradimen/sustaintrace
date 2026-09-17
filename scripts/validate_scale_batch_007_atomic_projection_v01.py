from __future__ import annotations

from pathlib import Path

import validate_scale_batch_atomic_projection_v01 as validator

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    validator.FACTS = (
        ROOT
        / "data/knowledge_bases/v0.1/increments/scale_batch_007_atomic_fact_records.jsonl"
    )
    validator.GRAPHS = ROOT / "data/manifests/scale_batch_007_table_graphs.lock.json"
    validator.DIAGNOSTICS = ROOT / "data/results/scale_batch_007_diagnostics.lock.json"
    validator.OUTPUT = (
        ROOT
        / "data/knowledge_bases/v0.1/increments/scale_batch_007_atomic_validations.jsonl"
    )
    validator.SUMMARY = ROOT / "data/results/scale_batch_007_atomic_validation.lock.json"
    validator.BATCH_ID = "KB-SCALE-BATCH-007"
    validator.main()


if __name__ == "__main__":
    main()
