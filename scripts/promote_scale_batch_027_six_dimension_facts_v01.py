from __future__ import annotations

from pathlib import Path

import promote_scale_batch_019_six_dimension_facts_v01 as promoter

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    promoter.INCREMENT = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_027_atomic_fact_records.jsonl"
    )
    promoter.VALIDATIONS = (
        ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_027_atomic_validations.jsonl"
    )
    promoter.SUMMARY = ROOT / "data/results/scale_batch_027_tier_b_promotion.lock.json"
    promoter.NATIVE_AUDIT = (
        ROOT / "data/results/scale_batch_027_native_coordinate_audit.lock.json"
    )
    promoter.SOURCES = {
        "KB-B027-HANDELSBANKEN-AR2025": {
            "path": ROOT
            / "data/raw/scale_batch_027/handelsbanken-annual-report-2025.pdf",
            "sha256": "8679cdb160d9603f970eb6251546c8e6a1d98813a493bc4605f26cb933d88717",
            "assurance_pages": [142, 143],
            "scope": (
                "Svenska Handelsbanken AB statutory sustainability statement "
                "on pages 57–139 for financial year 2025"
            ),
            "quote": "The sustainability statement is included on pages 57-139",
            "issuer": "Svenska Handelsbanken AB (publ)",
            "period": "financial year 2025",
            "conclusion": "nothing has come to our attention",
            "signatory": "Malin Lüning",
        },
        "KB-B027-SECURITAS-AR2025": {
            "path": ROOT / "data/raw/scale_batch_027/securitas-annual-report-2025.pdf",
            "sha256": "e5d82427641d2dae5ed6f0bbe5c075827382c9bb5a2064a0aa3b4ec8a3991f95",
            "assurance_pages": [175, 176],
            "scope": (
                "Securitas AB sustainability statement on pages 59–105 "
                "for financial year 2025, excluding comparative 2024 figures"
            ),
            "quote": "The sustainability statement is included on pages 59–105",
            "issuer": "Securitas AB (publ)",
            "period": "for the financial year",
            "conclusion": "nothing has come to our attention",
            "signatory": "Rickard Andersson",
        },
    }
    promoter.PROMOTABLE = {
        "fact-61ff328fd86eeb88f9e4c656": (
            "KB-B027-HANDELSBANKEN-AR2025",
            "headcount",
        ),
        "fact-f54afb968c84d69bee01887c": (
            "KB-B027-HANDELSBANKEN-AR2025",
            "headcount",
        ),
        "fact-2accd027061c74eea8d97546": (
            "KB-B027-HANDELSBANKEN-AR2025",
            "headcount",
        ),
        "fact-42663e8e6d32d64f5ba3438d": (
            "KB-B027-SECURITAS-AR2025",
            "fatalities",
        ),
        "fact-c4a43028480c67e2e32c54ce": (
            "KB-B027-SECURITAS-AR2025",
            "fatalities",
        ),
        "fact-06f27fbab3e3a5384832271b": (
            "KB-B027-SECURITAS-AR2025",
            "fatalities",
        ),
        "fact-af9b61979eed0b55ab126fcf": (
            "KB-B027-SECURITAS-AR2025",
            "fatalities",
        ),
    }
    promoter.EXPECTED_CANDIDATES = 16
    promoter.BATCH_NUMBER = "027"
    promoter.STATUS = "scale_batch_027_six_dimension_tier_b_review_complete"
    promoter.BLOCKED_REASON = (
        "comparative_period_excluded_or_native_row_header_not_corroborated"
    )
    promoter.NEXT_GATE = "scale_batch_027_global_kb_rebuild_and_closure"
    promoter.ALLOWED_PERIODS = {
        "KB-B027-HANDELSBANKEN-AR2025": {2025},
        "KB-B027-SECURITAS-AR2025": {2025},
    }
    promoter.main()


if __name__ == "__main__":
    main()
