from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .hashing import sha256_file


class IngestionError(RuntimeError):
    """Raised when a source document cannot be safely registered."""


def _page_count(path: Path) -> int:
    try:
        result = subprocess.run(
            ["pdfinfo", str(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise IngestionError(f"pdfinfo failed for {path}") from error
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    if not match:
        raise IngestionError(f"pdfinfo returned no page count for {path}")
    return int(match.group(1))


def _download_pdf(
    url: str, destination: Path, *, landing_page_url: str | None = None
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36 "
            "ESG-Reliable-Discovery/0.1"
        ),
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
    }
    if landing_page_url:
        headers["Referer"] = landing_page_url
    request = urllib.request.Request(url, headers=headers)
    digest = hashlib.sha256()
    byte_count = 0
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".part", delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    content_type = response.headers.get_content_type()
                    resolved_url = response.geturl()
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
                        digest.update(chunk)
                        byte_count += len(chunk)
            except urllib.error.HTTPError as error:
                raise IngestionError(f"HTTP {error.code} while downloading {url}") from error
            except (urllib.error.URLError, TimeoutError) as error:
                reason = getattr(error, "reason", str(error))
                raise IngestionError(
                    f"Network failure while downloading {url}: {reason}"
                ) from error
            with temporary.open("rb") as check:
                if check.read(5) != b"%PDF-":
                    raise IngestionError(f"Source is not a PDF: {url}")
            pages = _page_count(temporary)
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    return {
        "sha256": digest.hexdigest(),
        "bytes": byte_count,
        "page_count": pages,
        "content_type": content_type,
        "resolved_url": resolved_url,
    }


def ingest_document(
    manifest_path: str | Path, document_id: str, raw_root: str | Path
) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in manifest["documents"] if item["document_id"] == document_id]
    if len(matches) != 1:
        raise IngestionError(f"Expected one manifest entry for {document_id}, found {len(matches)}")
    record = matches[0]
    if record["ingestion_status"] not in {"planned", "downloaded"}:
        raise IngestionError(
            f"Cannot ingest {document_id} with status {record['ingestion_status']}"
        )
    relative_path = Path(record.get("local_path") or f"{document_id}.pdf")
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise IngestionError("local_path must remain inside raw_root")
    destination = Path(raw_root) / relative_path
    metadata = _download_pdf(
        record["source_url"],
        destination,
        landing_page_url=record.get("landing_page_url"),
    )
    record.update(metadata)
    record["local_path"] = relative_path.as_posix()
    record["retrieved_at"] = datetime.now(UTC).isoformat()
    record["ingestion_status"] = "downloaded"
    manifest["created_at"] = manifest.get("created_at") or datetime.now(UTC).isoformat()
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary_manifest = Path(stream.name)
    os.replace(temporary_manifest, path)
    return record


def verify_document(
    manifest_path: str | Path,
    document_id: str,
    raw_root: str | Path,
    *,
    representative_pages: list[int],
    visual_review: str,
) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    matches = [item for item in manifest["documents"] if item["document_id"] == document_id]
    if len(matches) != 1:
        raise IngestionError(f"Expected one manifest entry for {document_id}, found {len(matches)}")
    record = matches[0]
    relative_path = Path(record.get("local_path") or "")
    if not relative_path.parts or relative_path.is_absolute() or ".." in relative_path.parts:
        raise IngestionError("local_path must remain inside raw_root")
    document_path = Path(raw_root) / relative_path
    if not document_path.is_file():
        raise IngestionError(f"Local document not found: {document_path}")
    actual_hash = sha256_file(document_path)
    if actual_hash != record.get("sha256"):
        expected_hash = record.get("sha256")
        raise IngestionError(
            f"SHA-256 mismatch for {document_id}: expected {expected_hash}, got {actual_hash}"
        )
    pages = _page_count(document_path)
    if pages != record.get("page_count"):
        expected_pages = record.get("page_count")
        raise IngestionError(
            f"Page count mismatch for {document_id}: expected {expected_pages}, got {pages}"
        )
    if not representative_pages or any(page < 1 or page > pages for page in representative_pages):
        raise IngestionError("representative_pages must be valid 1-based page numbers")
    try:
        extracted = subprocess.run(
            ["pdftotext", str(document_path), "-"],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise IngestionError(f"pdftotext failed for {document_path}") from error
    text_characters = len(extracted.strip())
    if text_characters < 1000:
        raise IngestionError(
            f"Insufficient PDF text layer for {document_id}: {text_characters} chars"
        )
    if visual_review not in {"passed", "failed"}:
        raise IngestionError("visual_review must be passed or failed")
    record["verification"] = {
        "verified_at": datetime.now(UTC).isoformat(),
        "sha256_match": True,
        "page_count_match": True,
        "text_layer_characters": text_characters,
        "representative_pages": representative_pages,
        "visual_review": visual_review,
    }
    record["ingestion_status"] = "verified" if visual_review == "passed" else "excluded"
    if visual_review == "failed":
        record["exclusion_reason"] = "Representative-page visual review failed."
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary_manifest = Path(stream.name)
    os.replace(temporary_manifest, path)
    return record
