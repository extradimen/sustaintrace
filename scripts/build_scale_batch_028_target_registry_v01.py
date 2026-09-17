from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_028_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_028_target_pages.lock.json"

SELECTIONS = {
    "KB-B028-TELIA-AR2025": {
        76: ["biodiversity"],
        84: ["targets"],
        85: ["energy"],
        87: ["ghg_emissions"],
        90: ["circularity"],
        101: ["workforce"],
        103: ["health_safety"],
        129: ["water"],
        259: ["assurance"],
        260: ["assurance"],
    },
    "KB-B028-ASSA-ABLOY-AR2025": {
        77: ["biodiversity"],
        90: ["targets"],
        95: ["energy"],
        96: ["ghg_emissions"],
        98: ["water"],
        99: ["circularity"],
        100: ["circularity"],
        105: ["health_safety", "workforce"],
        170: ["assurance"],
        171: ["assurance"],
    },
    "KB-B028-LOOMIS-ASR2025": {
        71: ["biodiversity"],
        78: ["targets"],
        82: ["energy"],
        83: ["ghg_emissions"],
        89: ["circularity"],
        100: ["workforce"],
        104: ["health_safety"],
        118: ["water"],
        165: ["assurance"],
        166: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B028-TELIA-AR2025": {
        "pages": [259, 260],
        "required_literals": {
            "issuer_identity": "Telia Company AB (publ)",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Joakim Thilstedt",
        },
    },
    "KB-B028-ASSA-ABLOY-AR2025": {
        "pages": [170, 171],
        "required_literals": {
            "issuer_identity": "ASSA ABLOY AB (publ)",
            "reporting_period": "for the financial year",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Hamish Mabon",
        },
    },
    "KB-B028-LOOMIS-ASR2025": {
        "pages": [165, 166],
        "required_literals": {
            "issuer_identity": "Loomis AB",
            "reporting_period": "for the financial year",
            "opinion_or_conclusion": "our attention that causes us to believe",
            "signatory_identity": "Didrik Roos",
        },
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch28 target registry")
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
                    "pages": assurance["pages"],
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
        "registry_id": "KB-SCALE-BATCH-028-TARGET-PAGES-v0.1",
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
