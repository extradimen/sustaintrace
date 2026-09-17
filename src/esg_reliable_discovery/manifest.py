from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .hashing import sha256_file


class ManifestLockError(RuntimeError):
    """Raised when a document manifest cannot be reproducibly frozen."""


def _counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def summarize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    documents = payload.get("documents", [])
    statuses = _counts([document["ingestion_status"] for document in documents])
    verified = [document for document in documents if document["ingestion_status"] == "verified"]
    verified_companies = {document["company_id"] for document in verified}

    return {
        "manifest_id": payload.get("manifest_id"),
        "frozen": bool(payload.get("frozen", False)),
        "documents": {
            "total": len(documents),
            "by_status": statuses,
            "verified_pages": sum(document.get("page_count") or 0 for document in verified),
            "verified_bytes": sum(document.get("bytes") or 0 for document in verified),
        },
        "verified_coverage": {
            "companies": len(verified_companies),
            "countries": _counts([document["country"] for document in verified]),
            "sectors": _counts([document["sector"] for document in verified]),
            "report_types": _counts([document["report_type"] for document in verified]),
            "reporting_periods": _counts([document["reporting_period"] for document in verified]),
        },
        "excluded": [
            {
                "document_id": document["document_id"],
                "reason": document.get("exclusion_reason"),
            }
            for document in documents
            if document["ingestion_status"] == "excluded"
        ],
    }


def summarize_manifest_path(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return summarize_manifest(payload)


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def lock_manifest(
    manifest_path: str | Path,
    raw_root: str | Path,
    lock_path: str | Path,
    *,
    minimum_verified: int = 10,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    documents = payload.get("documents", [])
    identifiers = [document["document_id"] for document in documents]
    duplicates = sorted(
        identifier for identifier, count in Counter(identifiers).items() if count > 1
    )
    if duplicates:
        raise ManifestLockError(f"Duplicate document IDs: {', '.join(duplicates)}")

    incomplete = [
        document["document_id"]
        for document in documents
        if document["ingestion_status"] in {"planned", "downloaded"}
    ]
    if incomplete:
        raise ManifestLockError(f"Incomplete manifest records: {', '.join(incomplete)}")

    verified = [document for document in documents if document["ingestion_status"] == "verified"]
    if len(verified) < minimum_verified:
        raise ManifestLockError(
            f"Need at least {minimum_verified} verified documents, found {len(verified)}"
        )

    locked_documents = []
    for document in verified:
        relative_path = Path(document.get("local_path") or "")
        if not relative_path.parts or relative_path.is_absolute() or ".." in relative_path.parts:
            raise ManifestLockError(f"Invalid local_path for {document['document_id']}")
        source = Path(raw_root) / relative_path
        if not source.is_file():
            raise ManifestLockError(f"Missing source document: {source}")
        actual_hash = sha256_file(source)
        if actual_hash != document.get("sha256"):
            raise ManifestLockError(f"SHA-256 mismatch for {document['document_id']}")
        locked_documents.append(
            {
                "document_id": document["document_id"],
                "sha256": actual_hash,
                "bytes": document["bytes"],
                "page_count": document["page_count"],
            }
        )

    payload["frozen"] = True
    _atomic_json_write(manifest_file, payload)
    lock = {
        "schema_version": "1.0",
        "manifest_id": payload["manifest_id"],
        "locked_at": datetime.now(UTC).isoformat(),
        "manifest_sha256": sha256_file(manifest_file),
        "verified_document_count": len(locked_documents),
        "documents": locked_documents,
    }
    _atomic_json_write(Path(lock_path), lock)
    return lock
