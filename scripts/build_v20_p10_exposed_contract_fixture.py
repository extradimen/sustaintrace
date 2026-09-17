from __future__ import annotations

import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.v20_contracts import (
    require_controlled_conflict_slots,
    validate_slot_contracts_before_candidate,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "configs/framework/p10_slot_contracts_v0.1.lock.json"
OUTPUT = ROOT / "configs/framework/v2.0_p10_exposed_contract_fixture.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    fixture = {
        "schema_version": "2.0-development",
        "status": "exposed_failure_development_fixture_not_a_p10_erratum",
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": sha256(SOURCE),
        "contracts": {},
        "audit": {},
    }
    for task_id, contracts in source["contracts"].items():
        updated = []
        for original in contracts:
            contract = dict(original)
            contract.setdefault("predicate_id", f"esg_disclosure::{contract['slot_id']}")
            if contract["value_type"] in {"array", "object"}:
                contract["member_contract"] = {
                    "canonical_id": "nonempty_string",
                    "evidence_handle": "frozen_handle",
                    "verbatim_value": "grounded_nonempty_string",
                }
            updated.append(contract)
        fixture["contracts"][task_id] = updated
        fixture["audit"][task_id] = validate_slot_contracts_before_candidate(updated)
    require_controlled_conflict_slots(
        fixture["contracts"]["P10-ASSURE-001"],
        [
            "page_range_introduction",
            "page_range_scope_statement",
            "range_conflict_status",
        ],
    )
    fixture["controlled_conflict_gate"] = "passed"
    OUTPUT.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(sha256(OUTPUT))


if __name__ == "__main__":
    main()
