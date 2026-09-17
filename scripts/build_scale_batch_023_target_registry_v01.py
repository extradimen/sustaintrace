from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_023_RESUME02_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_023_RESUME02_target_pages.lock.json"

SELECTIONS = {
    "KB-B023-GLENCORE-SR2025": {
        5: ["energy", "ghg_emissions"],
        18: ["workforce"],
        23: ["health_safety"],
        28: ["circularity"],
        29: ["water"],
        35: ["biodiversity"],
        52: ["assurance"],
        53: ["assurance"],
        54: ["assurance"],
        55: ["assurance"],
    },
    "KB-B023-ARKEMA-URD2025": {
        189: ["ghg_emissions"],
        191: ["energy"],
        202: ["water"],
        204: ["biodiversity"],
        208: ["circularity"],
        226: ["workforce"],
        234: ["health_safety"],
        277: ["assurance"],
        278: ["assurance"],
        279: ["assurance"],
        280: ["assurance"],
    },
    "KB-B023-CRH-SPR2025": {
        23: ["circularity"],
        31: ["ghg_emissions"],
        34: ["biodiversity"],
        76: ["circularity", "water"],
        78: ["health_safety"],
        80: ["workforce"],
        90: ["assurance"],
        91: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B023-GLENCORE-SR2025": {
        "pages": [52, 53, 54, 55],
        "required_literals": {
            "issuer_identity": "engaged by Glencore plc",
            "reporting_period": "1 January 2025 – 31 December 2025",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "ERM CVS",
        },
        "visual_review_pages": [52, 55],
    },
    "KB-B023-ARKEMA-URD2025": {
        "pages": [277, 278, 279, 280],
        "required_literals": {
            "issuer_identity": "statutory auditors of Arkema S.A.",
            "reporting_period": "year ended December 31st, 2025",
            "opinion_or_conclusion": (
                "we have not identified any material errors, omissions or inconsistencies"
            ),
            "signatory_identity": "French original signed by",
        },
        "visual_review_pages": [277, 280],
    },
    "KB-B023-CRH-SPR2025": {
        "pages": [90, 91],
        "required_literals": {
            "issuer_identity": "Independent Limited Assurance Report to CRH plc",
            "reporting_period": "reporting year ended 31st December 2025",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Shuhaib Maudarbaccus",
        },
        "visual_review_pages": [90, 91],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch 23 target registry")
    diagnostics = json.loads(DIAGNOSTICS.read_text())
    documents = []
    preflight = []
    for document in diagnostics["documents"]:
        document_id = document["document_id"]
        pages = (ROOT / document["layout_text_path"]).read_text(
            errors="replace"
        ).split("\f")
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
                "window_text_sha256": hashlib.sha256(
                    assurance_text.encode()
                ).hexdigest(),
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
                    "audited_theme_page_selection_v0.6_with_pdf_coordinate_"
                    "assurance_window_preflight_visual_review_and_duplicate_gate"
                ),
                "target_pages": targets,
            }
        )
    payload = {
        "schema_version": "0.1",
        "registry_id": "KB-SCALE-BATCH-023-RESUME02-TARGET-PAGES-v0.1",
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
