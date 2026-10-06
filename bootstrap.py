#!/usr/bin/env python3
"""Cross-platform SustainTrace source installer.

The installer is intentionally auditable: every completed phase is recorded in
data/install/bootstrap_state.json and existing knowledge or model assets are
never overwritten unless their pinned digest differs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "data/install/bootstrap_state.json"
MINERU_LOCK = ROOT / "configs/parsers/mineru-runtime.lock.json"
MODEL_MANIFEST = ROOT / "model_manifests/mineru-pdf-extract-kit-1.0-ed6b654c.lock.json"
MODEL_ROOT = ROOT / "models/mineru/PDF-Extract-Kit-1.0-ed6b654c"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _bin(venv: Path, name: str) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / f"{name}.exe"
    return venv / "bin" / name


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def _write_state(phases: dict[str, Any], status: str) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "product": "SustainTrace",
        "status": status,
        "updated_at": _now(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "phases": phases,
    }
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(STATE)


def _phase(phases: dict[str, Any], name: str, status: str, **details: Any) -> None:
    phases[name] = {"status": status, "time": _now(), **details}
    _write_state(phases, "running" if status != "failed" else "failed")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _install_application(phases: dict[str, Any], *, dev: bool) -> Path:
    venv = ROOT / ".venv"
    python = _bin(venv, "python")
    if not python.exists():
        _run([sys.executable, "-m", "venv", str(venv)])
    pip_probe = subprocess.run(
        [str(python), "-m", "pip", "--version"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if pip_probe.returncode != 0:
        _run([str(python), "-m", "ensurepip", "--upgrade"])
    _run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    install_target = ".[dev]" if dev else "."
    _run([str(python), "-m", "pip", "install", "-e", install_target])
    _run(
        [
            str(python),
            "-c",
            "from esg_reliable_discovery.release_runtime import initialize_workspace;"
            "initialize_workspace('.')",
        ]
    )
    _phase(phases, "application", "complete", python=str(python))
    return python


def _find_poppler_tools() -> dict[str, str | None]:
    tools = {name: shutil.which(name) for name in ("pdftoppm", "pdftotext")}
    if all(tools.values()) or platform.system() != "Windows":
        return tools
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    package_root = local / "Microsoft/WinGet/Packages"
    if package_root.is_dir():
        for executable in package_root.glob("**/pdftoppm.exe"):
            candidate_dir = executable.parent
            partner = candidate_dir / "pdftotext.exe"
            if partner.is_file():
                os.environ["PATH"] = f"{candidate_dir}{os.pathsep}{os.environ.get('PATH', '')}"
                return {"pdftoppm": str(executable), "pdftotext": str(partner)}
    return tools


def _install_poppler(phases: dict[str, Any], *, check_only: bool) -> None:
    tools = _find_poppler_tools()
    if all(tools.values()):
        _phase(phases, "poppler", "complete", executables=tools)
        return
    if check_only:
        _phase(phases, "poppler", "missing", executables=tools)
        return
    system = platform.system()
    if system == "Darwin" and shutil.which("brew"):
        _run(["brew", "install", "poppler"])
    elif system == "Windows":
        installers: list[tuple[str, list[str]]] = []
        if shutil.which("winget"):
            installers.append(
                (
                    "winget",
                    [
                        "winget",
                        "install",
                        "--id",
                        "oschwartz10612.Poppler",
                        "--exact",
                        "--source",
                        "winget",
                        "--accept-package-agreements",
                        "--accept-source-agreements",
                        "--disable-interactivity",
                    ],
                )
            )
        if shutil.which("choco"):
            installers.append(("chocolatey", ["choco", "install", "poppler", "-y"]))
        if not installers:
            raise RuntimeError("Poppler requires winget or Chocolatey on Windows")
        failures: list[str] = []
        for installer, command in installers:
            try:
                _run(command)
                break
            except subprocess.CalledProcessError as error:
                failures.append(f"{installer}: exit {error.returncode}")
                print(f"{installer} failed; trying the next registered installer", flush=True)
        else:
            raise RuntimeError("Poppler installation failed: " + "; ".join(failures))
    elif system == "Linux":
        if shutil.which("apt-get"):
            prefix = [] if hasattr(os, "geteuid") and os.geteuid() == 0 else ["sudo"]
            _run([*prefix, "apt-get", "update"])
            _run([*prefix, "apt-get", "install", "-y", "poppler-utils"])
        elif shutil.which("dnf"):
            _run(["sudo", "dnf", "install", "-y", "poppler-utils"])
        elif shutil.which("pacman"):
            _run(["sudo", "pacman", "-S", "--needed", "--noconfirm", "poppler"])
        else:
            raise RuntimeError("No supported Linux package manager found for Poppler")
    else:
        raise RuntimeError("Poppler is missing and no supported package manager was found")
    tools = _find_poppler_tools()
    if not all(tools.values()):
        raise RuntimeError("Poppler installation completed but its executables are not on PATH")
    _phase(phases, "poppler", "complete", executables=tools)


def _ensure_uv(app_python: Path) -> Path:
    uv = shutil.which("uv")
    if uv:
        return Path(uv)
    _run([str(app_python), "-m", "pip", "install", "uv"])
    executable = _bin(ROOT / ".venv", "uv")
    if not executable.exists():
        raise RuntimeError("uv installation did not create an executable")
    return executable


def _render_mineru_config() -> Path:
    template = ROOT / "configs/parsers/mineru-tools-huggingface.template.json"
    output = ROOT / "configs/parsers/mineru-tools-huggingface.json"
    payload = json.loads(template.read_text(encoding="utf-8"))
    payload["models-dir"]["pipeline"] = str(MODEL_ROOT.resolve())
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _audit_models() -> tuple[bool, dict[str, Any]]:
    manifest = json.loads(MODEL_MANIFEST.read_text(encoding="utf-8"))
    asset_root = MODEL_ROOT / str(manifest.get("models_root_layout", "models/"))
    missing: list[str] = []
    invalid: list[str] = []
    for item in manifest["assets"]:
        path = asset_root / item["path"]
        if not path.is_file():
            missing.append(item["path"])
        elif path.stat().st_size != item["bytes"] or _sha256(path) != item["sha256"]:
            invalid.append(item["path"])
    return not missing and not invalid, {
        "expected_assets": manifest["asset_count"],
        "missing": missing,
        "invalid": invalid,
    }


def _install_mineru(
    phases: dict[str, Any], app_python: Path, *, check_only: bool, skip_models: bool
) -> None:
    lock = json.loads(MINERU_LOCK.read_text(encoding="utf-8"))
    venv = ROOT / ".mineru-venv"
    python = _bin(venv, "python")
    mineru = _bin(venv, "mineru")
    if check_only:
        models_ok, audit = _audit_models()
        _phase(
            phases,
            "mineru",
            "complete" if mineru.exists() and (models_ok or skip_models) else "missing",
            executable=str(mineru),
            models=audit,
        )
        return
    uv = _ensure_uv(app_python)
    if not python.exists():
        _run([str(uv), "python", "install", lock["python"]])
        _run([str(uv), "venv", "--python", lock["python"], str(venv)])
    specifications = []
    for name, version in lock["packages"].items():
        extras = lock.get("package_extras", {}).get(name, [])
        requirement = f"{name}[{','.join(extras)}]" if extras else name
        specifications.append(f"{requirement}=={version}")
    _run([str(uv), "pip", "install", "--python", str(python), *specifications])
    if not mineru.exists():
        raise RuntimeError("Pinned MinerU installation did not create the mineru executable")
    if not skip_models:
        models_ok, _ = _audit_models()
        if not models_ok:
            _run(
                [
                    str(python),
                    str(ROOT / "scripts/download_mineru_models.py"),
                    "--manifest",
                    str(MODEL_MANIFEST),
                    "--destination",
                    str(MODEL_ROOT),
                ]
            )
        models_ok, audit = _audit_models()
        if not models_ok:
            raise RuntimeError(f"MinerU model SHA256 audit failed: {audit}")
    else:
        _, audit = _audit_models()
    config = _render_mineru_config()
    _phase(
        phases,
        "mineru",
        "complete",
        executable=str(mineru),
        version=lock["packages"]["mineru"],
        config=str(config),
        models=audit,
        models_skipped=skip_models,
    )


def _minimal_pdf(path: Path) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        (
            b"<< /Length 55 >>\nstream\nBT /F1 16 Tf 30 120 Td "
            b"(SustainTrace PDF smoke test) Tj ET\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _smoke_test(phases: dict[str, Any], *, check_only: bool, skip_models: bool) -> None:
    mineru = _bin(ROOT / ".mineru-venv", "mineru")
    config = ROOT / "configs/parsers/mineru-tools-huggingface.json"
    source = ROOT / "data/install/smoke/sustaintrace-smoke.pdf"
    output = ROOT / "data/install/smoke/mineru-output"
    result_path = ROOT / "data/install/smoke/smoke_result.lock.json"
    if check_only:
        products = [path for path in output.rglob("*") if path.suffix.lower() in {".md", ".json"}]
        if source.is_file() and result_path.is_file() and products:
            previous = json.loads(result_path.read_text(encoding="utf-8"))
            valid = previous.get("source_sha256") == _sha256(source)
            _phase(
                phases,
                "pdf_smoke_test",
                "complete" if valid else "invalid",
                verified_existing_artifact=True,
                source_sha256=_sha256(source),
                outputs=len(products),
            )
        else:
            _phase(phases, "pdf_smoke_test", "missing", reason="no_frozen_smoke_result")
        return
    if skip_models:
        _phase(phases, "pdf_smoke_test", "skipped", reason="models_skipped")
        return
    if output.exists():
        shutil.rmtree(output)
    _minimal_pdf(source)
    env = os.environ.copy()
    env["MINERU_TOOLS_CONFIG_JSON"] = str(config)
    command = [
        str(mineru),
        "-p",
        str(source),
        "-o",
        str(output),
        "-b",
        "pipeline",
        "-m",
        "txt",
        "-s",
        "0",
        "-e",
        "0",
    ]
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    products = [path for path in output.rglob("*") if path.suffix.lower() in {".md", ".json"}]
    if not products:
        raise RuntimeError(
            f"MinerU smoke test produced no Markdown or JSON output (exit={result.returncode})"
        )
    details = {
        "source_sha256": _sha256(source),
        "outputs": len(products),
        "process_returncode": result.returncode,
        "shutdown_warning": (
            "Parser products verified despite a non-zero shutdown return code"
            if result.returncode != 0
            else None
        ),
    }
    result_path.write_text(
        json.dumps({"schema_version": "1.0", **details}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _phase(phases, "pdf_smoke_test", "complete", **details)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the complete SustainTrace runtime")
    parser.add_argument(
        "--check", action="store_true", help="Audit prerequisites without changing them"
    )
    parser.add_argument("--skip-mineru", action="store_true")
    parser.add_argument("--skip-models", action="store_true")
    parser.add_argument("--skip-poppler", action="store_true")
    parser.add_argument("--dev", action="store_true", help="Install test and lint dependencies")
    args = parser.parse_args()
    phases: dict[str, Any] = {}
    try:
        app_python = _bin(ROOT / ".venv", "python")
        if args.check:
            _phase(
                phases,
                "application",
                "complete" if app_python.exists() else "missing",
                python=str(app_python),
            )
        else:
            app_python = _install_application(phases, dev=args.dev)
        if args.skip_poppler:
            _phase(phases, "poppler", "skipped")
        else:
            _install_poppler(phases, check_only=args.check)
        if args.skip_mineru:
            _phase(phases, "mineru", "skipped")
            _phase(phases, "pdf_smoke_test", "skipped")
        else:
            _install_mineru(phases, app_python, check_only=args.check, skip_models=args.skip_models)
            _smoke_test(phases, check_only=args.check, skip_models=args.skip_models)
    except Exception as exc:
        phases["error"] = {"status": "failed", "type": type(exc).__name__, "detail": str(exc)}
        _write_state(phases, "failed")
        raise
    final_status = (
        "ready"
        if all(item.get("status") in {"complete", "skipped"} for item in phases.values())
        else "incomplete"
    )
    _write_state(phases, final_status)
    print(f"SustainTrace bootstrap status: {final_status}")
    if final_status == "ready":
        print("Start with: python run.py")


if __name__ == "__main__":
    main()
