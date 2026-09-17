from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_016_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_016_target_pages.lock.json"

SELECTIONS = {
    "KB-B016-AKZONOBEL-AR2025": {
        24: ["targets"],
        45: ["energy"],
        46: ["ghg_emissions"],
        49: ["water"],
        74: ["circularity"],
        75: ["workforce", "health_safety"],
        77: ["biodiversity"],
        224: ["assurance"],
        226: ["assurance"],
    },
    "KB-B016-NOVONESIS-AR2025": {
        71: ["targets"],
        74: ["energy"],
        75: ["ghg_emissions"],
        83: ["water"],
        85: ["biodiversity"],
        87: ["circularity"],
        96: ["workforce"],
        99: ["health_safety"],
        197: ["assurance"],
        199: ["assurance"],
    },
    "KB-B016-COLOPLAST-AR2025": {
        48: ["water"],
        55: ["targets"],
        60: ["energy"],
        61: ["ghg_emissions"],
        69: ["circularity"],
        72: ["biodiversity"],
        79: ["health_safety"],
        85: ["workforce"],
        162: ["assurance"],
        164: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B016-AKZONOBEL-AR2025": {
        "pages": [224, 226],
        "required_literals": {
            "issuer_identity": "Akzo Nobel N.V.",
            "reporting_period": "for 2025",
            "opinion_or_conclusion": "Limited assurance conclusion",
            "signatory_identity": "D. van Ameijden",
        },
    },
    "KB-B016-NOVONESIS-AR2025": {
        "pages": [197, 199],
        "required_literals": {
            "issuer_identity": "Novonesis A/S",
            "reporting_period": "January 1 – December 31, 2025",
            "opinion_or_conclusion": "Limited assurance conclusion",
            "signatory_identity": "Lars Fermann",
        },
    },
    "KB-B016-COLOPLAST-AR2025": {
        "pages": [162, 164],
        "required_literals": {
            "issuer_identity": "Coloplast A/S",
            "reporting_period": "1 October 2024 – 30 September 2025",
            "opinion_or_conclusion": "Limited assurance conclusion",
            "signatory_identity": "Margrethe B. Bergkvist",
        },
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch16 target registry")
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
                    "audited_theme_page_selection_v0.3_with_assurance_window_preflight"
                ),
                "target_pages": targets,
            }
        )
    payload = {
        "schema_version": "0.1",
        "registry_id": "KB-SCALE-BATCH-016-TARGET-PAGES-v0.1",
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
