from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_014_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_014_target_pages.lock.json"

SELECTIONS = {
    "KB-B014-SCA-AR2025": {
        124: ["targets"],
        127: ["energy"],
        128: ["ghg_emissions"],
        139: ["water"],
        147: ["biodiversity"],
        149: ["circularity"],
        154: ["workforce"],
        156: ["health_safety"],
        223: ["assurance"],
        224: ["assurance"],
    },
    "KB-B014-TRELLEBORG-AR2025": {
        62: ["water", "biodiversity"],
        68: ["targets"],
        71: ["energy"],
        72: ["ghg_emissions"],
        79: ["circularity"],
        82: ["workforce"],
        84: ["health_safety"],
        163: ["assurance"],
    },
    "KB-B014-ESSITY-AR2025": {
        65: ["targets"],
        66: ["energy"],
        68: ["ghg_emissions"],
        70: ["water"],
        72: ["biodiversity"],
        75: ["circularity"],
        82: ["workforce"],
        84: ["health_safety"],
        184: ["assurance"],
        185: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B014-SCA-AR2025": {
        "pages": [223, 224],
        "required_literals": {
            "issuer_identity": "Svenska Cellulosa Aktiebolaget",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "Conclusion",
            "signatory_identity": "Fredrik Norrman",
        },
    },
    "KB-B014-TRELLEBORG-AR2025": {
        "pages": [163],
        "required_literals": {
            "issuer_identity": "Trelleborg AB",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "Conclusion",
            "signatory_identity": "Fredrik Norrman",
        },
    },
    "KB-B014-ESSITY-AR2025": {
        "pages": [184, 185],
        "required_literals": {
            "issuer_identity": "Essity Aktiebolag",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "Conclusion",
            "signatory_identity": "Erik Sandström",
        },
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch14 target registry")
    diagnostics = json.loads(DIAGNOSTICS.read_text())
    documents = []
    preflight = []
    for document in diagnostics["documents"]:
        document_id = document["document_id"]
        pages = (ROOT / document["layout_text_path"]).read_text(errors="replace").split("\f")
        assurance = ASSURANCE_WINDOWS[document_id]
        assurance_text = "\n".join(pages[page - 1] for page in assurance["pages"])
        checks = {
            field: literal.casefold() in assurance_text.casefold()
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
        "registry_id": "KB-SCALE-BATCH-014-TARGET-PAGES-v0.1",
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
