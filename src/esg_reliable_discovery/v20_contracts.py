from __future__ import annotations

import re
from typing import Any

ALLOWED_VALUE_TYPES = {"number", "string", "boolean", "array", "object"}
REQUIRED_FIELDS = {"slot_id", "predicate_id", "value_type"}


def validate_slot_contracts_before_candidate(
    contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fail closed on incomplete or ambiguous Stage B contracts before model access."""
    if not contracts:
        raise ValueError("v20_slot_contracts_empty")
    slot_ids: list[str] = []
    for index, contract in enumerate(contracts):
        missing = sorted(REQUIRED_FIELDS - set(contract))
        if missing:
            raise ValueError(
                f"v20_slot_contract_missing_fields:{index}:{','.join(missing)}"
            )
        slot_id = contract["slot_id"]
        if not isinstance(slot_id, str) or not slot_id.strip():
            raise ValueError(f"v20_slot_id_invalid:{index}")
        slot_ids.append(slot_id)
        predicate_id = contract["predicate_id"]
        if not isinstance(predicate_id, str) or not predicate_id.strip():
            raise ValueError(f"v20_predicate_id_invalid:{slot_id}")
        value_type = contract["value_type"]
        if value_type not in ALLOWED_VALUE_TYPES:
            raise ValueError(f"v20_value_type_unsupported:{slot_id}:{value_type}")
        if value_type in {"array", "object"}:
            if not contract.get("member_contract"):
                raise ValueError(f"v20_collection_member_contract_missing:{slot_id}")
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("v20_duplicate_slot_id")
    return {
        "status": "passed",
        "slot_count": len(contracts),
        "collection_slot_count": sum(
            item["value_type"] in {"array", "object"} for item in contracts
        ),
        "candidate_inference_released": True,
    }


def require_controlled_conflict_slots(
    contracts: list[dict[str, Any]], required_conflict_ids: list[str]
) -> None:
    available = {item["slot_id"] for item in contracts}
    missing = sorted(set(required_conflict_ids) - available)
    if missing:
        raise ValueError(f"v20_required_conflict_slots_missing:{','.join(missing)}")


def validate_evidence_handle_pages(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Ensure every structured MinerU/page-line handle names its actual PDF page."""
    checked = []
    for item in evidence:
        handle = str(item.get("handle", ""))
        match = re.match(r"^[MP](\d+)-", handle)
        if match is None:
            raise ValueError(f"v20_evidence_handle_page_unparseable:{handle}")
        encoded_page = int(match.group(1))
        actual_page = int(item["page"])
        if encoded_page != actual_page:
            raise ValueError(
                f"v20_evidence_handle_page_mismatch:{handle}:{actual_page}"
            )
        checked.append({"handle": handle, "page": actual_page})
    return {"status": "passed", "checked": checked}
