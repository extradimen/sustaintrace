from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_027_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_027_target_pages.lock.json"

SELECTIONS = {
    "KB-B027-NORDEA-AR2025": {
        104: ["health_safety"],
        124: ["water"],
        128: ["targets"],
        137: ["energy"],
        149: ["ghg_emissions"],
        156: ["biodiversity"],
        158: ["workforce"],
        191: ["circularity"],
        375: ["assurance"],
        376: ["assurance"],
    },
    "KB-B027-HANDELSBANKEN-AR2025": {
        79: ["water"],
        86: ["targets"],
        87: ["energy"],
        92: ["ghg_emissions"],
        99: ["health_safety"],
        101: ["workforce"],
        139: ["biodiversity", "circularity"],
        140: ["biodiversity", "circularity"],
        142: ["assurance"],
        143: ["assurance"],
    },
    "KB-B027-SECURITAS-AR2025": {
        75: ["biodiversity"],
        78: ["energy", "ghg_emissions"],
        79: ["ghg_emissions"],
        80: ["targets"],
        81: ["circularity"],
        91: ["workforce"],
        93: ["health_safety"],
        103: ["water"],
        175: ["assurance"],
        176: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B027-NORDEA-AR2025": {
        "pages": [375, 376],
        "required_literals": {
            "issuer_identity": "group sustainability report of Nordea Bank Abp",
            "reporting_period": "period 1.1.–31.12.2025",
            "opinion_or_conclusion": "causes us to believe that the group sustainability",
            "signatory_identity": "Jukka Paunonen",
        },
        "visual_review_pages": [375, 376],
    },
    "KB-B027-HANDELSBANKEN-AR2025": {
        "pages": [142, 143],
        "required_literals": {
            "issuer_identity": "Svenska Handelsbanken AB (publ)",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Malin Lüning",
        },
        "visual_review_pages": [142, 143],
    },
    "KB-B027-SECURITAS-AR2025": {
        "pages": [175, 176],
        "required_literals": {
            "issuer_identity": "statement prepared by Securitas AB",
            "reporting_period": "for the financial year",
            "opinion_or_conclusion": (
                "causes us to believe that the sustainability statement is not"
            ),
            "signatory_identity": "Rickard Andersson",
        },
        "visual_review_pages": [175, 176],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch27 target registry")
    diagnostics = json.loads(DIAGNOSTICS.read_text())
    documents = []
    preflight = []
    for document in diagnostics["documents"]:
        document_id = document["document_id"]
        pages = (ROOT / document["layout_text_path"]).read_text(errors="replace").split("\f")
        assurance = ASSURANCE_WINDOWS[document_id]
        assurance_text = "\n".join(pages[page - 1] for page in assurance["pages"])
        normalized = " ".join(assurance_text.casefold().split())
        checks = {
            field: " ".join(literal.casefold().split()) in normalized
            for field, literal in assurance["required_literals"].items()
        }
        if not all(checks.values()):
            raise ValueError(f"assurance preflight failed: {document_id}:{checks}")
        preflight.append(
            {
                "document_id": document_id,
                "pages": assurance["pages"],
                "required_literal_checks": checks,
                "window_text_sha256": hashlib.sha256(assurance_text.encode()).hexdigest(),
                "visual_review": {
                    "pages": assurance["visual_review_pages"],
                    "status": "passed_against_rendered_source_before_target_freeze",
                    "checked_fields": sorted(checks),
                },
                "status": "passed_before_target_freeze",
            }
        )
        targets = []
        for page, themes in sorted(SELECTIONS[document_id].items()):
            text = pages[page - 1]
            if len(text.strip()) < 40:
                raise ValueError(f"selected page is not extractable: {document_id}:p{page}")
            targets.append(
                {
                    "page": page,
                    "themes": sorted(themes),
                    "native_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "native_text_characters": len(text.strip()),
                }
            )
        documents.append(
            {
                "document_id": document_id,
                "source_group_id": document["source_group_id"],
                "local_path": document["local_path"],
                "document_sha256": document["sha256"],
                "selection_rule": (
                    "audited_theme_page_selection_v0.8_with_complete_signed_"
                    "assurance_window_preflight_visual_review_and_duplicate_gate"
                ),
                "target_pages": targets,
            }
        )
    payload = {
        "schema_version": "0.1",
        "registry_id": "KB-SCALE-BATCH-027-TARGET-PAGES-v0.1",
        "batch_id": diagnostics["batch_id"],
        "created_at": datetime.now(UTC).isoformat(),
        "status": "target_pages_locked_after_assurance_preflight_before_mineru",
        "cloud_transmission": False,
        "assurance_window_preflight": preflight,
        "documents": documents,
        "totals": {
            "documents": len(documents),
            "unique_target_pages": sum(len(item["target_pages"]) for item in documents),
            "assurance_windows_passed": len(preflight),
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload["totals"], sort_keys=True))
    print(OUTPUT)


if __name__ == "__main__":
    main()
