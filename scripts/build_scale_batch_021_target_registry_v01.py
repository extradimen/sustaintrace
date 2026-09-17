from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_021_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_021_target_pages.lock.json"

SELECTIONS = {
    "KB-B021-CAPGEMINI-URD2025": {
        197: ["energy"],
        200: ["ghg_emissions"],
        211: ["circularity"],
        214: ["biodiversity"],
        216: ["water"],
        233: ["workforce"],
        256: ["health_safety"],
        317: ["assurance"],
        318: ["assurance"],
        319: ["assurance"],
        320: ["assurance"],
    },
    "KB-B021-REXEL-URD2025": {
        226: ["biodiversity"],
        261: ["ghg_emissions", "targets"],
        266: ["energy"],
        269: ["circularity"],
        277: ["health_safety"],
        292: ["workforce"],
        340: ["assurance"],
        341: ["assurance"],
        342: ["assurance"],
        343: ["assurance"],
        344: ["assurance"],
        347: ["water"],
    },
    "KB-B021-EIFFAGE-URD2025": {
        114: ["energy"],
        117: ["ghg_emissions", "targets"],
        126: ["water"],
        127: ["biodiversity"],
        144: ["circularity"],
        157: ["workforce"],
        215: ["health_safety"],
        218: ["assurance"],
        219: ["assurance"],
        220: ["assurance"],
        221: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B021-CAPGEMINI-URD2025": {
        "pages": [317, 318, 319, 320],
        "required_literals": {
            "issuer_identity": "statutory auditor of Capgemini SE",
            "reporting_period": "relating to the year ended December 31, 2025",
            "opinion_or_conclusion": (
                "we have not identified material errors, omissions or inconsistencies"
            ),
            "signatory_identity": "Anne-Laure Rousselou",
        },
        "visual_review_pages": [317, 320],
    },
    "KB-B021-REXEL-URD2025": {
        "pages": [340, 341, 342, 343, 344],
        "required_literals": {
            "issuer_identity": "auditors of Rexel SA",
            "reporting_period": "Year ended December 31, 2025",
            "opinion_or_conclusion": "have not identified material errors",
            "signatory_identity": "François Jaumain",
        },
        "visual_review_pages": [340, 344],
    },
    "KB-B021-EIFFAGE-URD2025": {
        "pages": [218, 219, 220, 221],
        "required_literals": {
            "issuer_identity": "the Eiffage Group. It includes",
            "reporting_period": "for the year ended 31 December 2025",
            "opinion_or_conclusion": "have not identified any",
            "signatory_identity": "Marc de Villartay",
        },
        "visual_review_pages": [218, 221],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch 21 target registry")
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
                    "audited_theme_page_selection_v0.4_with_contiguous_"
                    "assurance_window_preflight_and_visual_review"
                ),
                "target_pages": targets,
            }
        )
    payload = {
        "schema_version": "0.1",
        "registry_id": "KB-SCALE-BATCH-021-TARGET-PAGES-v0.1",
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
