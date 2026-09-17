from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "data/annotations/p17_simulated"
CONTRACT_OUTPUT = ROOT / "configs/framework/p17_slot_contracts_RESUME02_v0.1.lock.json"
GOLD_OUTPUT = ROOT / "data/annotations/p17_simulated/p17_atomic_slot_gold_RESUME02_v0.1.lock.json"


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, member in value.items():
            path = f"{prefix}::{key}" if prefix else key
            result.update(flatten(member, path))
        return result
    if isinstance(value, list):
        return {prefix: " | ".join(str(item) for item in value)}
    return {prefix: value}


def unit_for(slot_id: str) -> str | None:
    lowered = slot_id.casefold()
    if "percent" in lowered:
        return "percent"
    if "tco2e" in lowered:
        return "t CO2e"
    if "work_hours" in lowered:
        return "work_hours"
    if any(token in lowered for token in ("consumption", "recycled", "stored", "withdrawal")):
        return "m3"
    count_tokens = ("count", "total", "male", "female", "employees", "fatalities")
    if any(token in lowered for token in count_tokens):
        return "count"
    return None


def main() -> None:
    if CONTRACT_OUTPUT.exists() or GOLD_OUTPUT.exists():
        raise RuntimeError("refusing_to_overwrite_p17_contract_or_gold")
    contracts: dict[str, list[dict[str, Any]]] = {}
    gold: dict[str, dict[str, Any]] = {}
    for path in sorted(REFERENCE_ROOT.glob("P17-*.json")):
        reference = json.loads(path.read_text(encoding="utf-8"))
        task_id = reference["task_id"]
        flat = flatten(reference["normalized_value"])
        gold[task_id] = flat
        task_contracts = []
        for slot_id, value in flat.items():
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            value_type = "number" if is_number else "string"
            contract = {
                "slot_id": slot_id,
                "predicate_id": f"esg_p17::{task_id.casefold()}::{slot_id}",
                "value_type": value_type,
            }
            unit = unit_for(slot_id)
            if unit is not None and value_type == "number":
                contract["canonical_unit"] = unit
            task_contracts.append(contract)
        contracts[task_id] = task_contracts
    CONTRACT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_OUTPUT.write_text(
        json.dumps(
            {
                "schema_version": "2.6",
                "experiment_id": "P17-V26-UNSEEN-LOCKBOX-V01",
                "status": "frozen_before_candidate_inference",
                "derivation": (
                    "deterministic recursive atomic projection of the six frozen normalized "
                    "references; dictionary keys become ::-separated slot paths and lists "
                    "become ordered pipe-separated strings"
                ),
                "contracts": contracts,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    GOLD_OUTPUT.write_text(
        json.dumps(
            {
                "schema_version": "2.6",
                "experiment_id": "P17-V26-UNSEEN-LOCKBOX-V01",
                "status": "frozen_atomic_scoring_projection_before_candidate_inference",
                "source_reference_freeze": (
                    "data/manifests/"
                    "p17_simulated_reference_freeze_RESUME02_v0.1.lock.json"
                ),
                "values": gold,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"tasks": len(contracts), "slots": sum(map(len, contracts.values()))}))


if __name__ == "__main__":
    main()
