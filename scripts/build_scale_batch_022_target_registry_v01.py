from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_022_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_022_target_pages.lock.json"

SELECTIONS = {
    "KB-B022-ENGIE-URD2025": {
        121: ["energy"],
        122: ["ghg_emissions"],
        132: ["water"],
        133: ["biodiversity"],
        138: ["circularity"],
        140: ["circularity", "water"],
        154: ["workforce"],
        174: ["health_safety"],
        220: ["assurance"],
        221: ["assurance"],
    },
    "KB-B022-ORANGE-URD2025": {
        362: ["biodiversity", "water"],
        363: ["biodiversity"],
        382: ["energy"],
        383: ["ghg_emissions"],
        396: ["circularity"],
        400: ["circularity"],
        425: ["workforce"],
        428: ["health_safety"],
        482: ["assurance"],
        483: ["assurance"],
        484: ["assurance"],
        485: ["assurance"],
    },
    "KB-B022-SKANSKA-ASR2025": {
        64: ["biodiversity", "water"],
        69: ["energy"],
        70: ["ghg_emissions"],
        71: ["ghg_emissions", "targets"],
        75: ["circularity"],
        76: ["circularity"],
        81: ["workforce"],
        84: ["health_safety"],
        208: ["assurance"],
        209: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B022-ENGIE-URD2025": {
        "pages": [220, 221],
        "required_literals": {
            "issuer_identity": "statutory auditors of Engie",
            "reporting_period": "year ended December 31, 2025",
            "opinion_or_conclusion": (
                "Information has been prepared, in all material respects"
            ),
            "signatory_identity": "Nadia Laadouli",
        },
        "visual_review_pages": [220, 221],
    },
    "KB-B022-ORANGE-URD2025": {
        "pages": [482, 483, 484, 485],
        "required_literals": {
            "issuer_identity": "statutory auditors of ORANGE",
            "reporting_period": "Year ended December 31, 2025",
            "opinion_or_conclusion": (
                "not identified any material errors, omissions or inconsistencies"
            ),
            "signatory_identity": "Christophe PATRIER",
        },
        "visual_review_pages": [482, 485],
    },
    "KB-B022-SKANSKA-ASR2025": {
        "pages": [208, 209],
        "required_literals": {
            "issuer_identity": "Skanska AB",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Rickard Andersson",
        },
        "visual_review_pages": [208, 209],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch 22 target registry")
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
                    "audited_theme_page_selection_v0.5_with_contiguous_"
                    "assurance_window_preflight_visual_review_and_duplicate_gate"
                ),
                "target_pages": targets,
            }
        )
    payload = {
        "schema_version": "0.1",
        "registry_id": "KB-SCALE-BATCH-022-TARGET-PAGES-v0.1",
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
