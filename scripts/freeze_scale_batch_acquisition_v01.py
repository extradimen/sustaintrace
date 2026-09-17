from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_pages(path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError(f"pdfinfo did not report page count: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--failures", required=True, type=Path)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text())
    records = []
    failures = []
    for document in config["documents"]:
        path = ROOT / document["local_path"]
        try:
            if path.read_bytes()[:5] != b"%PDF-":
                raise ValueError("invalid PDF header")
            records.append(
                {
                    "document_id": document["document_id"],
                    "local_path": document["local_path"],
                    "bytes": path.stat().st_size,
                    "pages": pdf_pages(path),
                    "sha256": sha256_file(path),
                    "pdf_header_valid": True,
                    "pdfinfo_valid": True,
                    "download_status": "downloaded_verified_pdf",
                }
            )
        except Exception as error:  # noqa: BLE001 - preserve acquisition failure
            failures.append(
                {
                    "document_id": document["document_id"],
                    "local_path": document["local_path"],
                    "bytes": path.stat().st_size if path.exists() else 0,
                    "failure_class": "downloaded_object_validation_failed",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
    if failures:
        raise RuntimeError(f"acquisition validation failures: {failures}")
    created_at = datetime.now(UTC).isoformat()
    manifest = {
        "schema_version": "0.1",
        "batch_id": config["batch_id"],
        "created_at": created_at,
        "source_config": config_path.relative_to(ROOT).as_posix(),
        "documents": records,
        "totals": {
            "documents": len(records),
            "bytes": sum(item["bytes"] for item in records),
            "pages": sum(item["pages"] for item in records),
        },
    }
    failure_manifest = {
        "schema_version": "0.1",
        "batch_id": config["batch_id"],
        "created_at": created_at,
        "status": "no_acquisition_failures",
        "failures": failures,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.failures.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    args.failures.write_text(json.dumps(failure_manifest, indent=2) + "\n")
    print(json.dumps(manifest["totals"], sort_keys=True))


if __name__ == "__main__":
    main()
