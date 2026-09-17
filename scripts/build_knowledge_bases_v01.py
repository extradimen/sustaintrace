from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import (
    development_result_to_repair_observation,
    reference_to_fact_records,
    result_to_failure_records,
    sha256_file,
    validate_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic v0.1 ESG knowledge bases")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def phase_number(path: Path) -> int | None:
    match = re.search(r"/p(\d+)_simulated/", path.as_posix())
    return int(match.group(1)) if match else None


def select_result_files(root: Path) -> list[Path]:
    selected: list[Path] = []
    for phase in range(2, 24):
        candidates = sorted((root / "data/results").glob(f"p{phase}_*result.lock.json"))
        if not candidates:
            continue
        final = [path for path in candidates if "final_result" in path.name]
        selected.append(final[-1] if final else candidates[-1])
    return selected


def select_reference_files(root: Path) -> list[Path]:
    paths = []
    for path in sorted((root / "data/annotations").glob("p*_simulated/*.json")):
        phase = phase_number(path)
        if phase is None or not 2 <= phase <= 23:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload.get("task_id"), str) and payload.get("normalized_value") is not None:
            paths.append(path)
    return paths


def select_development_results(root: Path) -> list[Path]:
    results = root / "data/results"
    patterns = ("v*_development*.lock.json", "v*_exposed*_development*.lock.json")
    return sorted({path for pattern in patterns for path in results.glob(pattern)})


def select_increment_files(root: Path, suffix: str) -> list[Path]:
    return sorted((root / "data/knowledge_bases/v0.1/increments").glob(f"*_{suffix}.jsonl"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def select_source_registries(root: Path) -> list[Path]:
    selected = []
    for phase in range(2, 24):
        candidates = sorted((root / "data/manifests").glob(f"p{phase}_source_registry*.json"))
        if candidates:
            selected.append(candidates[-1])
    return selected


def build_document_index(paths: list[Path]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for candidate in payload.get("candidates", []):
            if not isinstance(candidate, dict) or not isinstance(candidate.get("document_id"), str):
                continue
            index[candidate["document_id"]] = {
                key: candidate[key]
                for key in ("document_id", "company", "title", "language", "sha256", "local_path")
                if key in candidate
            }
    return index


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    content = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )
    path.write_text(content, encoding="utf-8")


def aggregate_sha256(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256_file(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def source_inventory(paths: list[Path], root: Path) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(paths)
    ]


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output = (args.output or root / "data/knowledge_bases/v0.1").resolve()
    output.mkdir(parents=True, exist_ok=True)

    fact_sources = select_reference_files(root)
    result_sources = select_result_files(root)
    repair_sources = select_development_results(root)
    source_registries = select_source_registries(root)
    document_index = build_document_index(source_registries)

    facts = [
        record
        for path in fact_sources
        for record in reference_to_fact_records(path, root, document_index)
    ]
    failures = [
        record for path in result_sources for record in result_to_failure_records(path, root)
    ]
    repairs = [development_result_to_repair_observation(path, root) for path in repair_sources]
    fact_increment_sources = select_increment_files(root, "fact_records")
    failure_increment_sources = select_increment_files(root, "failure_records")
    facts.extend(record for path in fact_increment_sources for record in load_jsonl(path))
    failures.extend(record for path in failure_increment_sources for record in load_jsonl(path))

    schema_dir = root / "schemas/knowledge"
    fact_schema = json.loads((schema_dir / "fact-record-v0.1.schema.json").read_text())
    failure_schema = json.loads((schema_dir / "failure-record-v0.1.schema.json").read_text())
    repair_schema = json.loads((schema_dir / "repair-observation-v0.1.schema.json").read_text())
    validate_records(facts, fact_schema)
    validate_records(failures, failure_schema)
    validate_records(repairs, repair_schema)

    fact_path = output / "fact_records.jsonl"
    failure_path = output / "failure_records.jsonl"
    repair_path = output / "repair_observations.jsonl"
    write_jsonl(fact_path, facts)
    write_jsonl(failure_path, failures)
    write_jsonl(repair_path, repairs)
    signature_groups: dict[str, list[dict[str, str]]] = {}
    for record in failures:
        signature_groups.setdefault(record["failure_signature"], []).append(
            {"experiment_id": record["experiment_id"], "task_id": record["task_id"]}
        )
    signature_catalog = {
        "schema_version": "0.1",
        "status": "deterministically_grouped_pending_strategy_adjudication",
        "signature_count": len(signature_groups),
        "failure_record_count": len(failures),
        "signatures": [
            {"signature": signature, "count": len(examples), "examples": examples}
            for signature, examples in sorted(signature_groups.items())
        ],
    }
    signature_path = output / "failure_signature_catalog.json"
    signature_path.write_text(
        json.dumps(signature_catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "0.1",
        "status": "deterministic_initial_migration_complete",
        "scope": "P2-P23 historical artifacts; no experiment modified or rescored",
        "trust_policy": {
            "fact_default": "reference_candidate",
            "simulated_reference_tier": "C",
            "automatic_fact_promotion": False,
            "automatic_repair_execution": False,
        },
        "counts": {
            "reference_source_files": len(fact_sources),
            "fact_records": len(facts),
            "selected_locked_result_files": len(result_sources),
            "failure_records": len(failures),
            "development_result_files": len(repair_sources),
            "repair_observations": len(repairs),
            "failure_signatures": len(signature_groups),
            "source_registry_files": len(source_registries),
            "indexed_documents": len(document_index),
            "fact_increment_files": len(fact_increment_sources),
            "failure_increment_files": len(failure_increment_sources),
        },
        "source_sets": {
            "facts_sha256": aggregate_sha256(fact_sources, root),
            "locked_results_sha256": aggregate_sha256(result_sources, root),
            "development_results_sha256": aggregate_sha256(repair_sources, root),
            "source_registries_sha256": aggregate_sha256(source_registries, root),
            "fact_increments_sha256": aggregate_sha256(fact_increment_sources, root),
            "failure_increments_sha256": aggregate_sha256(failure_increment_sources, root),
        },
        "source_inventory": {
            "fact_sources": source_inventory(fact_sources, root),
            "locked_results": source_inventory(result_sources, root),
            "development_results": source_inventory(repair_sources, root),
            "source_registries": source_inventory(source_registries, root),
            "fact_increments": source_inventory(fact_increment_sources, root),
            "failure_increments": source_inventory(failure_increment_sources, root),
        },
        "outputs": {
            "fact_records": {
                "path": fact_path.relative_to(root).as_posix(),
                "sha256": sha256_file(fact_path),
            },
            "failure_records": {
                "path": failure_path.relative_to(root).as_posix(),
                "sha256": sha256_file(failure_path),
            },
            "repair_observations": {
                "path": repair_path.relative_to(root).as_posix(),
                "sha256": sha256_file(repair_path),
            },
            "failure_signature_catalog": {
                "path": signature_path.relative_to(root).as_posix(),
                "sha256": sha256_file(signature_path),
            },
        },
        "next_gates": [
            "independent fact promotion audit against frozen source evidence",
            "adjudicate failure signatures and merge duplicates",
            "convert repair observations into bounded versioned strategies",
            "implement controller validation and rollback before enabling automatic repair",
        ],
    }
    manifest_path = output / "migration_manifest.lock.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
