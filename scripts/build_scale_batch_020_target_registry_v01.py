from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_020_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_020_target_pages.lock.json"

SELECTIONS = {
    "KB-B020-SOLVAY-AIR2025": {
        143: ["energy", "targets"],
        145: ["ghg_emissions", "targets"],
        166: ["water"],
        167: ["biodiversity"],
        170: ["circularity"],
        177: ["workforce"],
        180: ["health_safety"],
        322: ["assurance"],
        323: ["assurance"],
        324: ["assurance"],
        325: ["assurance"],
    },
    "KB-B020-KERING-URD2025": {
        201: ["energy"],
        207: ["ghg_emissions", "targets"],
        219: ["water"],
        223: ["biodiversity"],
        234: ["circularity"],
        263: ["workforce"],
        265: ["health_safety"],
        303: ["assurance"],
        304: ["assurance"],
        305: ["assurance"],
        306: ["assurance"],
    },
    "KB-B020-CARREFOUR-URD2025": {
        98: ["ghg_emissions", "targets"],
        102: ["energy"],
        122: ["water"],
        126: ["biodiversity"],
        143: ["circularity"],
        165: ["workforce"],
        183: ["health_safety"],
        238: ["assurance"],
        239: ["assurance"],
        240: ["assurance"],
        241: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B020-SOLVAY-AIR2025": {
        "pages": [322, 323, 324, 325],
        "required_literals": {
            "issuer_identity": "consolidated sustainability statement of Solvay SA",
            "reporting_period": "as of 31 December 2025 and for the year ended on that date",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Eric Van Hoof",
        },
        "visual_review_pages": [322, 325],
    },
    "KB-B020-KERING-URD2025": {
        "pages": [303, 304, 305, 306],
        "required_literals": {
            "issuer_identity": "statutory auditor of Kering",
            "reporting_period": "relating to the year ended 31 December 2025",
            "opinion_or_conclusion": (
                "we have not identified any material errors, omissions or inconsistencies"
            ),
            "signatory_identity": "Patrice Morot",
        },
        "visual_review_pages": [303, 306],
    },
    "KB-B020-CARREFOUR-URD2025": {
        "pages": [238, 239, 240, 241],
        "required_literals": {
            "issuer_identity": "Shareholder’s Meeting of Carrefour SA",
            "reporting_period": "relating to the year ended December 31, 2025",
            "opinion_or_conclusion": (
                "we have not identified material errors, omissions or inconsistencies"
            ),
            "signatory_identity": "Olivier BROISSAND",
        },
        "visual_review_pages": [238, 241],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch 20 target registry")
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
        "registry_id": "KB-SCALE-BATCH-020-TARGET-PAGES-v0.1",
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
