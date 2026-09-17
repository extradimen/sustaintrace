from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_017_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_017_target_pages.lock.json"

SELECTIONS = {
    "KB-B017-ROCKWOOL-AR2025": {
        12: ["targets"],
        68: ["energy", "ghg_emissions"],
        76: ["water"],
        80: ["circularity"],
        85: ["biodiversity"],
        89: ["health_safety"],
        91: ["workforce"],
        166: ["assurance"],
        168: ["assurance"],
    },
    "KB-B017-HUSQVARNA-AR2025": {
        38: ["targets"],
        50: ["ghg_emissions"],
        52: ["energy", "water"],
        54: ["circularity"],
        60: ["health_safety", "workforce"],
        67: ["biodiversity"],
        124: ["assurance"],
        125: ["assurance"],
    },
    "KB-B017-SWECO-AR2025": {
        70: ["targets"],
        73: ["energy"],
        74: ["ghg_emissions"],
        77: ["water"],
        78: ["biodiversity"],
        80: ["circularity"],
        91: ["workforce"],
        95: ["health_safety"],
        176: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B017-ROCKWOOL-AR2025": {
        "pages": [166, 168],
        "required_literals": {
            "issuer_identity": "ROCKWOOL A/S",
            "reporting_period": "January – 31 December 2025",
            "opinion_or_conclusion": "Limited assurance conclusion",
            "signatory_identity": "Kim Tromholt",
        },
    },
    "KB-B017-HUSQVARNA-AR2025": {
        "pages": [124, 125],
        "required_literals": {
            "issuer_identity": "Husqvarna AB (publ)",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Joakim Thilstedt",
        },
    },
    "KB-B017-SWECO-AR2025": {
        "pages": [176],
        "required_literals": {
            "issuer_identity": "Sweco AB (publ)",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Jonas Svensson",
        },
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch17 target registry")
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
        "registry_id": "KB-SCALE-BATCH-017-TARGET-PAGES-v0.1",
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
