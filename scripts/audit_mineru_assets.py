#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--revision")
    args = parser.parse_args()

    root = args.models_root.resolve()
    actual = inventory(root)
    if args.write:
        payload = {
            "schema_version": "1.0",
            "repository": "opendatalab/PDF-Extract-Kit-1.0",
            "revision": args.revision,
            "models_root_layout": "models/",
            "asset_count": len(actual),
            "total_bytes": sum(int(item["bytes"]) for item in actual),
            "assets": actual,
        }
        args.manifest.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {len(actual)} assets to {args.manifest}")
        return

    expected = json.loads(args.manifest.read_text(encoding="utf-8"))
    if actual != expected["assets"]:
        raise SystemExit("MinerU asset audit failed: local inventory differs from manifest")
    if len(actual) != expected["asset_count"]:
        raise SystemExit("MinerU asset audit failed: asset count differs")
    print(
        f"Verified {len(actual)} assets, "
        f"{sum(int(item['bytes']) for item in actual)} bytes, revision={expected['revision']}"
    )


if __name__ == "__main__":
    main()
