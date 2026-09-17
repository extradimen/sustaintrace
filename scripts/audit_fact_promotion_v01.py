from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import (
    audit_fact_source_grounding,
    build_native_page_index,
    build_parser_page_index,
    sha256_file,
    validate_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit v0.1 fact candidates against parser pages")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def select_latest_by_phase(paths: list[Path]) -> list[Path]:
    by_phase: dict[int, list[Path]] = {}
    for path in paths:
        match = re.search(r"p(\d+)_", path.name)
        if match:
            by_phase.setdefault(int(match.group(1)), []).append(path)
    return [sorted(items)[-1] for phase, items in sorted(by_phase.items()) if 2 <= phase <= 23]


def fallback_document_ids(root: Path) -> dict[int, str]:
    result = {}
    source_registries = select_latest_by_phase(
        list((root / "data/manifests").glob("p*_source_registry*.json"))
    )
    for path in source_registries:
        phase = int(re.search(r"p(\d+)_", path.name).group(1))
        candidates = json.loads(path.read_text()).get("candidates", [])
        if len(candidates) == 1 and isinstance(candidates[0].get("document_id"), str):
            result[phase] = candidates[0]["document_id"]
    return result


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    kb_dir = root / "data/knowledge_bases/v0.1"
    facts = load_jsonl(kb_dir / "fact_records.jsonl")
    registries = select_latest_by_phase(
        list((root / "data/manifests").glob("p*_mineru_target_registry*.json"))
    )
    document_fallbacks = fallback_document_ids(root)
    parser_index = build_parser_page_index(registries, root, document_fallbacks)
    native_registries = [
        root / "data/manifests/p12_mineru_failure_and_native_fallback_v0.1.lock.json",
        root / "data/manifests/p13_native_target_registry_v0.1.lock.json",
    ]
    parser_index.update(build_native_page_index(native_registries, root, document_fallbacks))
    audits = [audit_fact_source_grounding(fact, parser_index) for fact in facts]
    schema = json.loads(
        (root / "schemas/knowledge/fact-promotion-audit-v0.1.schema.json").read_text()
    )
    validate_records(audits, schema)

    audit_path = kb_dir / "fact_promotion_audits.jsonl"
    write_jsonl(audit_path, audits)
    status_counts: dict[str, int] = {}
    for audit in audits:
        status = audit["source_grounding_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "schema_version": "0.1",
        "status": "source_grounding_audit_complete_semantic_promotion_pending",
        "fact_records": len(facts),
        "parser_registry_files": len(registries),
        "native_fallback_registry_files": len(native_registries),
        "indexed_parser_pages": len(parser_index),
        "source_grounding_status_counts": status_counts,
        "promoted_to_tier_b": 0,
        "reason_no_automatic_promotion": (
            "Historical references bind task-level evidence bundles, not each normalized field "
            "to an "
            "independent cell or literal. Quote presence cannot prove field-level semantics."
        ),
        "artifacts": {
            "fact_records": {
                "path": "data/knowledge_bases/v0.1/fact_records.jsonl",
                "sha256": sha256_file(kb_dir / "fact_records.jsonl"),
            },
            "promotion_audits": {
                "path": "data/knowledge_bases/v0.1/fact_promotion_audits.jsonl",
                "sha256": sha256_file(audit_path),
            },
        },
        "next_gate": "construct field-level evidence bindings for source-grounded candidates",
    }
    summary_path = kb_dir / "promotion_audit_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary["source_grounding_status_counts"], sort_keys=True))


if __name__ == "__main__":
    main()
