from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def _quote_is_grounded(quote: str, page_text: str) -> bool:
    """Match a verbatim quote or ordered ellipsis-separated table fragments."""
    normalized_quote = _norm(quote)
    normalized_page = _norm(page_text)
    if "..." not in normalized_quote:
        return normalized_quote in normalized_page
    cursor = 0
    for fragment in (part.strip() for part in normalized_quote.split("...")):
        if not fragment:
            continue
        location = normalized_page.find(fragment, cursor)
        if location < 0:
            return False
        cursor = location + len(fragment)
    return True


def audit_reference_before_candidate(
    *,
    target_pages: list[int],
    reference: dict[str, Any],
    frozen_page_text: dict[int, str],
    required_normalized_fields: list[str],
) -> dict[str, Any]:
    """Fail closed before inference when a simulated reference is not self-consistent."""
    allowed = set(target_pages)
    if set(frozen_page_text) != allowed:
        raise ValueError("v19_frozen_page_text_does_not_match_target_window")
    evidence = reference.get("evidence", [])
    if not evidence:
        raise ValueError("v19_reference_has_no_evidence")
    checked = []
    for item in evidence:
        page = int(item["pdf_page"])
        if page not in allowed:
            raise ValueError(f"v19_reference_page_outside_window:{page}")
        quote = _norm(str(item.get("quote", "")))
        if not quote:
            raise ValueError(f"v19_empty_reference_quote:{page}")
        if not _quote_is_grounded(quote, frozen_page_text[page]):
            raise ValueError(f"v19_reference_quote_not_grounded:{page}")
        checked.append({"pdf_page": page, "quote_grounded": True})
    normalized = reference.get("normalized_value", {})
    missing = [key for key in required_normalized_fields if key not in normalized]
    if missing:
        raise ValueError(f"v19_missing_required_normalized_fields:{','.join(missing)}")
    return {
        "status": "passed",
        "target_pages": sorted(allowed),
        "evidence_checks": checked,
        "required_normalized_fields": required_normalized_fields,
        "candidate_inference_released": True,
        "reference_visible_to_candidate": False,
    }
