from __future__ import annotations

from pathlib import Path

import promote_scale_batch_019_six_dimension_facts_v01 as promoter

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    promoter.INCREMENT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_024_atomic_fact_records.jsonl"
    )
    promoter.VALIDATIONS = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_024_atomic_validations.jsonl"
    )
    promoter.SUMMARY = ROOT / "data/results/scale_batch_024_tier_b_promotion.lock.json"
    promoter.NATIVE_AUDIT = (
        ROOT / "data/results/scale_batch_024_native_coordinate_audit.lock.json"
    )
    promoter.SOURCES = {
        "KB-B024-YARA-AR2025": {
            "path": ROOT / "data/raw/scale_batch_024/yara-annual-report-2025.pdf",
            "sha256": "95ecc7a0b18ca97ee9d579bc3799ed58052a31584ef6b21ac55d466aa77ce5d2",
            "assurance_pages": [308, 309, 310, 311],
            "scope": (
                "Yara International ASA consolidated Sustainability Statement as at "
                "31 December 2025 and for the year then ended"
            ),
            "quote": (
                "We have conducted a limited assurance engagement on the consolidated "
                "sustainability statement of Yara International ASA"
            ),
            "issuer": "consolidated sustainability statement of Yara International ASA",
            "period": "as at 31 December 2025 and for the year then ended",
            "conclusion": "nothing has come to our attention",
            "signatory": "Espen Johansen",
        },
        "KB-B024-TELENOR-AR2025": {
            "path": ROOT / "data/raw/scale_batch_024/telenor-annual-report-2025.pdf",
            "sha256": "308f8724d892dfb85582b8278c3a9852b8771f5cd2297fde020916ccecb2d701",
            "assurance_pages": [277, 278, 279, 280],
            "scope": (
                "Telenor ASA consolidated Sustainability Statement as at 31 December "
                "2025 and for the year then ended"
            ),
            "quote": (
                "We have conducted a limited assurance engagement on the consolidated "
                "sustainability statement of Telenor ASA"
            ),
            "issuer": "statement of Telenor ASA",
            "period": "as at 31 December 2025",
            "conclusion": "come to our attention",
            "signatory": "Anders Gøbel",
        },
    }
    promoter.PROMOTABLE = {
        "fact-905f6fc433c4da967372b27d": (
            "KB-B024-YARA-AR2025",
            "million tonnes CO2e",
        ),
        "fact-b29593659bfa4855929a179b": ("KB-B024-TELENOR-AR2025", "headcount"),
        "fact-f55f010b8dd8689975e3f531": ("KB-B024-TELENOR-AR2025", "headcount"),
        "fact-32232e8ab521a7936180c2a9": ("KB-B024-TELENOR-AR2025", "headcount"),
        "fact-a9494da2f8301751ceb0831f": ("KB-B024-TELENOR-AR2025", "headcount"),
    }
    promoter.EXPECTED_CANDIDATES = 10
    promoter.BATCH_NUMBER = "024"
    promoter.STATUS = "scale_batch_024_six_dimension_tier_b_review_complete"
    promoter.BLOCKED_REASON = (
        "comparative_period_not_selected_or_native_literal_annotation_not_corroborated"
    )
    promoter.NEXT_GATE = "scale_batch_024_global_kb_rebuild_and_closure"
    promoter.ALLOWED_PERIODS = {
        "KB-B024-YARA-AR2025": {2025},
        "KB-B024-TELENOR-AR2025": {2025},
    }
    promoter.main()


if __name__ == "__main__":
    main()
