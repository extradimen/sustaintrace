from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_015_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_015_target_pages.lock.json"

SELECTIONS = {
    "KB-B015-UCB-IAR2025": {
        55: ["targets"],
        59: ["energy"],
        60: ["ghg_emissions"],
        68: ["water", "biodiversity"],
        71: ["circularity"],
        88: ["workforce"],
        90: ["health_safety"],
        125: ["assurance"],
        127: ["assurance"],
    },
    "KB-B015-ARLA-AR2025": {
        38: ["water"],
        45: ["targets"],
        47: ["energy"],
        48: ["ghg_emissions"],
        53: ["biodiversity"],
        59: ["circularity"],
        69: ["workforce"],
        70: ["health_safety"],
        161: ["assurance"],
        162: ["assurance"],
    },
    "KB-B015-FRESENIUS-AR2025": {
        188: ["biodiversity"],
        207: ["targets"],
        208: ["energy"],
        213: ["ghg_emissions"],
        221: ["water"],
        223: ["circularity"],
        249: ["workforce"],
        255: ["health_safety"],
        431: ["assurance"],
        434: ["assurance"],
    },
}

ASSURANCE_WINDOWS = {
    "KB-B015-UCB-IAR2025": {
        "pages": [125, 127],
        "required_literals": {
            "issuer_identity": "UCB SA",
            "reporting_period": "year ended on that date",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Sébastien Schueremans",
        },
    },
    "KB-B015-ARLA-AR2025": {
        "pages": [161, 162],
        "required_literals": {
            "issuer_identity": "Arla Foods amba",
            "reporting_period": "financial year 1 January - 31 December 2025",
            "opinion_or_conclusion": "Limited assurance conclusion",
            "signatory_identity": "Monica Mai Bak Larsen",
        },
    },
    "KB-B015-FRESENIUS-AR2025": {
        "pages": [431, 434],
        "required_literals": {
            "issuer_identity": "Fresenius SE & Co. KGaA",
            "reporting_period": "report for the financial year from 1 January to 31 December",
            "reporting_year": "2025",
            "opinion_or_conclusion": "nothing has come to our attention",
            "signatory_identity": "Aissata Touré",
        },
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch15 target registry")
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
        "registry_id": "KB-SCALE-BATCH-015-TARGET-PAGES-v0.1",
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
