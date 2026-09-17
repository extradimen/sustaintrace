import json
from pathlib import Path

import pytest

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.mineru_adapter import (
    MinerUError,
    audit_mineru_assets,
    parse_with_mineru,
    probe_mineru,
)


def test_parse_rejects_non_pdf(tmp_path: Path) -> None:
    source = tmp_path / "bad.pdf"
    source.write_text("not pdf", encoding="utf-8")
    with pytest.raises(MinerUError, match="not a PDF"):
        parse_with_mineru(source, tmp_path / "out")


def test_parse_rejects_missing_executable(tmp_path: Path) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-fake")
    with pytest.raises(MinerUError, match="unavailable"):
        parse_with_mineru(source, tmp_path / "out", executable="missing-mineru-command")


def test_parse_refuses_nonempty_output(tmp_path: Path) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-fake")
    output = tmp_path / "out"
    output.mkdir()
    (output / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(MinerUError, match="Refusing to overwrite"):
        parse_with_mineru(source, output, executable="true")


def test_probe_reports_missing_executable() -> None:
    result = probe_mineru("missing-mineru-command")
    assert result == {
        "available": False,
        "executable": "missing-mineru-command",
        "version": None,
    }


def test_parse_rejects_reversed_page_range(tmp_path: Path) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-fake")
    with pytest.raises(MinerUError, match="must not precede"):
        parse_with_mineru(source, tmp_path / "out", executable="true", start_page=2, end_page=1)


def test_asset_audit_verifies_frozen_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    model_root = snapshot / "models/MFR/example"
    model_root.mkdir(parents=True)
    weight = model_root / "model.safetensors"
    weight.write_bytes(b"locked-weight")
    config = tmp_path / "mineru.json"
    config.write_text(
        json.dumps({"models-dir": {"pipeline": str(snapshot)}}), encoding="utf-8"
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "models_root_layout": "models/",
            "revision": "test-revision",
            "asset_count": 1,
            "assets": [{
                "path": "MFR/example/model.safetensors",
                "bytes": weight.stat().st_size,
                "sha256": sha256_file(weight),
            }],
        }),
        encoding="utf-8",
    )
    result = audit_mineru_assets(config, manifest)
    assert result["state"] == "verified"
    assert result["asset_count"] == 1
    assert result["checked_bytes"] == len(b"locked-weight")


def test_asset_audit_rejects_modified_weight(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    model_root = snapshot / "models"
    model_root.mkdir(parents=True)
    weight = model_root / "weight.bin"
    weight.write_bytes(b"modified")
    config = tmp_path / "mineru.json"
    config.write_text(
        json.dumps({"models-dir": {"pipeline": str(snapshot)}}), encoding="utf-8"
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "models_root_layout": "models/",
            "revision": "test-revision",
            "asset_count": 1,
            "assets": [{"path": "weight.bin", "bytes": 8, "sha256": "0" * 64}],
        }),
        encoding="utf-8",
    )
    with pytest.raises(MinerUError, match="SHA256 mismatch"):
        audit_mineru_assets(config, manifest)
