from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.read_only_diagnostics import run_read_only_diagnostic

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "artifacts/second_repair_fixtures_v0.1"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
OUTPUT = ROOT / "artifacts/second_repair_diagnostics_RESUME01_v0.1"
PARENT_ATTEMPT = ROOT / "artifacts/second_repair_diagnostics_v0.1/diagnostic_summary.lock.json"


def main() -> None:
    summary_path = OUTPUT / "diagnostic_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_read_only_diagnostics")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    facts = {
        item["record_id"]: item
        for item in (
            json.loads(line) for line in FACTS.read_text(encoding="utf-8").splitlines() if line
        )
    }
    records = []
    for fixture_path in sorted(FIXTURES.glob("*.fixture.json")):
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        if fixture["parent_hashes"]["fact_records"] != sha256_file(FACTS):
            raise ValueError("fact_store_parent_hash_mismatch")
        diagnostic = run_read_only_diagnostic(fixture, facts[fixture["fact_record_id"]], ROOT)
        output_path = OUTPUT / fixture_path.name.replace(".fixture", ".diagnostic")
        output_path.write_text(
            json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        records.append(
            {
                "gap_signature": fixture["gap_signature"],
                "status": diagnostic["status"],
                "path": str(output_path.relative_to(ROOT)),
                "sha256": sha256_file(output_path),
            }
        )
    summary = {
        "schema_version": "0.1",
        "status": "exposed_read_only_diagnostics_complete",
        "resume_lineage": {
            "parent_attempt": str(PARENT_ATTEMPT.relative_to(ROOT)),
            "parent_sha256": sha256_file(PARENT_ATTEMPT),
            "reason": "row header included a preceding numeric cell in the initial diagnostic",
            "reused_inputs": True,
        },
        "records": records,
        "passed": sum(item["status"] == "passed" for item in records),
        "blocked": sum(item["status"] == "blocked" for item in records),
        "fact_records_sha256": sha256_file(FACTS),
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "semantic_inference_performed": False,
        "cloud_transmission_performed": False,
        "next_gate": "add deterministic positive and negative screens for period and unit binding",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"passed": summary["passed"], "blocked": summary["blocked"]}))


if __name__ == "__main__":
    main()
