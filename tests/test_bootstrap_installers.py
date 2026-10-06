from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import bootstrap


def test_mineru_installs_pipeline_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("python", "mineru"):
        (tmp_path / name).touch()
    commands: list[list[str]] = []
    monkeypatch.setattr(bootstrap, "_bin", lambda _venv, name: tmp_path / name)
    monkeypatch.setattr(bootstrap, "_ensure_uv", lambda _python: tmp_path / "uv")
    monkeypatch.setattr(bootstrap, "_run", lambda command: commands.append(command))
    monkeypatch.setattr(bootstrap, "_audit_models", lambda: (True, {}))
    monkeypatch.setattr(bootstrap, "_render_mineru_config", lambda: tmp_path / "config.json")
    monkeypatch.setattr(bootstrap, "_phase", lambda *_args, **_kwargs: None)

    bootstrap._install_mineru({}, tmp_path / "app-python", check_only=False, skip_models=True)

    assert commands == [
        [
            str(tmp_path / "uv"),
            "pip",
            "install",
            "--python",
            str(tmp_path / "python"),
            "mineru[pipeline]==3.4.0",
            "pdftext==0.6.3",
            "pypdfium2==4.30.0",
        ]
    ]


def test_windows_poppler_falls_back_from_winget_to_chocolatey(monkeypatch) -> None:
    probes = iter(
        [
            {"pdftoppm": None, "pdftotext": None},
            {"pdftoppm": "C:/poppler/pdftoppm.exe", "pdftotext": "C:/poppler/pdftotext.exe"},
        ]
    )
    commands: list[list[str]] = []
    phases: dict[str, object] = {}

    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Windows")
    monkeypatch.setattr(bootstrap, "_find_poppler_tools", lambda: next(probes))
    monkeypatch.setattr(
        bootstrap.shutil,
        "which",
        lambda name: f"C:/{name}.exe" if name in {"winget", "choco"} else None,
    )
    monkeypatch.setattr(
        bootstrap,
        "_phase",
        lambda target, name, status, **details: target.update(
            {name: {"status": status, **details}}
        ),
    )

    def fake_run(command: list[str], **_kwargs: object) -> None:
        commands.append(command)
        if command[0] == "winget":
            raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(bootstrap, "_run", fake_run)

    bootstrap._install_poppler(phases, check_only=False)

    assert [command[0] for command in commands] == ["winget", "choco"]
    assert phases["poppler"]["status"] == "complete"
