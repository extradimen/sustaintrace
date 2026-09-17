import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "templates/finding_card.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


@pytest.mark.parametrize(
    "fixture",
    sorted((ROOT / "tests/fixtures/finding_cards").glob("*.json")),
    ids=lambda path: path.stem,
)
def test_finding_card_calibration_fixtures_are_valid(fixture):
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    VALIDATOR.validate(payload)


def test_verified_card_requires_supporting_evidence():
    fixture = ROOT / "tests/fixtures/finding_cards/verified_fact.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["supporting_evidence"] = []

    errors = list(VALIDATOR.iter_errors(payload))

    assert any(error.validator == "minItems" for error in errors)


def test_structural_anomaly_requires_anomaly_code():
    fixture = ROOT / "tests/fixtures/finding_cards/verified_fact.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["finding_type"] = "structural_anomaly"

    errors = list(VALIDATOR.iter_errors(payload))

    assert any(error.validator == "minItems" for error in errors)
