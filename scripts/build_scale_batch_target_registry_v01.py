from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "data/results/scale_batch_001_diagnostics.lock.json"
OUTPUT = ROOT / "data/manifests/scale_batch_001_target_pages.lock.json"


def page_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostics", type=Path, default=DIAGNOSTICS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--registry-id")
    args = parser.parse_args()
    diagnostics_path = args.diagnostics.resolve()
    output_path = args.output.resolve()
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    documents = []
    for document in diagnostics["documents"]:
        pages = (ROOT / document["layout_text_path"]).read_text(
            encoding="utf-8", errors="replace"
        ).split("\f")
        selected: dict[int, set[str]] = {}
        for theme, candidates in document["candidate_pages_by_theme"].items():
            if candidates:
                selected.setdefault(candidates[0]["page"], set()).add(theme)
        target_pages = [
            {
                "page": page,
                "themes": sorted(themes),
                "native_text_sha256": page_hash(pages[page - 1]),
                "native_text_characters": len(pages[page - 1].strip()),
            }
            for page, themes in sorted(selected.items())
        ]
        documents.append(
            {
                "document_id": document["document_id"],
                "source_group_id": document["source_group_id"],
                "local_path": document["local_path"],
                "document_sha256": document["sha256"],
                "selection_rule": "highest_keyword_hit_page_per_theme_v0.1",
                "target_pages": target_pages,
            }
        )
    payload = {
        "schema_version": "0.1",
        "registry_id": args.registry_id or "KB-SCALE-BATCH-001-TARGET-PAGES-v0.1",
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"locked {payload['totals']['unique_target_pages']} target pages")
    print(output_path)


if __name__ == "__main__":
    main()
