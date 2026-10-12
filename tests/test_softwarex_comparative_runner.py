from __future__ import annotations

import json
from pathlib import Path

import pytest

from esg_reliable_discovery import softwarex_comparative_runner as runner
from esg_reliable_discovery.ollama_client import OllamaResult
from esg_reliable_discovery.softwarex_comparative import SLOTS
from esg_reliable_discovery.softwarex_comparative_runner import (
    CONTRACT_V2_ID,
    ComparativeContext,
    ModelBehaviorError,
    SourcePreflightError,
    apply_full_admission_gate,
    apply_full_admission_gate_v3,
    build_messages,
    build_messages_v2,
    contract_v2_instructions,
    execute_task_paired_v3,
    parse_model_decision,
    quote_is_grounded,
)


def task(stratum: str = "direct_claim") -> dict:
    return {
        "task_id": "T1",
        "company": "Example plc",
        "report_title": "Annual Report 2025",
        "stratum": stratum,
        "candidate_predicate": "scope_1_emissions",
        "candidate_claim": "Example plc reported 10 tCO2e for 2025.",
        "candidate_evidence": {"pdf_page": 7, "quote": "10 tCO2e"},
        "instruction": "Verify the candidate.",
    }


def context(*, grounded: bool = True) -> ComparativeContext:
    return ComparativeContext(
        task_id="T1",
        document_path=Path("report.pdf"),
        pages=(7,),
        page_text={7: "Scope 1 emissions 10 tCO2e"},
        evidence_page_is_permitted=True,
        evidence_quote_is_grounded=grounded,
    )


def decision(action: str = "admit") -> dict:
    return {
        "support_label": "fully_supported",
        "knowledge_base_action": action,
        "slots": {slot: "Y" for slot in SLOTS},
    }


def test_prompt_profiles_share_evidence_but_only_structured_profiles_define_labels() -> None:
    plain = build_messages(task(), context(), "plain_model_verifier")
    ungated = build_messages(task(), context(), "ungated_pipeline_verifier")
    assert "10 tCO2e" in plain[1]["content"]
    assert "10 tCO2e" in ungated[1]["content"]
    assert "Support labels:" not in plain[1]["content"]
    assert "Support labels:" in ungated[1]["content"]


def test_abstention_semantics_are_explicit() -> None:
    messages = build_messages(task("abstention_audit"), context(), "sustaintrace_full")
    assert "proposed refusal is correct" in messages[1]["content"]
    assert "all abstention-audit slots NA" in messages[1]["content"]


def test_strict_parser_rejects_prose_and_extra_fields() -> None:
    payload = decision()
    assert parse_model_decision(json.dumps(payload)) == payload
    with pytest.raises(ModelBehaviorError, match="strict JSON"):
        parse_model_decision("Here is the answer: " + json.dumps(payload))
    payload["explanation"] = "not allowed"
    with pytest.raises(ModelBehaviorError, match="top-level"):
        parse_model_decision(json.dumps(payload))


def test_full_gate_blocks_unsafe_admission_without_rewriting_support() -> None:
    safe = apply_full_admission_gate(decision(), context())
    assert safe["knowledge_base_action"] == "admit"
    blocked = apply_full_admission_gate(decision(), context(grounded=False))
    assert blocked["support_label"] == "fully_supported"
    assert blocked["knowledge_base_action"] == "reject"


def test_v3_gate_preserves_safe_admission_and_emits_audit() -> None:
    guarded, audit = apply_full_admission_gate_v3(
        decision(),
        context(),
        stratum="direct_claim",
        admission_contract={
            "allow_admission": True,
            "candidate_component_count": 1,
            "required_slots": ["Subject", "Predicate", "Value", "Period", "Unit"],
        },
    )
    assert guarded["knowledge_base_action"] == "admit"
    assert audit["outcome"] == "admission_preserved"
    assert audit["reason_codes"] == []


def test_v3_gate_blocks_missing_required_slot_without_rewriting_slots() -> None:
    candidate = decision()
    candidate["slots"]["Unit"] = "N"
    guarded, audit = apply_full_admission_gate_v3(
        candidate,
        context(),
        stratum="direct_claim",
        admission_contract={
            "allow_admission": True,
            "candidate_component_count": 1,
            "required_slots": ["Subject", "Predicate", "Value", "Period", "Unit"],
        },
    )
    assert guarded["knowledge_base_action"] == "correct_then_review"
    assert guarded["slots"]["Unit"] == "N"
    assert audit["outcome"] == "admission_blocked"
    assert "required_slots_are_supported" in audit["reason_codes"]
    assert "no_negative_slot" in audit["reason_codes"]


def test_v3_gate_rejects_admission_for_nonadmissible_task_class() -> None:
    guarded, audit = apply_full_admission_gate_v3(
        decision(),
        context(),
        stratum="abstention_audit",
        admission_contract={
            "allow_admission": False,
            "candidate_component_count": 0,
            "required_slots": [],
        },
    )
    assert guarded["knowledge_base_action"] == "reject"
    assert audit["outcome"] == "admission_blocked"
    assert "task_class_allows_admission" in audit["reason_codes"]
    assert "not_abstention_audit" in audit["reason_codes"]


def test_v3_gate_rejects_structurally_compound_claim() -> None:
    guarded, audit = apply_full_admission_gate_v3(
        decision(),
        context(),
        stratum="compound_claim",
        admission_contract={
            "allow_admission": True,
            "candidate_component_count": 2,
            "required_slots": ["Subject", "Predicate", "Value"],
        },
    )
    assert guarded["knowledge_base_action"] == "reject"
    assert "claim_is_atomic" in audit["reason_codes"]


def test_v3_gate_requires_a_valid_frozen_contract() -> None:
    with pytest.raises(ModelBehaviorError):
        parse_model_decision("not json")
    with pytest.raises(SourcePreflightError, match="allow_admission"):
        apply_full_admission_gate_v3(
            decision(),
            context(),
            stratum="direct_claim",
            admission_contract={"required_slots": [], "candidate_component_count": 1},
        )


def test_paired_v3_calls_model_once_and_derives_both_conditions(monkeypatch) -> None:
    class Client:
        calls = 0

        def chat(self, messages, *, schema, think):
            self.calls += 1
            return OllamaResult(
                request={"messages": messages, "schema": schema, "think": think},
                response={
                    "message": {"content": json.dumps(decision())},
                    "prompt_eval_count": 100,
                    "eval_count": 20,
                },
                elapsed_seconds=0.25,
                request_sha256="a" * 64,
            )

    frozen_task = task()
    frozen_task["admission_contract"] = {
        "allow_admission": True,
        "candidate_component_count": 1,
        "required_slots": ["Subject", "Predicate", "Value", "Period", "Unit"],
    }
    monkeypatch.setattr(runner, "build_context", lambda _task, _root: context())
    client = Client()
    output = execute_task_paired_v3(frozen_task, Path("."), client)
    assert client.calls == 1
    assert output["ungated_decision"] == output["sustaintrace_full_decision"]
    assert output["gate_audit"]["outcome"] == "admission_preserved"


def test_quote_grounding_normalizes_markup_and_layout_order() -> None:
    quote = "GHG includes CO<sub>2</sub>, CH<sub>4</sub> and N<sub>2</sub>O."
    source = "N2O is reported elsewhere in the table. GHG includes CO2 and CH4."
    assert quote_is_grounded(quote, source)
    assert not quote_is_grounded("water withdrawal was 999 million m3", source)


def test_v2_contract_names_every_exact_field_and_allowed_label() -> None:
    contract = contract_v2_instructions()
    assert CONTRACT_V2_ID.endswith("v2.0")
    for field in ("support_label", "knowledge_base_action", *SLOTS):
        assert field in contract
    for label in (
        "fully_supported",
        "partially_supported",
        "unsupported",
        "cannot_assess",
        "source_defect",
        "admit",
        "correct_then_review",
        "reject",
        "abstain_or_conflict",
    ):
        assert label in contract
    assert "Do not use Markdown" in contract
    assert "wrapper such as decision" in contract


def test_v2_visible_messages_are_condition_invariant() -> None:
    messages = build_messages_v2(task(), context())
    assert "Condition:" not in messages[1]["content"]
    assert "10 tCO2e" in messages[1]["content"]
    assert set(json.loads('{"Subject":"Y","Predicate":"Y","Value":"Y",'
                          '"Period":"Y","Unit":"Y","Boundary/method":"Y",'
                          '"Evidence coordinates":"Y"}')) == set(SLOTS)
