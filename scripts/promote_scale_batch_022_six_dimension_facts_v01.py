from __future__ import annotations

from pathlib import Path

import promote_scale_batch_019_six_dimension_facts_v01 as promoter

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    promoter.INCREMENT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_022_atomic_fact_records.jsonl"
    )
    promoter.VALIDATIONS = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_022_atomic_validations.jsonl"
    )
    promoter.SUMMARY = ROOT / "data/results/scale_batch_022_tier_b_promotion.lock.json"
    promoter.NATIVE_AUDIT = (
        ROOT / "data/results/scale_batch_022_native_coordinate_audit.lock.json"
    )
    promoter.SOURCES = {
        "KB-B022-ENGIE-URD2025": {
            "path": ROOT
            / "data/raw/scale_batch_022/engie-universal-registration-document-2025.pdf",
            "sha256": "a36a9568ecaa2fdfbb433afebc62ea653a8e9b57952d70164657405b088460bd",
            "assurance_pages": [220, 221],
            "scope": (
                "ENGIE selected social and environmental information for the year "
                "ended December 31, 2025; financial revenues are outside this scope"
            ),
            "quote": "selection of social and environmental information",
            "issuer": "statutory auditors of Engie",
            "period": "year ended December 31, 2025",
            "conclusion": "Information has been prepared, in all material respects",
            "signatory": "Nadia Laadouli",
        },
        "KB-B022-ORANGE-URD2025": {
            "path": ROOT
            / "data/raw/scale_batch_022/orange-universal-registration-document-2025.pdf",
            "sha256": "844c7fdf8bfd21bed694b02a80a67448c1b659d84991c47731875c472ce0f370",
            "assurance_pages": [482, 483, 484, 485],
            "scope": (
                "Orange Chapter 4 Sustainability Statement for the year ended "
                "December 31, 2025"
            ),
            "quote": "included in Chapter 4 in the Group Management Report",
            "issuer": "statutory auditors of ORANGE",
            "period": "Year ended December 31, 2025",
            "conclusion": "not identified any material errors",
            "signatory": "Christophe PATRIER",
        },
        "KB-B022-SKANSKA-ASR2025": {
            "path": ROOT
            / "data/raw/scale_batch_022/skanska-annual-and-sustainability-report-2025.pdf",
            "sha256": "ebf370f35c5ea1c395ff604abbd3c86147c58ab0fe3fd45a4b2f3014e732b2b9",
            "assurance_pages": [208, 209],
            "scope": (
                "Skanska AB sustainability statement on pages 50–89 for financial year 2025"
            ),
            "quote": "sustainability statement is included on pages 50–89",
            "issuer": "Skanska AB",
            "period": "financial year 2025",
            "conclusion": "nothing has come to our attention",
            "signatory": "Rickard Andersson",
        },
    }
    promoter.PROMOTABLE = {}
    promoter.EXPECTED_CANDIDATES = 2
    promoter.BATCH_NUMBER = "022"
    promoter.STATUS = "scale_batch_022_six_dimension_tier_b_review_complete"
    promoter.BLOCKED_REASON = "candidate_metric_outside_frozen_assurance_scope"
    promoter.NEXT_GATE = "scale_batch_022_global_kb_rebuild_and_closure"
    promoter.ALLOWED_PERIODS = {
        "KB-B022-ENGIE-URD2025": {2024, 2025},
        "KB-B022-ORANGE-URD2025": {2024, 2025},
        "KB-B022-SKANSKA-ASR2025": {2025},
    }
    promoter.main()


if __name__ == "__main__":
    main()
