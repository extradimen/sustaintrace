import json

import pytest

from esg_reliable_discovery.ingest import (
    IngestionError,
    _download_pdf,
    ingest_document,
    verify_document,
)


def test_ingest_rejects_path_escape(tmp_path):
    manifest = {
        "documents": [
            {
                "document_id": "doc",
                "ingestion_status": "planned",
                "source_url": "https://example.org/report.pdf",
                "local_path": "../report.pdf",
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(IngestionError, match="inside raw_root"):
        ingest_document(manifest_path, "doc", tmp_path / "raw")


def test_ingest_requires_unique_document_id(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"documents": []}), encoding="utf-8")
    with pytest.raises(IngestionError, match="found 0"):
        ingest_document(manifest_path, "missing", tmp_path / "raw")


def test_download_wraps_socket_timeout(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", timeout)
    with pytest.raises(IngestionError, match="Network failure.*timed out"):
        _download_pdf("https://example.com/report.pdf", tmp_path / "report.pdf")


def test_verify_rejects_hash_mismatch_before_pdf_tools(tmp_path):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    (raw_root / "report.pdf").write_bytes(b"%PDF-not-a-real-report")
    manifest = {
        "documents": [
            {
                "document_id": "doc",
                "local_path": "report.pdf",
                "sha256": "0" * 64,
                "page_count": 1,
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(IngestionError, match="SHA-256 mismatch"):
        verify_document(
            manifest_path,
            "doc",
            raw_root,
            representative_pages=[1],
            visual_review="passed",
        )
