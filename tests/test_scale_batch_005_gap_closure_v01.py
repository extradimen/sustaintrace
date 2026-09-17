from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_scale_batch_atomic_projection_v01 import (  # noqa: E402
    native_row_header_present,
    normalize,
)


def test_wrapped_row_header_survives_interleaved_native_column() -> None:
    native = normalize(
        "Total GHG emissions (market-based) unrelated right column content "
        "per net revenue (tCO2/€ m sales)"
    )
    assert native_row_header_present(
        "Total GHG emissions (market-based) per net revenue (tCO2/€ m sales)", native
    )


def test_gap_repair_is_scenario_candidate_not_metric() -> None:
    records = [
        json.loads(line)
        for line in (
            ROOT
            / "data/knowledge_bases/v0.1/increments/scale_batch_005_gap_repair_fact_records.jsonl"
        )
        .read_text()
        .splitlines()
        if line
    ]
    assert len(records) == 1
    record = records[0]
    assert record["trust_tier"] == "C"
    assert "biodiversity declines" in record["value"].casefold()
    assert record["promotion"]["eligible"] is False
