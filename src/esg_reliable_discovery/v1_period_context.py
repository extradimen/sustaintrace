from __future__ import annotations

import re
from typing import Any

_BLOCK = re.compile(r"^(?P<prefix>M\d{3}-B)(?P<number>\d{4})$")
_DATE_YEAR = re.compile(r"(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/(?P<year>20\d{2})")


def add_auditable_period_context(
    handles: list[dict[str, Any]], reporting_year: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach only explicit nearby dates or a frozen reporting-year label to numeric blocks."""
    indexed = {item["handle"]: item for item in handles}
    augmented: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    for item in handles:
        copied = dict(item)
        match = _BLOCK.match(item["handle"])
        text = item.get("normalized_text", item.get("verbatim_text", ""))
        if not match or not re.fullmatch(r"[\d,.]+", text.strip()):
            augmented.append(copied)
            continue
        prefix = match.group("prefix")
        number = int(match.group("number"))
        candidates = []
        for offset in (-2, -1, 1, 2):
            neighbor_id = f"{prefix}{number + offset:04d}"
            neighbor = indexed.get(neighbor_id)
            if neighbor:
                candidates.append((offset, neighbor_id, neighbor.get("verbatim_text", "")))
        linked_year = None
        linked_handle = None
        link_rule = None
        for _, neighbor_id, neighbor_text in candidates:
            date = _DATE_YEAR.search(neighbor_text)
            if date:
                linked_year = int(date.group("year"))
                linked_handle = neighbor_id
                link_rule = "same_page_within_two_blocks_explicit_end_date"
                break
        if linked_year is None and any(
            "reporting year" in neighbor_text.casefold() for _, _, neighbor_text in candidates
        ):
            linked_year = reporting_year
            linked_handle = next(
                neighbor_id
                for _, neighbor_id, neighbor_text in candidates
                if "reporting year" in neighbor_text.casefold()
            )
            link_rule = "same_page_within_two_blocks_reporting_year_label"
        if linked_year is not None:
            existing = copied.get("table_header_context") or ""
            copied["table_header_context"] = f"{existing} {linked_year}".strip()
            links.append(
                {
                    "value_handle": item["handle"],
                    "period_handle": linked_handle,
                    "period_year": linked_year,
                    "rule": link_rule,
                }
            )
        augmented.append(copied)
    return augmented, links
