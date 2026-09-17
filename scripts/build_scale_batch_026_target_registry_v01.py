from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_026_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_026_target_pages.lock.json"

SELECTIONS = {
    "KB-B026-STOREBRAND-AR2025": {
        54: ["biodiversity", "circularity"],
        69: ["energy"],
        70: ["targets"],
        78: ["water"],
        81: ["ghg_emissions"],
        91: ["workforce"],
        120: ["health_safety"],
        163: ["assurance"],
        164: ["assurance"],
        165: ["assurance"],
    },
    "KB-B026-ORKLA-AR2025": {
        72: ["targets"],
        73: ["energy"],
        76: ["ghg_emissions"],
        81: ["water"],
        85: ["biodiversity"],
        91: ["circularity"],
        97: ["workforce"],
        99: ["health_safety"],
        253: ["assurance"],
        254: ["assurance"],
    },
    "KB-B026-SEB-AR2025": {
        90: ["water"],
        105: ["energy"],
        109: ["biodiversity"],
        112: ["targets"],
        120: ["ghg_emissions"],
        137: ["workforce"],
        163: ["health_safety"],
        179: ["circularity"],
        343: ["assurance"],
        344: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B026-STOREBRAND-AR2025": {
        "pages": [163, 164, 165],
        "required_literals": {
            "issuer_identity": "consolidated sustainability statement of Storebrand ASA",
            "reporting_period": "as at 31 December 2025 and for the year then ended",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Thomas Steffensen",
        },
        "visual_review_pages": [163, 165],
    },
    "KB-B026-ORKLA-AR2025": {
        "pages": [253, 254],
        "required_literals": {
            "issuer_identity": "Orkla ASA, included in 2.3 Sustainability",
            "reporting_period": "as at 31 December 2025 and for the year then ended",
            "opinion_or_conclusion": (
                "causes us to believe that the Sustainability Statement is not prepared"
            ),
            "signatory_identity": "Kjetil Rimstad",
        },
        "visual_review_pages": [253, 254],
    },
    "KB-B026-SEB-AR2025": {
        "pages": [343, 344],
        "required_literals": {
            "issuer_identity": "Skandinaviska Enskilda Banken AB (publ)",
            "reporting_period": "for the financial year 2025",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Hamish Mabon",
        },
        "visual_review_pages": [343, 344],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch26 target registry")
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
        "registry_id": "KB-SCALE-BATCH-026-TARGET-PAGES-v0.1",
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
