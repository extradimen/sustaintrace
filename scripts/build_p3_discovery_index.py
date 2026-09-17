#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--pdftotext", default="pdftotext")
    args = parser.parse_args()

    source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    args.output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for source in source_manifest["accepted_sources"]:
        pdf = Path(source["local_path"])
        actual_hash = sha256_file(pdf)
        if actual_hash != source["sha256"]:
            raise SystemExit(f"Source hash mismatch: {source['source_id']}")
        output = args.output_root / f"{source['source_id']}.pages.jsonl"
        with tempfile.TemporaryDirectory(prefix="esg-p3-index-") as temp_dir:
            text_path = Path(temp_dir) / "document.txt"
            subprocess.run(
                [args.pdftotext, "-enc", "UTF-8", pdf, text_path],
                check=True,
                capture_output=True,
                text=True,
            )
            pages = text_path.read_text(encoding="utf-8", errors="replace").split("\f")
        if pages and not pages[-1].strip():
            pages.pop()
        with output.open("w", encoding="utf-8") as handle:
            for page_number, text in enumerate(pages, start=1):
                handle.write(
                    json.dumps(
                        {
                            "source_id": source["source_id"],
                            "pdf_page": page_number,
                            "text": text,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
        if len(pages) != source["pages"]:
            raise SystemExit(
                f"Page count mismatch: {source['source_id']} "
                f"expected={source['pages']} actual={len(pages)}"
            )
        records.append(
            {
                "source_id": source["source_id"],
                "source_sha256": actual_hash,
                "page_count": len(pages),
                "index_path": output.as_posix(),
                "index_sha256": sha256_file(output),
                "text_character_count": sum(len(page) for page in pages),
            }
        )
    index_manifest = {
        "schema_version": "1.0",
        "status": "deterministic_discovery_index_completed",
        "source_manifest": args.source_manifest.as_posix(),
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "candidate_evidence_admissible": False,
        "records": records,
    }
    manifest_path = args.output_root / "index_manifest.json"
    manifest_path.write_text(
        json.dumps(index_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "source_count": len(records),
                "page_count": sum(int(item["page_count"]) for item in records),
                "manifest": manifest_path.as_posix(),
                "manifest_sha256": sha256_file(manifest_path),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
