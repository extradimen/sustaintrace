import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/render_mineru_config.py"
SPEC = importlib.util.spec_from_file_location("render_mineru_config", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_render_replaces_snapshot_placeholder(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    template.write_text(
        json.dumps({"models-dir": {"pipeline": MODULE.PLACEHOLDER}}), encoding="utf-8"
    )
    snapshot = tmp_path / "snapshot"
    (snapshot / "models").mkdir(parents=True)
    result = MODULE.render(template, snapshot)
    assert result["models-dir"]["pipeline"] == str(snapshot.resolve())


def test_render_rejects_snapshot_without_models(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    template.write_text(
        json.dumps({"models-dir": {"pipeline": MODULE.PLACEHOLDER}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="does not contain models"):
        MODULE.render(template, tmp_path / "missing")
