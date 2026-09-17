from __future__ import annotations

from typing import Any


def classify_failure(
    *, stage: str, error_type: str, error_message: str, model_call_started: bool
) -> dict[str, Any]:
    """Assign one mutually exclusive failure owner without converting it into a score."""
    message = error_message.casefold()
    if any(token in message for token in ("no route to host", "timed out", "http 502")):
        category = "cloud_transport"
        owner = "infrastructure"
        score_as_model_failure = False
    elif any(
        token in message
        for token in (
            "slot_contract_missing",
            "predicate_id",
            "collection_member_contract_missing",
            "required_conflict_slots_missing",
        )
    ):
        category = "frozen_configuration"
        owner = "framework"
        score_as_model_failure = False
    elif any(token in message for token in ("parser", "mineru", "structure_unrecoverable")):
        category = "parser"
        owner = "document_pipeline"
        score_as_model_failure = False
    elif model_call_started:
        category = "model_behavior"
        owner = "candidate_model"
        score_as_model_failure = True
    else:
        category = "executor"
        owner = "framework"
        score_as_model_failure = False
    return {
        "stage": stage,
        "error_type": error_type,
        "category": category,
        "owner": owner,
        "model_call_started": model_call_started,
        "score_as_model_failure": score_as_model_failure,
        "retry_policy": (
            "separate_audited_infrastructure_recovery_only"
            if category == "cloud_transport"
            else "no_retry_in_locked_experiment"
        ),
    }
