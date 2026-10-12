from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the pinned MinerU model snapshot")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    snapshot = Path(
        snapshot_download(
            repo_id=manifest["repository"],
            revision=manifest["revision"],
            allow_patterns=[
                (Path(str(manifest.get("models_root_layout", "models/"))) / item["path"]).as_posix()
                for item in manifest["assets"]
            ],
        )
    )
    args.destination.mkdir(parents=True, exist_ok=True)
    asset_root = args.destination / str(manifest.get("models_root_layout", "models/"))
    for item in manifest["assets"]:
        source = snapshot / str(manifest.get("models_root_layout", "models/")) / item["path"]
        target = asset_root / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha256_file(target) == item["sha256"]:
            continue
        shutil.copy2(source, target)
        if target.stat().st_size != item["bytes"] or sha256_file(target) != item["sha256"]:
            target.unlink(missing_ok=True)
            raise SystemExit(f"MinerU model integrity check failed: {item['path']}")
    actual = [path for path in asset_root.rglob("*") if path.is_file()]
    expected_names = {item["path"] for item in manifest["assets"]}
    unexpected = [
        path for path in actual if path.relative_to(asset_root).as_posix() not in expected_names
    ]
    if unexpected:
        raise SystemExit(f"Unexpected files in MinerU model directory: {unexpected[:3]}")
    print(f"Verified {len(actual)} MinerU assets in {args.destination}")


if __name__ == "__main__":
    main()
