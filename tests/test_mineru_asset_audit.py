import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/audit_mineru_assets.py"
SPEC = importlib.util.spec_from_file_location("audit_mineru_assets", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_inventory_is_relative_deterministic_and_sensitive_to_bytes(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    asset = tmp_path / "nested/model.bin"
    asset.write_bytes(b"model-v1")

    first = MODULE.inventory(tmp_path)
    second = MODULE.inventory(tmp_path)
    assert first == second
    assert first[0]["path"] == "nested/model.bin"
    assert first[0]["bytes"] == 8

    asset.write_bytes(b"model-v2")
    changed = MODULE.inventory(tmp_path)
    assert changed[0]["sha256"] != first[0]["sha256"]
