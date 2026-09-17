from __future__ import annotations

from pathlib import Path

import promote_scale_batch_019_six_dimension_facts_v01 as promoter

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    promoter.INCREMENT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_023_atomic_fact_records.jsonl"
    )
    promoter.VALIDATIONS = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_023_atomic_validations.jsonl"
    )
    promoter.SUMMARY = ROOT / "data/results/scale_batch_023_tier_b_promotion.lock.json"
    promoter.NATIVE_AUDIT = (
        ROOT / "data/results/scale_batch_023_native_coordinate_audit.lock.json"
    )
    promoter.SOURCES = {
        "KB-B023-GLENCORE-SR2025": {
            "path": ROOT
            / "data/raw/scale_batch_023/glencore-sustainability-report-2025.pdf",
            "sha256": "ea07caee265d09dd6abbea0d26523460f3f9bd04e67093f2e6eda23889f74d8d",
            "assurance_pages": [52, 53, 54, 55],
            "scope": "Glencore 2025 selected performance metrics and ICMM disclosures",
            "quote": "Table 1: 2025 Performance Metrics",
            "issuer": "engaged by Glencore plc",
            "period": "1 January 2025 – 31 December 2025",
            "conclusion": "nothing has come to our attention",
            "signatory": "ERM CVS",
        },
        "KB-B023-ARKEMA-URD2025": {
            "path": ROOT
            / "data/raw/scale_batch_023/arkema-universal-registration-document-2025.pdf",
            "sha256": "de11061374f70634028b7ffc561e33f93d2f69bf26043888f09be18a8f4f1632",
            "assurance_pages": [277, 278, 279, 280],
            "scope": "Arkema section 4.2 Sustainability report for year ended December 31st, 2025",
            "quote": "included in section 4.2 “Sustainability report”",
            "issuer": "statutory auditors of Arkema S.A.",
            "period": "year ended December 31st, 2025",
            "conclusion": "we have not identified material errors",
            "signatory": "French original signed by",
        },
        "KB-B023-CRH-SPR2025": {
            "path": ROOT
            / "data/raw/scale_batch_023/crh-sustainability-performance-report-2025.pdf",
            "sha256": "838c40c5c4a2bf8ebfb225d5f6579e38de4565efad44d91ce6fd456dea3ef9ba",
            "assurance_pages": [90, 91],
            "scope": (
                "CRH Selected Indicators in Annex tables on report pages 73 to 81 "
                "for reporting year ended 31st December 2025"
            ),
            "quote": "as reported on pages 73 to 81 of the Report",
            "issuer": "Independent Limited Assurance Report to CRH plc",
            "period": "reporting year ended 31st December 2025",
            "conclusion": "nothing has come to our attention",
            "signatory": "Shuhaib Maudarbaccus",
        },
    }
    promoter.PROMOTABLE = {
        "fact-19bd0e277c26ae32ef47fc20": ("KB-B023-CRH-SPR2025", "percent"),
        "fact-1000aed3a021cd253d5181f0": ("KB-B023-CRH-SPR2025", "percent"),
    }
    promoter.EXPECTED_CANDIDATES = 6
    promoter.BATCH_NUMBER = "023"
    promoter.STATUS = "scale_batch_023_six_dimension_tier_b_review_complete"
    promoter.BLOCKED_REASON = "comparative_period_outside_2025_assurance_scope"
    promoter.NEXT_GATE = "scale_batch_023_global_kb_rebuild_and_closure"
    promoter.ALLOWED_PERIODS = {
        "KB-B023-GLENCORE-SR2025": {2025},
        "KB-B023-ARKEMA-URD2025": {2025},
        "KB-B023-CRH-SPR2025": {2025},
    }
    promoter.main()


if __name__ == "__main__":
    main()
