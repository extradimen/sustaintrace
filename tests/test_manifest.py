import json

import pytest

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.manifest import ManifestLockError, lock_manifest, summarize_manifest


def test_summarize_manifest_counts_only_verified_coverage():
    payload = {
        "manifest_id": "P0",
        "frozen": False,
        "documents": [
            {
                "document_id": "a",
                "company_id": "company-1",
                "country": "US",
                "sector": "Technology",
                "report_type": "sustainability",
                "reporting_period": "FY2024",
                "ingestion_status": "verified",
                "page_count": 10,
                "bytes": 100,
            },
            {
                "document_id": "b",
                "company_id": "company-1",
                "country": "US",
                "sector": "Technology",
                "report_type": "annual",
                "reporting_period": "FY2024",
                "ingestion_status": "verified",
                "page_count": 20,
                "bytes": 200,
            },
            {
                "document_id": "c",
                "company_id": "company-2",
                "country": "GB",
                "sector": "Energy",
                "report_type": "integrated",
                "reporting_period": "FY2024",
                "ingestion_status": "excluded",
                "exclusion_reason": "HTTP 403",
            },
        ],
    }

    summary = summarize_manifest(payload)

    assert summary["documents"] == {
        "total": 3,
        "by_status": {"excluded": 1, "verified": 2},
        "verified_pages": 30,
        "verified_bytes": 300,
    }
    assert summary["verified_coverage"]["companies"] == 1
    assert summary["verified_coverage"]["countries"] == {"US": 2}
    assert summary["verified_coverage"]["report_types"] == {
        "annual": 1,
        "sustainability": 1,
    }
    assert summary["excluded"] == [{"document_id": "c", "reason": "HTTP 403"}]


def test_lock_manifest_freezes_verified_sources(tmp_path):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    source = raw_root / "report.pdf"
    source.write_bytes(b"verified-source")
    manifest = {
        "schema_version": "1.0",
        "manifest_id": "P0",
        "frozen": False,
        "documents": [
            {
                "document_id": "doc",
                "ingestion_status": "verified",
                "local_path": "report.pdf",
                "sha256": sha256_file(source),
                "bytes": source.stat().st_size,
                "page_count": 1,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    lock_path = tmp_path / "manifest.lock.json"

    lock = lock_manifest(manifest_path, raw_root, lock_path, minimum_verified=1)

    assert json.loads(manifest_path.read_text(encoding="utf-8"))["frozen"] is True
    assert lock["verified_document_count"] == 1
    assert lock["manifest_sha256"] == sha256_file(manifest_path)
    assert json.loads(lock_path.read_text(encoding="utf-8")) == lock


def test_lock_manifest_rejects_incomplete_record(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "P0",
                "documents": [{"document_id": "pending", "ingestion_status": "downloaded"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestLockError, match="Incomplete manifest records"):
        lock_manifest(manifest_path, tmp_path / "raw", tmp_path / "lock.json")
