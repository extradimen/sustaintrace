from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_fixtures import DIAGNOSTIC_SHAPES, select_exposed_fixture

ROOT = Path(__file__).resolve().parents[1]
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
QUEUE = ROOT / "data/knowledge_bases/v0.1/second_repair_queue.jsonl"
OUTPUT = ROOT / "artifacts/second_repair_fixtures_v0.1"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    summary_path = OUTPUT / "fixture_selection_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_exposed_repair_fixtures")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    gaps = read_jsonl(GAPS)
    facts = {item["record_id"]: item for item in read_jsonl(FACTS)}
    queue = {item["gap_id"]: item for item in read_jsonl(QUEUE)}
    parent_hashes = {
        "knowledge_gaps": sha256_file(GAPS),
        "fact_records": sha256_file(FACTS),
        "second_repair_queue": sha256_file(QUEUE),
    }
    records = []
    attempts = {}
    for signature in DIAGNOSTIC_SHAPES:
        fixture, selection_attempts = select_exposed_fixture(
            signature=signature,
            gaps=gaps,
            facts=facts,
            queue_items=queue,
            root=ROOT,
            parent_hashes=parent_hashes,
        )
        path = OUTPUT / f"{signature.lower()}.fixture.json"
        path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records.append(
            {
                "gap_signature": signature,
                "gap_id": fixture["gap_id"],
                "fact_record_id": fixture["fact_record_id"],
                "fixture_path": str(path.relative_to(ROOT)),
                "fixture_sha256": sha256_file(path),
            }
        )
        attempts[signature] = selection_attempts
    summary = {
        "schema_version": "0.1",
        "status": "four_exposed_read_only_fixtures_prepared_not_executed",
        "parent_hashes": parent_hashes,
        "fixtures": records,
        "selection_attempts": attempts,
        "fixture_count": len(records),
        "blocked_candidates_preserved": sum(
            item["decision"] == "blocked"
            for items in attempts.values()
            for item in items
        ),
        "execution_performed": False,
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "cloud_transmission_performed": False,
        "next_gate": "implement and validate the four read-only diagnostic adapters",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"fixtures": len(records), "blocked": summary["blocked_candidates_preserved"]}
        )
    )


if __name__ == "__main__":
    main()
