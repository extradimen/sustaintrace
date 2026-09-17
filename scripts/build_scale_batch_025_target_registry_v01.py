from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_025_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_025_target_pages.lock.json"

SELECTIONS = {
    "KB-B025-EQUINOR-AR2025": {
        101: ["targets"],
        112: ["energy"],
        113: ["ghg_emissions"],
        123: ["biodiversity"],
        128: ["circularity"],
        138: ["workforce"],
        162: ["health_safety"],
        305: ["assurance"],
        306: ["assurance"],
        307: ["assurance"],
    },
    "KB-B025-AKERBP-AR2025": {
        62: ["targets"],
        73: ["energy"],
        74: ["ghg_emissions"],
        85: ["water"],
        86: ["biodiversity"],
        94: ["circularity"],
        103: ["workforce"],
        110: ["health_safety"],
        126: ["assurance"],
        127: ["assurance"],
    },
    "KB-B025-DNB-AR2025": {
        83: ["targets"],
        94: ["health_safety"],
        124: ["energy"],
        134: ["ghg_emissions"],
        154: ["workforce"],
        202: ["biodiversity", "circularity"],
        350: ["assurance"],
        351: ["assurance"],
        352: ["assurance"],
        353: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B025-EQUINOR-AR2025": {
        "pages": [305, 306, 307],
        "required_literals": {
            "issuer_identity": "consolidated sustainability statement of Equinor ASA",
            "reporting_period": "as at 31 December 2025 and for the year then ended",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Tor Inge Skjellevik",
        },
        "visual_review_pages": [305, 307],
    },
    "KB-B025-AKERBP-AR2025": {
        "pages": [126, 127],
        "required_literals": {
            "issuer_identity": "consolidated sustainability statement of Aker BP ASA",
            "reporting_period": "at 31 December 2025 and for the year then ended",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Per Arvid Gimre",
        },
        "visual_review_pages": [126, 127],
    },
    "KB-B025-DNB-AR2025": {
        "pages": [350, 351, 352, 353],
        "required_literals": {
            "issuer_identity": "consolidated sustainability statement of DNB Bank ASA",
            "reporting_period": "as at 31 December 2025 and for the year then ended",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Kjetil Rimstad",
        },
        "visual_review_pages": [350, 353],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch25 target registry")
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
        "registry_id": "KB-SCALE-BATCH-025-TARGET-PAGES-v0.1",
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
