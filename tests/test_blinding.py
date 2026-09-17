import json
from copy import deepcopy
from pathlib import Path

import pytest

from esg_reliable_discovery.blinding import build_blind_pool

ROOT = Path(__file__).parents[1]


def _schema() -> dict:
    return json.loads((ROOT / "templates/finding_card.schema.json").read_text(encoding="utf-8"))


def _card() -> dict:
    return json.loads(
        (ROOT / "tests/fixtures/finding_cards/verified_fact.json").read_text(encoding="utf-8")
    )


def _write_card(path: Path, card: dict) -> None:
    path.write_text(json.dumps(card), encoding="utf-8")


def test_blind_pool_removes_identity_and_preserves_private_map(tmp_path):
    card_a = _card()
    card_a["task_id"] = "P0-OPEN-001"
    card_a["finding_id"] = "model-a-finding"
    card_a["provenance"]["model_snapshot"] = "secret-model-a"
    card_a["provenance"]["run_id"] = "secret-run-a"
    card_b = deepcopy(card_a)
    card_b["finding_id"] = "model-b-finding"
    card_b["provenance"]["model_snapshot"] = "secret-model-b"
    card_b["provenance"]["run_id"] = "secret-run-b"
    input_a = tmp_path / "a.json"
    input_b = tmp_path / "b.json"
    _write_card(input_a, card_a)
    _write_card(input_b, card_b)

    result = build_blind_pool(
        [input_b, input_a],
        pool_id="P0-OPEN-CAL",
        task_id="P0-OPEN-001",
        seed=240901,
        output_directory=tmp_path / "public",
        identity_map_path=tmp_path / "local_state/identity.json",
        finding_schema=_schema(),
        created_at="2026-09-01T00:00:00Z",
    )

    manifest = json.loads(Path(result["public_manifest_path"]).read_text(encoding="utf-8"))
    identity = json.loads((tmp_path / "local_state/identity.json").read_text(encoding="utf-8"))
    assert manifest["pre_review_deduplication"] is False
    assert manifest["candidate_count"] == 2
    assert {item["model_snapshot"] for item in identity["identities"]} == {
        "secret-model-a",
        "secret-model-b",
    }
    for item in manifest["candidates"]:
        blinded = json.loads(Path(item["path"]).read_text(encoding="utf-8"))
        assert blinded["provenance"]["model_snapshot"] is None
        assert blinded["provenance"]["run_id"] == "BLINDED"
        assert "secret-model" not in json.dumps(blinded)


def test_blind_pool_is_deterministic_for_input_order(tmp_path):
    inputs = []
    for index in range(3):
        card = _card()
        card["task_id"] = "P0-OPEN-001"
        card["finding_id"] = f"finding-{index}"
        path = tmp_path / f"candidate-{index}.json"
        _write_card(path, card)
        inputs.append(path)
    first = build_blind_pool(
        inputs,
        pool_id="POOL",
        task_id="P0-OPEN-001",
        seed=42,
        output_directory=tmp_path / "first",
        identity_map_path=tmp_path / "local_state/first.json",
        finding_schema=_schema(),
        created_at="2026-09-01T00:00:00Z",
    )
    second = build_blind_pool(
        list(reversed(inputs)),
        pool_id="POOL",
        task_id="P0-OPEN-001",
        seed=42,
        output_directory=tmp_path / "second",
        identity_map_path=tmp_path / "local_state/second.json",
        finding_schema=_schema(),
        created_at="2026-09-01T00:00:00Z",
    )
    first_identity = json.loads((tmp_path / "local_state/first.json").read_text(encoding="utf-8"))
    second_identity = json.loads((tmp_path / "local_state/second.json").read_text(encoding="utf-8"))
    assert first_identity["identities"] == second_identity["identities"]
    assert first["candidate_count"] == second["candidate_count"]


def test_blind_pool_refuses_overwrite(tmp_path):
    output = tmp_path / "public"
    output.mkdir()
    (output / "existing.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_blind_pool(
            [],
            pool_id="POOL",
            task_id="P0-OPEN-001",
            seed=1,
            output_directory=output,
            identity_map_path=tmp_path / "identity.json",
            finding_schema=_schema(),
        )
