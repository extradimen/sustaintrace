from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/knowledge/scale_batch_001_RESUME01_v0.2.json"
DEFAULT_MANIFEST = ROOT / "data/manifests/scale_batch_001_acquisition.lock.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_pdf(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 5:
        return False
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def download_with_resume(url: str, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if is_pdf(destination):
        return {"download_status": "reused_verified_pdf", "resumed_from_bytes": 0}

    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "ESG-Reliable-Discovery/0.1"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=90)
    except urllib.error.HTTPError as exc:
        if offset and exc.code == 416:
            os.replace(partial, destination)
            return {
                "download_status": "completed_from_existing_partial",
                "resumed_from_bytes": offset,
            }
        raise

    status = getattr(response, "status", None)
    append = offset > 0 and status == 206
    if offset and not append:
        offset = 0
    with response, partial.open("ab" if append else "wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    if not is_pdf(partial):
        raise ValueError(f"downloaded object is not a PDF: {partial}")
    os.replace(partial, destination)
    return {"download_status": "downloaded", "resumed_from_bytes": offset}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    args.config = args.config.resolve()
    args.manifest = args.manifest.resolve()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    records = []
    for document in config["documents"]:
        destination = ROOT / document["local_path"]
        try:
            result = download_with_resume(document["download_url"], destination)
            records.append(
                {
                    "document_id": document["document_id"],
                    "local_path": document["local_path"],
                    "bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                    "pdf_header_valid": is_pdf(destination),
                    **result,
                }
            )
            print(f"{document['document_id']}: {destination.stat().st_size} bytes")
        except Exception as error:  # noqa: BLE001 - preserve per-source acquisition failures
            partial = destination.with_suffix(destination.suffix + ".part")
            records.append(
                {
                    "document_id": document["document_id"],
                    "local_path": document["local_path"],
                    "bytes": destination.stat().st_size if destination.exists() else 0,
                    "partial_bytes": partial.stat().st_size if partial.exists() else 0,
                    "sha256": sha256_file(destination) if is_pdf(destination) else None,
                    "pdf_header_valid": is_pdf(destination),
                    "download_status": "failed_preserved",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
            print(f"{document['document_id']}: failed: {type(error).__name__}: {error}")
    manifest = {
        "schema_version": "0.1",
        "batch_id": config["batch_id"],
        "created_at": datetime.now(UTC).isoformat(),
        "source_config": str(args.config.relative_to(ROOT)),
        "documents": records,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(args.manifest)


if __name__ == "__main__":
    main()
