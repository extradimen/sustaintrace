from esg_reliable_discovery.failure_prioritization import (
    classify_lane,
    lane_totals,
    summarize_failure_signatures,
)


def _strategy(strategy_id, signatures, maturity="historical_observation", risk="medium"):
    return {
        "strategy_id": strategy_id,
        "target_signatures": signatures,
        "maturity": maturity,
        "risk_level": risk,
        "execution_policy": "supervised",
    }


def _failure(signature, experiment, task, category="model_behavior"):
    return {
        "failure_signature": signature,
        "experiment_id": experiment,
        "task_id": task,
        "failure_category": category,
        "failure_owner": "candidate_model",
        "provenance": {"source_artifact": f"data/results/{experiment}.json"},
    }


def test_infrastructure_volume_does_not_outrank_capability_failure():
    records = [
        _failure(
            "MINERU_SANDBOX_LOOPBACK_BIND_DENIED",
            "run-a",
            f"page-{index}",
            "executor_or_configuration",
        )
        for index in range(20)
    ]
    records.append(_failure("EVIDENCE_GROUNDING_MISMATCH", "p2", "task-1"))
    catalog = {
        "strategies": [
            _strategy("RS-CHECKPOINT-RESUME", ["MINERU_SANDBOX_LOOPBACK_BIND_DENIED"]),
            _strategy("RS-EVIDENCE-RESELECTION", ["EVIDENCE_GROUNDING_MISMATCH"]),
        ]
    }
    summary = summarize_failure_signatures(records, catalog)
    evidence = next(item for item in summary if item["failure_signature"].startswith("EVIDENCE"))
    mineru = next(item for item in summary if item["failure_signature"].startswith("MINERU"))
    assert evidence["capability_rank"] == 1
    assert evidence["research_priority_score"] > 0
    assert mineru["capability_rank"] is None
    assert mineru["research_priority_score"] == 0


def test_lane_totals_preserve_all_observations():
    records = [
        _failure("EVIDENCE_GROUNDING_MISMATCH", "p2", "task-1"),
        _failure(
            "MINERU_SANDBOX_LOOPBACK_BIND_DENIED",
            "run-a",
            "page-1",
            "executor_or_configuration",
        ),
        _failure("OFFICIAL_SOURCE_HTTP_403", "run-b", "download", "cloud_transport"),
    ]
    assert classify_lane("OFFICIAL_SOURCE_HTTP_403") == "source_acquisition_integrity"
    assert lane_totals(records) == {
        "knowledge_capability": 1,
        "operational_infrastructure": 1,
        "source_acquisition_integrity": 1,
    }
