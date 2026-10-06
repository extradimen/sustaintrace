from __future__ import annotations

import fnmatch
import hashlib
import json
import runpy
import sys
import types
from pathlib import Path

import pytest


@pytest.mark.parametrize("layout", ["models/", "custom/models/", ""])
@pytest.mark.parametrize("corrupt", [False, True])
def test_download_uses_repository_paths_and_checks_integrity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str, corrupt: bool
) -> None:
    content = b'{"model": "layout"}'
    asset = "Layout/PP-DocLayoutV2/config.json"
    repository_path = (Path(layout) / asset).as_posix()
    manifest = {
        "repository": "opendatalab/PDF-Extract-Kit-1.0",
        "revision": "ed6b654c018d742e65a17671e379c5e6ecc87ec9",
        "models_root_layout": layout,
        "assets": [
            {"path": asset, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    destination = tmp_path / "installed"
    calls = []

    def download(**kwargs: object) -> str:
        calls.append(kwargs)
        # Model the Hub's filtering against full repository paths on a cold cache.
        if any(fnmatch.fnmatch(repository_path, p) for p in kwargs["allow_patterns"]):
            source = snapshot / repository_path
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"x" * len(content) if corrupt else content)
        return str(snapshot)

    module = types.ModuleType("huggingface_hub")
    module.snapshot_download = download
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "download_mineru_models.py",
            "--manifest",
            str(manifest_path),
            "--destination",
            str(destination),
        ],
    )
    script = Path(__file__).resolve().parents[1] / "scripts/download_mineru_models.py"
    target = destination / repository_path
    if corrupt:
        with pytest.raises(SystemExit, match="integrity check failed"):
            runpy.run_path(str(script), run_name="__main__")
        assert not target.exists()
    else:
        runpy.run_path(str(script), run_name="__main__")
        assert target.read_bytes() == content
    assert calls == [
        {
            "repo_id": manifest["repository"],
            "revision": manifest["revision"],
            "allow_patterns": [repository_path],
        }
    ]
