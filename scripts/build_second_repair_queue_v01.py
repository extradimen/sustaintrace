from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_queue import (
    build_second_repair_queue,
    summarize_second_repair_queue,
)

ROOT = Path(__file__).resolve().parents[1]
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
RANKINGS = ROOT / "data/knowledge_bases/v0.1/repair_gap_rankings.jsonl"
OUTPUT = ROOT / "data/knowledge_bases/v0.1/second_repair_queue.jsonl"
SUMMARY = ROOT / "data/knowledge_bases/v0.1/second_repair_queue_summary.lock.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    if OUTPUT.exists() or SUMMARY.exists():
        raise FileExistsError("refusing_to_overwrite_second_repair_queue")
    gaps_sha = sha256_file(GAPS)
    rankings_sha = sha256_file(RANKINGS)
    records = build_second_repair_queue(
        gaps=read_jsonl(GAPS),
        rankings=read_jsonl(RANKINGS),
        gaps_sha256=gaps_sha,
        rankings_sha256=rankings_sha,
    )
    OUTPUT.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )
    summary = {
        "schema_version": "0.1",
        "status": "second_repair_queue_frozen_no_execution",
        **summarize_second_repair_queue(records),
        "inputs": {
            "knowledge_gaps_sha256": gaps_sha,
            "repair_rankings_sha256": rankings_sha,
        },
        "output": {
            "path": "data/knowledge_bases/v0.1/second_repair_queue.jsonl",
            "sha256": sha256_file(OUTPUT),
        },
        "execution_performed": False,
        "semantic_repair_performed": False,
        "next_gate": "build exposed-only deterministic fixtures for read-only binders",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summarize_second_repair_queue(records), ensure_ascii=False))


if __name__ == "__main__":
    main()
