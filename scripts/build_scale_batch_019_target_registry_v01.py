from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_019_RESUME01_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_019_target_pages.lock.json"

SELECTIONS = {
    "KB-B019-NESTE-AR2025": {
        36: ["ghg_emissions", "targets"],
        37: ["energy", "circularity"],
        39: ["health_safety"],
        40: ["workforce"],
        41: ["workforce"],
        50: ["assurance"],
        51: ["assurance"],
        110: ["energy", "ghg_emissions"],
        117: ["biodiversity"],
        121: ["circularity"],
    },
    "KB-B019-BOLIDEN-ASR2025": {
        78: ["ghg_emissions", "targets"],
        80: ["energy"],
        81: ["ghg_emissions"],
        90: ["water"],
        91: ["biodiversity"],
        95: ["circularity"],
        105: ["workforce"],
        108: ["health_safety"],
        122: ["assurance"],
        123: ["assurance"],
    },
    "KB-B019-METSO-AR2025": {
        86: ["ghg_emissions", "targets"],
        94: ["ghg_emissions", "energy"],
        98: ["water"],
        102: ["biodiversity"],
        106: ["circularity"],
        115: ["workforce"],
        117: ["health_safety"],
        239: ["assurance"],
        240: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B019-NESTE-AR2025": {
        "pages": [50, 51],
        "required_literals": {
            "issuer_identity": "Neste Oyj",
            "reporting_period": "reporting period January 1–December 31, 2025",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Leenakaisa Winberg",
        },
    },
    "KB-B019-BOLIDEN-ASR2025": {
        "pages": [122, 123],
        "required_literals": {
            "issuer_identity": "Boliden AB (publ)",
            "reporting_period": "sustainability statement for the year 2025",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Anna Rosendal",
        },
    },
    "KB-B019-METSO-AR2025": {
        "pages": [239, 240],
        "required_literals": {
            "issuer_identity": "Metso Corporation",
            "reporting_period": "reporting period 1.1.–31.12.2025",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Toni Halonen",
        },
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch19 target registry")
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
        "registry_id": "KB-SCALE-BATCH-019-TARGET-PAGES-v0.1",
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
