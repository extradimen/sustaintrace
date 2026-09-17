import pytest

from esg_reliable_discovery.evidence_repair_triage import (
    classify_evidence_failure,
    plan_evidence_repair,
)


def _failure(signature, note, stage_b=None):
    state = {"semantic_note": note}
    if stage_b is not None:
        state["stage_b"] = stage_b
    return {
        "record_id": f"failure-{signature.lower()}",
        "failure_signature": signature,
        "observed_stage_states": state,
    }


@pytest.mark.parametrize(
    ("failure", "subtype"),
    [
        (
            _failure("EVIDENCE_GROUNDING_MISMATCH", "used rounded headline"),
            "rounded_value_selected",
        ),
        (
            _failure("EVIDENCE_GROUNDING_MISMATCH", "model abstained despite exact cell"),
            "exact_value_present_but_abstained",
        ),
        (
            _failure("EVIDENCE_GROUNDING_MISMATCH", "exact value", "failed_numeric_grounding"),
            "stage_b_handle_binding_failure",
        ),
        (
            _failure("EVIDENCE_GROUNDING_MISMATCH", "truncated excerpt"),
            "truncated_quote",
        ),
        (
            _failure("EVIDENCE_SELECTION_GAP", "model-supplied year was not grounded"),
            "period_anchor_missing",
        ),
        (
            _failure("TARGET_ASSURANCE_WINDOW_INCOMPLETE", "missing issuer and opinion"),
            "assurance_window_incomplete",
        ),
    ],
)
def test_evidence_failure_subtyping(failure, subtype):
    assert classify_evidence_failure(failure) == subtype


def test_locked_results_are_never_repaired():
    failure = _failure("EVIDENCE_GROUNDING_MISMATCH", "used rounded headline")
    plan = plan_evidence_repair(failure, mode="locked_evaluation")
    assert plan["decision"] == "archive_only"
    assert plan["execution_performed"] is False
    assert plan["candidate_output_may_be_semantically_rewritten"] is False


def test_operational_period_reselection_requires_new_lineage():
    failure = _failure("EVIDENCE_SELECTION_GAP", "year was not grounded")
    plan = plan_evidence_repair(failure, mode="operational")
    assert plan["decision"] == "supervised_new_lineage_reselection"
    assert plan["new_lineage_required"] is True
