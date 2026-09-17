from __future__ import annotations

import subprocess

import bootstrap


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

