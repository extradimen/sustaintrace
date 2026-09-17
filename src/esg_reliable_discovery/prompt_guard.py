from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .hashing import sha256_file


def _normalized(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def _contains_phrase(text: str, phrase: str, minimum_length: int = 24) -> bool:
    normalized_phrase = _normalized(phrase)
    return len(normalized_phrase) >= minimum_length and normalized_phrase in text


def audit_instruction_prompt(
    prompt: str,
    gold_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    """Detect answer-derived content in instruction text, excluding runtime source material."""
    normalized_prompt = _normalized(prompt)
    findings: list[dict[str, str]] = []
    for card in gold_cards:
        finding_id = card.get("finding_id", "unknown")
        for field, value in (
            ("claim", card.get("claim")),
            ("confidence_basis", card.get("confidence_basis")),
            ("falsification_condition", card.get("falsification_condition")),
        ):
            if value and _contains_phrase(normalized_prompt, str(value)):
                findings.append({"finding_id": finding_id, "field": field, "type": "phrase"})
        for evidence_kind in ("supporting_evidence", "contrary_evidence"):
            for evidence in card.get(evidence_kind, []):
                excerpt = evidence.get("excerpt")
                if excerpt and _contains_phrase(normalized_prompt, excerpt):
                    findings.append(
                        {"finding_id": finding_id, "field": evidence_kind, "type": "excerpt"}
                    )

        metric = card.get("metric") or {}
        metric_name = _normalized(metric.get("name", ""))
        value = metric.get("reported_value")
        value_tokens = re.findall(r"[-+]?\d+(?:\.\d+)?", str(value)) if value is not None else []
        if len(metric_name) >= 8 and metric_name in normalized_prompt:
            for token in value_tokens:
                numeric_boundary = rf"(?<![\d.]){re.escape(token)}(?!\d|\.\d)"
                if re.search(numeric_boundary, normalized_prompt):
                    findings.append(
                        {
                            "finding_id": finding_id,
                            "field": "metric.reported_value",
                            "type": "metric_value_pair",
                        }
                    )
                    break

    return {
        "passed": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "scope": "instruction_prompt_only",
        "runtime_sources_excluded": True,
    }


def audit_prompt_paths(prompt_path: str | Path, gold_directory: str | Path) -> dict[str, Any]:
    prompt_path = Path(prompt_path)
    gold_paths = sorted(Path(gold_directory).glob("*.json"))
    cards = [json.loads(path.read_text(encoding="utf-8")) for path in gold_paths]
    result = audit_instruction_prompt(prompt_path.read_text(encoding="utf-8"), cards)
    result.update(
        {
            "prompt_path": str(prompt_path),
            "prompt_sha256": sha256_file(prompt_path),
            "gold_card_count": len(cards),
        }
    )
    return result
