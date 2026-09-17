from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

URL_KEYS = ("official_url", "source_url", "resolved_url", "url")
LANDING_KEYS = ("official_landing_page", "landing_page_url", "source_page_url")


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    facts = _jsonl(root / "data/knowledge_bases/v0.1/trusted_fact_records.jsonl")
    documents: dict[str, dict[str, Any]] = {}
    for fact in facts:
        for metadata in fact.get("subject", {}).get("document_metadata", []):
            document_id = metadata.get("document_id")
            if document_id:
                documents.setdefault(str(document_id), dict(metadata))

    candidates: list[dict[str, Any]] = []
    for path in sorted((root / "data/manifests").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        for record in _walk(payload):
            if any(key in record for key in (*URL_KEYS, *LANDING_KEYS)):
                candidates.append(record)

    records: list[dict[str, Any]] = []
    for document_id, metadata in sorted(documents.items()):
        sha256 = metadata.get("sha256")
        matches = [
            item
            for item in candidates
            if item.get("document_id") == document_id or (sha256 and item.get("sha256") == sha256)
        ]
        direct_url = next(
            (
                str(item[key])
                for item in matches
                for key in URL_KEYS
                if isinstance(item.get(key), str) and str(item[key]).startswith("http")
            ),
            None,
        )
        landing_page = next(
            (
                str(item[key])
                for item in matches
                for key in LANDING_KEYS
                if isinstance(item.get(key), str) and str(item[key]).startswith("http")
            ),
            None,
        )
        if direct_url:
            distribution_class = "official_auto_download"
        elif landing_page:
            distribution_class = "official_manual_download"
        else:
            distribution_class = "metadata_only"
        records.append(
            {
                "document_id": document_id,
                "company": metadata.get("company"),
                "title": metadata.get("title"),
                "language": metadata.get("language"),
                "expected_sha256": sha256,
                "distribution_class": distribution_class,
                "bundled_in_release": False,
                "direct_official_url": direct_url,
                "official_landing_page": landing_page,
                "license_status": "issuer_copyright_no_redistribution_grant_recorded",
            }
        )

    counts: dict[str, int] = {}
    for record in records:
        key = record["distribution_class"]
        counts[key] = counts.get(key, 0) + 1
    payload = {
        "schema_version": "0.1",
        "record_kind": "source_distribution_manifest",
        "policy": {
            "raw_issuer_pdfs_bundled": False,
            "download_only_from_official_source": True,
            "sha256_required_after_download": True,
            "metadata_only_when_stable_official_url_unavailable": True,
            "generated_smoke_fixture_is_redistributable": True,
        },
        "counts": counts,
        "records": records,
    }
    output = root / "data/manifests/release_source_distribution_v0.1.lock.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"documents": len(records), **counts}, sort_keys=True))
    print(f"sha256={_sha256(output)}")


if __name__ == "__main__":
    main()
