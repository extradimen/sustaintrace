from __future__ import annotations

from pathlib import Path

import promote_scale_batch_019_six_dimension_facts_v01 as promoter

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    promoter.INCREMENT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_026_atomic_fact_records.jsonl"
    )
    promoter.VALIDATIONS = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_026_atomic_validations.jsonl"
    )
    promoter.SUMMARY = ROOT / "data/results/scale_batch_026_tier_b_promotion.lock.json"
    promoter.NATIVE_AUDIT = (
        ROOT / "data/results/scale_batch_026_native_coordinate_audit.lock.json"
    )
    promoter.SOURCES = {}
    promoter.PROMOTABLE = {}
    promoter.EXPECTED_CANDIDATES = 1
    promoter.BATCH_NUMBER = "026"
    promoter.STATUS = "scale_batch_026_six_dimension_tier_b_review_complete_fail_closed"
    promoter.BLOCKED_REASON = "native_row_header_not_corroborated"
    promoter.NEXT_GATE = "scale_batch_026_global_kb_rebuild_and_closure"
    promoter.ALLOWED_PERIODS = {}
    promoter.main()


if __name__ == "__main__":
    main()
