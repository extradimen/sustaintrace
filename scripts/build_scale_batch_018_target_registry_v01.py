from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_018_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_018_target_pages.lock.json"

SELECTIONS = {
    "KB-B018-EPIROC-ASR2025": {
        41: ["targets"],
        93: ["water", "biodiversity"],
        106: ["energy", "ghg_emissions"],
        108: ["ghg_emissions"],
        117: ["circularity"],
        128: ["health_safety"],
        132: ["workforce"],
        233: ["assurance"],
        234: ["assurance"],
        235: ["assurance"],
    },
    "KB-B018-ALFA-LAVAL-ASR2025": {
        33: ["targets"],
        34: ["energy"],
        35: ["ghg_emissions"],
        38: ["water"],
        42: ["circularity"],
        61: ["health_safety", "workforce"],
        64: ["biodiversity"],
        145: ["assurance"],
        146: ["assurance"],
    },
    "KB-B018-SSAB-AR2025": {
        80: ["targets"],
        84: ["ghg_emissions"],
        86: ["energy"],
        92: ["circularity"],
        96: ["water", "biodiversity"],
        104: ["workforce"],
        106: ["health_safety"],
        183: ["assurance"],
        184: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B018-EPIROC-ASR2025": {
        "pages": [233, 234, 235],
        "required_literals": {
            "issuer_identity": "Epiroc AB",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Erik Sandström",
        },
    },
    "KB-B018-ALFA-LAVAL-ASR2025": {
        "pages": [145, 146],
        "required_literals": {
            "issuer_identity": "Alfa Laval AB",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Andreas Troberg",
        },
    },
    "KB-B018-SSAB-AR2025": {
        "pages": [183, 184],
        "required_literals": {
            "issuer_identity": "SSAB AB (publ)",
            "reporting_period": "financial year 2025",
            "opinion_or_conclusion": "nothing has come",
            "signatory_identity": "Rickard Andersson",
        },
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch18 target registry")
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
        "registry_id": "KB-SCALE-BATCH-018-TARGET-PAGES-v0.1",
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
