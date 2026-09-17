import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tier_b_policy_rejects_same_pdf_parser_agreement():
    policy = json.loads(
        (ROOT / "configs/knowledge/tier_b_independent_source_policy_v0.1.json").read_text()
    )
    assert policy["promotion_rule"]["automatic"] is False
    assert policy["promotion_rule"]["requires_all_dimensions"] is True
    assert any("second parser" in item for item in policy["ineligible_as_independent"])
    assert set(policy["required_match_dimensions"]) >= {
        "entity",
        "metric",
        "period",
        "unit",
        "scope_boundary",
    }
