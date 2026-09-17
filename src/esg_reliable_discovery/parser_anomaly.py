from __future__ import annotations

import re
from collections import Counter
from typing import Any

_NUMBER = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?%?")


def _tokens(text: str) -> Counter[str]:
    return Counter(match.group(0).replace(",", "") for match in _NUMBER.finditer(text))


def _multiset_recall(reference: Counter[str], candidate: Counter[str]) -> float:
    total = sum(reference.values())
    if total == 0:
        return 1.0
    recovered = sum(min(count, candidate[token]) for token, count in reference.items())
    return recovered / total


def assess_page_parser_anomaly(
    *,
    mineru_blocks: list[dict[str, Any]],
    native_layout_text: str,
    numeric_recall_threshold: float = 0.95,
    minimum_native_numeric_tokens: int = 3,
) -> dict[str, Any]:
    """Apply a task- and expected-value-independent parser fallback trigger."""
    mineru_text = "\n".join(
        str(block.get("text") or block.get("table_body") or "") for block in mineru_blocks
    )
    native_tokens = _tokens(native_layout_text)
    mineru_tokens = _tokens(mineru_text)
    numeric_recall = _multiset_recall(native_tokens, mineru_tokens)
    mineru_table_detected = any(
        block.get("type") == "table" or bool(block.get("table_body"))
        for block in mineru_blocks
    )
    numeric_loss_detected = (
        sum(native_tokens.values()) >= minimum_native_numeric_tokens
        and numeric_recall < numeric_recall_threshold
    )
    reasons = []
    if mineru_table_detected:
        reasons.append("mineru_table_detected")
    if numeric_loss_detected:
        reasons.append("native_to_mineru_numeric_recall_below_threshold")
    return {
        "fallback_required": bool(reasons),
        "reasons": reasons,
        "numeric_token_recall": numeric_recall,
        "numeric_recall_threshold": numeric_recall_threshold,
        "native_numeric_token_count": sum(native_tokens.values()),
        "mineru_numeric_token_count": sum(mineru_tokens.values()),
        "mineru_table_detected": mineru_table_detected,
        "task_text_used": False,
        "expected_value_used": False,
    }
