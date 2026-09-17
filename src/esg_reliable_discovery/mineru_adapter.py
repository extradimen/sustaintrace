from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .hashing import sha256_file


class MinerUError(RuntimeError):
    """Raised when the external MinerU parser cannot be safely used."""


def audit_mineru_assets(
    tools_config: str | Path,
    asset_manifest: str | Path,
) -> dict[str, Any]:
    """Verify the configured MinerU snapshot against its frozen asset manifest."""
    config_path = Path(tools_config).resolve()
    manifest_path = Path(asset_manifest).resolve()
    if not config_path.is_file():
        raise MinerUError(f"MinerU tools config does not exist: {config_path}")
    if not manifest_path.is_file():
        raise MinerUError(f"MinerU asset manifest does not exist: {manifest_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        snapshot_root = Path(config["models-dir"]["pipeline"]).resolve()
        model_root = snapshot_root / str(manifest.get("models_root_layout", "models/"))
        expected_assets = manifest["assets"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise MinerUError(f"Invalid MinerU asset configuration: {exc}") from exc

    checked_bytes = 0
    for expected in expected_assets:
        path = model_root / expected["path"]
        if not path.is_file():
            raise MinerUError(f"MinerU asset is missing: {path}")
        actual_bytes = path.stat().st_size
        if actual_bytes != int(expected["bytes"]):
            raise MinerUError(
                f"MinerU asset size mismatch: {path} ({actual_bytes} != {expected['bytes']})"
            )
        actual_sha256 = sha256_file(path)
        if actual_sha256 != expected["sha256"]:
            raise MinerUError(f"MinerU asset SHA256 mismatch: {path}")
        checked_bytes += actual_bytes
    if len(expected_assets) != int(manifest["asset_count"]):
        raise MinerUError("MinerU manifest asset count is internally inconsistent")
    return {
        "schema_version": "1.0",
        "record_kind": "mineru_asset_preflight",
        "state": "verified",
        "tools_config": str(config_path),
        "tools_config_sha256": sha256_file(config_path),
        "asset_manifest": str(manifest_path),
        "asset_manifest_sha256": sha256_file(manifest_path),
        "models_root": str(model_root),
        "revision": manifest.get("revision"),
        "asset_count": len(expected_assets),
        "checked_bytes": checked_bytes,
    }


def probe_mineru(executable: str = "mineru") -> dict[str, Any]:
    resolved = shutil.which(executable)
    if resolved is None:
        return {"available": False, "executable": executable, "version": None}
    try:
        result = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True, check=False, timeout=30
        )
    except subprocess.TimeoutExpired:
        environment_python = str(Path(resolved).with_name("python"))
        metadata_result = subprocess.run(
            [
                environment_python,
                "-c",
                "import importlib.metadata as m; print(m.version('mineru'))",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return {
            "available": metadata_result.returncode == 0,
            "executable": resolved,
            "version": metadata_result.stdout.strip() or None,
            "version_source": "python_package_metadata",
            "cli_version_probe_timed_out": True,
            "returncode": metadata_result.returncode,
        }
    version_text = (result.stdout or result.stderr).strip()
    return {
        "available": result.returncode == 0,
        "executable": resolved,
        "version": version_text,
        "version_source": "cli",
        "cli_version_probe_timed_out": False,
        "returncode": result.returncode,
    }


def parse_with_mineru(
    input_pdf: str | Path,
    output_directory: str | Path,
    *,
    executable: str = "mineru",
    backend: str = "pipeline",
    method: str = "auto",
    start_page: int | None = None,
    end_page: int | None = None,
    tools_config: str | Path | None = None,
    timeout_seconds: int = 7200,
) -> dict[str, Any]:
    source = Path(input_pdf).resolve()
    destination = Path(output_directory).resolve()
    if not source.is_file() or source.read_bytes()[:5] != b"%PDF-":
        raise MinerUError(f"Input is not a PDF: {source}")
    probe = probe_mineru(executable)
    if not probe["available"]:
        raise MinerUError(f"MinerU executable is unavailable: {executable}")
    if destination.exists() and any(destination.iterdir()):
        raise MinerUError(f"Refusing to overwrite non-empty output directory: {destination}")
    if start_page is not None and start_page < 0:
        raise MinerUError("start_page must be non-negative")
    if end_page is not None and end_page < 0:
        raise MinerUError("end_page must be non-negative")
    if start_page is not None and end_page is not None and end_page < start_page:
        raise MinerUError("end_page must not precede start_page")
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        str(probe["executable"]),
        "-p",
        str(source),
        "-o",
        str(destination),
        "-b",
        backend,
        "-m",
        method,
    ]
    if start_page is not None:
        command.extend(["--start", str(start_page)])
    if end_page is not None:
        command.extend(["--end", str(end_page)])
    environment = os.environ.copy()
    resolved_tools_config = None
    if tools_config is not None:
        resolved_tools_config = str(Path(tools_config).resolve())
        if not Path(resolved_tools_config).is_file():
            raise MinerUError(f"MinerU tools config does not exist: {resolved_tools_config}")
        environment["MINERU_TOOLS_CONFIG_JSON"] = resolved_tools_config
    started_at = datetime.now(UTC)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
        env=environment,
    )
    files = sorted(path for path in destination.rglob("*") if path.is_file())
    output_files = [
        {
            "path": str(path.relative_to(destination)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    record = {
        "schema_version": "1.0",
        "parser": "MinerU",
        "parser_probe": probe,
        "backend": backend,
        "method": method,
        "start_page_zero_based": start_page,
        "end_page_zero_based": end_page,
        "tools_config": resolved_tools_config,
        "input_pdf": str(source),
        "input_sha256": sha256_file(source),
        "output_directory": str(destination),
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output_files": output_files,
    }
    record_path = destination / "esg_rd_mineru_run.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    if result.returncode != 0:
        raise MinerUError(f"MinerU failed; audit record: {record_path}")
    if not any(path.suffix.lower() in {".md", ".json"} for path in files):
        raise MinerUError(f"MinerU produced no Markdown or JSON output: {record_path}")
    return record
