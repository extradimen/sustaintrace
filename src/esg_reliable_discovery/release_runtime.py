from __future__ import annotations

import hashlib
import json
import shutil
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _seed_root() -> Any:
    return files("esg_reliable_discovery").joinpath("release_seed/knowledge_bases/v0.1")


def initialize_workspace(workspace: str | Path) -> dict[str, Any]:
    """Initialize an empty workspace without replacing user or audited data."""
    root = Path(workspace).expanduser().resolve()
    destination = root / "data/knowledge_bases/v0.1"
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    preserved: list[str] = []
    seed = _seed_root()
    with as_file(seed.joinpath("release_manifest.lock.json")) as manifest_path:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {item["path"]: item for item in manifest["files"]}
    expected["release_manifest.lock.json"] = None
    for name, metadata in expected.items():
        target = destination / name
        if target.exists():
            preserved.append(name)
            continue
        with as_file(seed.joinpath(name)) as source:
            shutil.copy2(source, target)
        if metadata is not None and sha256_file(target) != metadata["sha256"]:
            target.unlink(missing_ok=True)
            raise RuntimeError(f"release seed integrity check failed for {name}")
        copied.append(name)
    for relative in ("data/workbench/jobs", "data/workbench/runtime", "configs/parsers"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    return {
        "workspace": str(root),
        "copied": copied,
        "preserved": preserved,
        "counts": manifest["counts"],
        "policy": {
            "existing_files_overwritten": False,
            "default_query_layer": manifest["default_query_layer"],
        },
    }
