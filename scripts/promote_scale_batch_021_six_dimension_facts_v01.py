from __future__ import annotations

from pathlib import Path

import promote_scale_batch_019_six_dimension_facts_v01 as promoter

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    promoter.INCREMENT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_021_atomic_fact_records.jsonl"
    )
    promoter.VALIDATIONS = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_021_atomic_validations.jsonl"
    )
    promoter.SUMMARY = ROOT / "data/results/scale_batch_021_tier_b_promotion.lock.json"
    promoter.NATIVE_AUDIT = (
        ROOT / "data/results/scale_batch_021_native_coordinate_audit.lock.json"
    )
    promoter.SOURCES = {
        "KB-B021-CAPGEMINI-URD2025": {
            "path": ROOT
            / "data/raw/scale_batch_021/capgemini-universal-registration-document-2025.pdf",
            "sha256": "2307fecb6a5bb7cdd9802d819984fa99f689599b5e0028b6781650a564bf0771",
            "assurance_pages": [317, 318, 319, 320],
            "scope": (
                "Capgemini SE section 4A 2025 Sustainability Statement for the year ended "
                "December 31, 2025, including reported comparative information"
            ),
            "quote": (
                "It covers the sustainability information and the information required by "
                "Article 8 of Regulation (EU) 2020/852"
            ),
            "issuer": "Capgemini SE",
            "period": "December 31, 2025",
            "conclusion": "not identified material errors",
            "signatory": "Anne-Laure Rousselou",
        },
        "KB-B021-REXEL-URD2025": {
            "path": ROOT
            / "data/raw/scale_batch_021/rexel-universal-registration-document-2025.pdf",
            "sha256": "1fa5bb1d5a0323384c20ce25ec500c25677bc6b3dc6dc70d45c4540c575afba6",
            "assurance_pages": [340, 341, 342, 343, 344],
            "scope": (
                "Rexel SA section 4 Sustainability Statement for the financial year ended "
                "December 31, 2025, including reported comparative information"
            ),
            "quote": (
                "It covers the sustainability information and the information required by "
                "Article 8 of Regulation (EU) 2020/852"
            ),
            "issuer": "Rexel SA",
            "period": "December 31, 2025",
            "conclusion": "not identified material errors",
            "signatory": "François Jaumain",
        },
    }
    promoter.PROMOTABLE = {
        "fact-8ceab3c738a122c48216bddd": ("KB-B021-CAPGEMINI-URD2025", "percent"),
        "fact-d0ae55d4bef70e678c4650e4": ("KB-B021-CAPGEMINI-URD2025", "percent"),
        "fact-63098bfb7b2b40b7a6d56978": ("KB-B021-CAPGEMINI-URD2025", "percent"),
        "fact-abd58c704358c84c719de807": ("KB-B021-CAPGEMINI-URD2025", "percent"),
        "fact-3aace6e7321a4f83bea77a5c": ("KB-B021-CAPGEMINI-URD2025", "percent"),
        "fact-4769317f2024c90591e7786b": ("KB-B021-REXEL-URD2025", "m3"),
        "fact-2f41f5750dda979acbdeb108": ("KB-B021-REXEL-URD2025", "m3"),
        "fact-689c8ad7b74e7668c34fd318": ("KB-B021-REXEL-URD2025", "L/m2"),
        "fact-7babe00e90f91591483ca1db": ("KB-B021-REXEL-URD2025", "L/m2"),
    }
    promoter.EXPECTED_CANDIDATES = 11
    promoter.BATCH_NUMBER = "021"
    promoter.STATUS = "scale_batch_021_six_dimension_tier_b_review_complete"
    promoter.BLOCKED_REASON = "native_row_header_not_corroborated"
    promoter.NEXT_GATE = "scale_batch_021_global_kb_rebuild_and_closure"
    promoter.ALLOWED_PERIODS = {
        "KB-B021-CAPGEMINI-URD2025": {2024, 2025, 2030},
        "KB-B021-REXEL-URD2025": {2024, 2025},
    }
    promoter.main()


if __name__ == "__main__":
    main()
