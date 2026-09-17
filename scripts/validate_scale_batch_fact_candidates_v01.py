from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_001_fact_records.jsonl"
DIAGNOSTICS = ROOT / "data/results/scale_batch_001_diagnostics.lock.json"
OUTPUT = ROOT / "data/knowledge_bases/v0.1/increments/scale_batch_001_evidence_validations.jsonl"
SUMMARY = ROOT / "data/results/scale_batch_001_evidence_gate.lock.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def normalize(text: str) -> str:
    text = re.sub(r"[|*_#<>]", " ", text)
    return " ".join(text.split()).casefold()


def main() -> None:
    facts = load_jsonl(FACTS)
    diagnostics = json.loads(DIAGNOSTICS.read_text(encoding="utf-8"))
    native_pages = {
        item["document_id"]: (ROOT / item["layout_text_path"])
        .read_text(encoding="utf-8", errors="replace")
        .split("\f")
        for item in diagnostics["documents"]
    }
    records = []
    for fact in facts:
        quote = fact["evidence"][0]["quote"]
        document_id = fact["subject"]["document_ids"][0]
        page = fact["evidence"][0]["pdf_page"]
        markdown_path = ROOT / fact["provenance"]["source_artifact"]
        markdown = markdown_path.read_text(encoding="utf-8", errors="replace")
        native = native_pages[document_id][page - 1]
        parser_exact = quote in markdown
        native_normalized = normalize(quote) in normalize(native)
        records.append(
            {
                "schema_version": "0.1",
                "validation_id": "validation-"
                + hashlib.sha256(fact["record_id"].encode()).hexdigest()[:24],
                "fact_record_id": fact["record_id"],
                "document_id": document_id,
                "pdf_page": page,
                "mineru_quote_exact": parser_exact,
                "native_text_normalized_exact": native_normalized,
                "source_identity_verified": True,
                "semantic_atomic_projection_complete": False,
                "promotion_decision": "hold_tier_c",
                "promotion_reason": "semantic_atomic_projection_and_independent_review_pending",
            }
        )
    OUTPUT.write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in records),
        encoding="utf-8",
    )
    summary = {
        "schema_version": "0.1",
        "batch_id": "KB-SCALE-BATCH-001-RESUME01",
        "status": "evidence_gate_complete_no_automatic_promotion",
        "candidate_count": len(records),
        "mineru_exact_count": sum(item["mineru_quote_exact"] for item in records),
        "native_normalized_exact_count": sum(
            item["native_text_normalized_exact"] for item in records
        ),
        "held_tier_c_count": len(records),
        "promoted_tier_b_count": 0,
        "validation_output": OUTPUT.relative_to(ROOT).as_posix(),
        "validation_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "policy": {
            "no_semantic_guessing": True,
            "no_automatic_promotion_without_atomic_projection": True,
            "locked_experiments_modified": False,
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
