import json
from pathlib import Path

from esg_reliable_discovery.prompt_guard import audit_instruction_prompt, audit_prompt_paths

ROOT = Path(__file__).parents[1]


def _gold_card() -> dict:
    return {
        "finding_id": "gold-001",
        "claim": "The company reported a highly specific hidden benchmark answer.",
        "confidence_basis": "Direct evidence on the hidden evaluation page.",
        "falsification_condition": "A corrected official table would falsify this finding.",
        "metric": {"name": "bribery allegation count", "reported_value": 77},
        "supporting_evidence": [
            {"excerpt": "This is a sufficiently long hidden evidence excerpt for testing."}
        ],
        "contrary_evidence": [],
    }


def test_clean_prompt_passes():
    result = audit_instruction_prompt(
        "Extract only evidence-supported ESG findings and preserve reporting boundaries.",
        [_gold_card()],
    )
    assert result["passed"] is True
    assert result["findings"] == []


def test_exact_gold_claim_is_detected():
    card = _gold_card()
    result = audit_instruction_prompt(f"Answer: {card['claim']}", [card])
    assert result["passed"] is False
    assert result["findings"][0]["field"] == "claim"


def test_metric_and_value_pair_is_detected_but_metric_alone_is_allowed():
    card = _gold_card()
    assert audit_instruction_prompt("Find the bribery allegation count.", [card])["passed"]
    result = audit_instruction_prompt("The bribery allegation count is 77.", [card])
    assert result["passed"] is False
    assert result["findings"][0]["type"] == "metric_value_pair"


def test_integer_answer_does_not_match_decimal_or_larger_number():
    card = _gold_card()
    assert audit_instruction_prompt("The bribery allegation count is 77.5.", [card])["passed"]
    assert audit_instruction_prompt("The bribery allegation count is 177.", [card])["passed"]


def test_frozen_p0_prompt_has_no_closed_answer_leakage():
    result = audit_prompt_paths(
        ROOT / "prompts/p0_evidence_discovery_v0.1.txt",
        ROOT / "data/annotations/p0_gold",
    )
    assert result["passed"] is True, json.dumps(result, indent=2)
    assert result["gold_card_count"] == 6
