import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[1]


def test_all_json_schemas_are_valid():
    for path in (ROOT / "templates").glob("*.schema.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_initial_p0_manifest_matches_schema():
    schema = json.loads(
        (ROOT / "templates/document_manifest.schema.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((ROOT / "data/manifests/p0_manifest.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(manifest)
