from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_024_RESUME01_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_024_RESUME01_target_pages.lock.json"

SELECTIONS = {
    "KB-B024-FORTUM-FIN2025": {
        47: ["water"],
        56: ["energy", "targets"],
        63: ["ghg_emissions"],
        68: ["biodiversity"],
        73: ["circularity"],
        89: ["workforce"],
        92: ["health_safety"],
        231: ["assurance"],
        232: ["assurance"],
    },
    "KB-B024-YARA-AR2025": {
        111: ["energy"],
        112: ["ghg_emissions", "targets"],
        124: ["water"],
        126: ["biodiversity"],
        130: ["circularity"],
        135: ["health_safety"],
        151: ["workforce"],
        308: ["assurance"],
        309: ["assurance"],
        310: ["assurance"],
        311: ["assurance"],
    },
    "KB-B024-TELENOR-AR2025": {
        91: ["targets"],
        92: ["energy"],
        93: ["ghg_emissions"],
        98: ["biodiversity"],
        106: ["circularity"],
        116: ["workforce"],
        118: ["health_safety"],
        277: ["assurance"],
        278: ["assurance"],
        279: ["assurance"],
        280: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B024-FORTUM-FIN2025": {
        "pages": [231, 232],
        "required_literals": {
            "issuer_identity": "group sustainability statement of Fortum Oyj",
            "reporting_period": "reporting period 1.1.–31.12.2025",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Jukka Vattulainen",
        },
        "visual_review_pages": [231, 232],
    },
    "KB-B024-YARA-AR2025": {
        "pages": [308, 309, 310, 311],
        "required_literals": {
            "issuer_identity": "consolidated sustainability statement of Yara International ASA",
            "reporting_period": "as at 31 December 2025 and for the year then ended",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Espen Johansen",
        },
        "visual_review_pages": [308, 311],
    },
    "KB-B024-TELENOR-AR2025": {
        "pages": [277, 278, 279, 280],
        "required_literals": {
            "issuer_identity": "statement of Telenor ASA",
            "reporting_period": "as at 31 December 2025",
            "opinion_or_conclusion": "come to our attention",
            "signatory_identity": "Anders Gøbel",
        },
        "visual_review_pages": [277, 280],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch 24 RESUME01 target registry")
    diagnostics = json.loads(DIAGNOSTICS.read_text())
    documents = []
    preflight = []
    for document in diagnostics["documents"]:
        document_id = document["document_id"]
        pages = (ROOT / document["layout_text_path"]).read_text(errors="replace").split("\f")
        assurance = ASSURANCE_WINDOWS[document_id]
        assurance_text = "\n".join(pages[page - 1] for page in assurance["pages"])
        normalized_assurance_text = " ".join(assurance_text.casefold().split())
        checks = {
            field: " ".join(literal.casefold().split()) in normalized_assurance_text
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
                    "audited_theme_page_selection_v0.7_with_complete_signed_"
                    "assurance_window_preflight_visual_review_and_duplicate_gate"
                ),
                "target_pages": targets,
            }
        )
    payload = {
        "schema_version": "0.2",
        "registry_id": "KB-SCALE-BATCH-024-RESUME01-TARGET-PAGES-v0.1",
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
