from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the SustainTrace release boundary")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--wheel", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    publication_files = (
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CITATION.cff",
        "docs/SOURCE_DISTRIBUTION_POLICY.md",
        "docs/SOFTWAREX_REPRODUCIBILITY.md",
        "docs/RELEASE_ENGINEERING_MILESTONE.md",
    )
    han_pattern = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
    for relative_path in publication_files:
        publication_path = root / relative_path
        assert publication_path.is_file(), f"missing publication file: {relative_path}"
        assert not han_pattern.search(publication_path.read_text(encoding="utf-8")), (
            f"publication-facing file contains Chinese text: {relative_path}"
        )
    seed = root / "src/esg_reliable_discovery/release_seed/knowledge_bases/v0.1"
    manifest = json.loads((seed / "release_manifest.lock.json").read_text(encoding="utf-8"))
    assert manifest["counts"] == {
        "failure_observations": 1032,
        "issuer_entities": 34,
        "relation_edges": 149,
        "trusted_facts": 149,
    }
    assert manifest["candidate_records_included"] is False
    assert manifest["simulated_records_included"] is False
    trusted = _jsonl(seed / "trusted_fact_records.jsonl")
    assert all(row["trust_tier"] == "B" for row in trusted)
    assert all(row["provenance"]["simulated"] is False for row in trusted)
    for data_name, schema_name in (
        ("entity_registry.jsonl", "entity-record-v0.1.schema.json"),
        ("relation_edges.jsonl", "relation-edge-v0.1.schema.json"),
    ):
        schema = json.loads((root / "schemas/knowledge" / schema_name).read_text())
        validator = Draft202012Validator(schema)
        for row in _jsonl(seed / data_name):
            validator.validate(row)
    source_policy = json.loads(
        (seed / "source_distribution_manifest.lock.json").read_text(encoding="utf-8")
    )
    assert source_policy["policy"]["raw_issuer_pdfs_bundled"] is False
    assert all(not row["bundled_in_release"] for row in source_policy["records"])
    if args.wheel:
        with zipfile.ZipFile(args.wheel) as archive:
            names = set(archive.namelist())
        for name in (
            "esg_reliable_discovery/workbench_static/index.html",
            "esg_reliable_discovery/release_seed/knowledge_bases/v0.1/trusted_fact_records.jsonl",
            "esg_reliable_discovery/release_seed/knowledge_bases/v0.1/entity_registry.jsonl",
            "esg_reliable_discovery/release_seed/knowledge_bases/v0.1/relation_edges.jsonl",
        ):
            assert name in names, name
    print(json.dumps({"status": "passed", **manifest["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
