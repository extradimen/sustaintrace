from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_013_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_013_target_pages.lock.json"

SELECTIONS = {
    "KB-B013-WARTSILA-AR2025": {
        101: ["water", "biodiversity", "circularity"],
        117: ["targets"],
        123: ["energy"],
        124: ["ghg_emissions"],
        129: ["workforce"],
        132: ["health_safety"],
        226: ["assurance"],
    },
    "KB-B013-ELECTROLUX-AR2025": {
        90: ["targets", "ghg_emissions"],
        91: ["energy"],
        98: ["water"],
        101: ["biodiversity"],
        106: ["circularity"],
        113: ["workforce"],
        116: ["health_safety"],
        130: ["assurance"],
    },
    "KB-B013-SKF-ASR2025": {
        42: ["water", "biodiversity"],
        58: ["targets"],
        59: ["energy"],
        61: ["ghg_emissions"],
        68: ["circularity"],
        77: ["workforce"],
        79: ["health_safety"],
        96: ["assurance"],
    },
}


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite frozen Batch13 target registry")
    diagnostics = json.loads(DIAGNOSTICS.read_text())
    documents = []
    for document in diagnostics["documents"]:
        document_id = document["document_id"]
        pages = (ROOT / document["layout_text_path"]).read_text(errors="replace").split("\f")
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
                    "audited_theme_page_selection_v0.2_with_explicit_nonmaterial_topic_pages"
                ),
                "target_pages": targets,
            }
        )
    payload = {
        "schema_version": "0.1",
        "registry_id": "KB-SCALE-BATCH-013-TARGET-PAGES-v0.1",
        "batch_id": diagnostics["batch_id"],
        "created_at": datetime.now(UTC).isoformat(),
        "status": "target_pages_locked_before_mineru",
        "cloud_transmission": False,
        "documents": documents,
        "totals": {
            "documents": len(documents),
            "unique_target_pages": sum(len(item["target_pages"]) for item in documents),
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"locked {payload['totals']['unique_target_pages']} target pages")
    print(OUTPUT)


if __name__ == "__main__":
    main()
