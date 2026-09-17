from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _company(record: dict[str, Any]) -> str:
    subject = record.get("subject", {})
    if subject.get("entity_label"):
        return str(subject["entity_label"])
    metadata = subject.get("document_metadata") or []
    return str(metadata[0].get("company", "Unknown issuer")) if metadata else "Unknown issuer"


def _alias_index(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entity in config.get("canonical_entities", []):
        for alias in entity.get("aliases", []):
            index[str(alias).casefold()] = entity
    return index


def build(root: Path, output: Path) -> dict[str, Any]:
    source = root / "data/knowledge_bases/v0.1"
    trusted = _jsonl(source / "trusted_fact_records.jsonl")
    failures = _jsonl(source / "failure_records.jsonl")
    if len(trusted) != 149:
        raise ValueError(
            f"release baseline must contain exactly 149 Tier B facts, found {len(trusted)}"
        )
    invalid = [
        row.get("record_id")
        for row in trusted
        if row.get("trust_tier") != "B"
        or row.get("knowledge_status") != "promoted_validated_fact"
        or row.get("provenance", {}).get("simulated") is not False
    ]
    if invalid:
        raise ValueError(f"untrusted or simulated records reached release seed: {invalid[:5]}")

    aliases = json.loads(
        (root / "configs/knowledge/entity_aliases_v0.1.json").read_text(encoding="utf-8")
    )
    alias_index = _alias_index(aliases)
    entity_by_name: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for fact in trusted:
        reported_name = _company(fact)
        alias_group = alias_index.get(reported_name.casefold())
        canonical_name = str(alias_group["canonical_name"]) if alias_group else reported_name
        entity_id = _identifier("issuer", canonical_name.casefold())
        entity = entity_by_name.setdefault(
            canonical_name,
            {
                "schema_version": "0.1",
                "record_kind": "entity",
                "entity_id": entity_id,
                "entity_type": "issuer",
                "canonical_name": canonical_name,
                "canonical_slug": _slug(canonical_name),
                "aliases": [],
                "disambiguation": (
                    alias_group.get("disambiguation")
                    if alias_group
                    else "Exact reported issuer label; fuzzy merging is disabled."
                ),
                "merge_policy": "controlled_alias_only",
            },
        )
        if reported_name not in entity["aliases"]:
            entity["aliases"].append(reported_name)
        predicate = str(fact.get("predicate", {}).get("canonical_key", "unknown"))
        edges.append(
            {
                "schema_version": "0.1",
                "record_kind": "entity_fact_edge",
                "edge_id": _identifier("edge", str(fact["record_id"])),
                "subject_entity_id": entity_id,
                "predicate": predicate,
                "object": {"kind": "literal", "value": fact.get("value")},
                "qualifiers": fact.get("qualifiers", {}),
                "reported_subject_label": reported_name,
                "source_fact_id": fact["record_id"],
                "trust_tier": "B",
                "evidence": fact.get("evidence", []),
            }
        )

    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / "trusted_fact_records.jsonl", trusted)
    _write_jsonl(output / "failure_records.jsonl", failures)
    _write_jsonl(
        output / "entity_registry.jsonl",
        sorted(entity_by_name.values(), key=lambda row: row["entity_id"]),
    )
    _write_jsonl(output / "relation_edges.jsonl", edges)
    shutil.copy2(
        source / "failure_signature_catalog.json", output / "failure_signature_catalog.json"
    )
    for name in (
        "repair_strategy_catalog_v0.1.json",
        "repair_executor_catalog_v0.1.json",
        "boundary_semantic_ontology_v0.1.json",
    ):
        shutil.copy2(root / "configs/knowledge" / name, output / name)
    shutil.copy2(
        root / "data/manifests/release_source_distribution_v0.1.lock.json",
        output / "source_distribution_manifest.lock.json",
    )

    files = sorted(path for path in output.iterdir() if path.is_file())
    manifest = {
        "schema_version": "0.1",
        "record_kind": "sustaintrace_release_knowledge_manifest",
        "default_query_layer": "trusted_tier_b_only",
        "candidate_records_included": False,
        "simulated_records_included": False,
        "counts": {
            "trusted_facts": len(trusted),
            "failure_observations": len(failures),
            "issuer_entities": len(entity_by_name),
            "relation_edges": len(edges),
        },
        "files": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in files
        ],
    }
    (output / "release_manifest.lock.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the audited SustainTrace release seed")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (
        args.output or root / "src/esg_reliable_discovery/release_seed/knowledge_bases/v0.1"
    ).resolve()
    print(json.dumps(build(root, output)["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
