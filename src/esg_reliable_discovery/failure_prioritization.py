from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

CHECKPOINT_SIGNATURES = {
    "CLOUD_TRANSPORT_FAILURE",
    "MINERU_LOCALHOST_BIND_SANDBOX_DENIED",
    "MINERU_SANDBOX_LOOPBACK_BIND_DENIED",
    "SANDBOX_LOCALHOST_BIND_DENIED",
    "SANDBOX_LOOPBACK_PORT_DENIED",
    "SANDBOX_NETWORK_DNS_DENIED",
    "MINERU_POSTPROCESS_RUNTIME_ABORT",
    "MINERU_POST_PROCESS_SHUTDOWN_MUTEX_ABORT",
}

SOURCE_INTEGRITY_SIGNATURES = {
    "OFFICIAL_SOURCE_HTTP_403",
    "OFFICIAL_SOURCE_READ_TIMEOUT",
    "ISSUER_SOURCE_ASSURANCE_PERIOD_ANOMALY",
    "ISSUER_SOURCE_ASSURANCE_SIGNATORY_MISSING",
    "ISSUER_SOURCE_ASSURANCE_REPORT_SEPARATE",
    "SOURCE_REPORT_SERIES_ALREADY_USED",
    "SOURCE_REPORT_SERIES_ALREADY_USED_EXACT_SHA256",
}

CATEGORY_IMPACT = {
    "reference_integrity": 100,
    "retrieval_or_evidence_selection": 90,
    "parser_or_document_structure": 85,
    "model_behavior": 80,
    "executor_or_configuration": 75,
    "cloud_transport": 40,
}

MATURITY_ADJUSTMENT = {
    "historical_observation": 25,
    "development_validated": 10,
    "unseen_validated": -30,
}

RISK_PENALTY = {"low": 0, "medium": 5, "high": 15}


def strategy_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for strategy in catalog.get("strategies", []):
        for signature in strategy.get("target_signatures", []):
            if signature in index:
                raise ValueError(f"duplicate strategy for signature: {signature}")
            index[signature] = strategy
    return index


def classify_lane(signature: str) -> str:
    if signature in CHECKPOINT_SIGNATURES:
        return "operational_infrastructure"
    if signature in SOURCE_INTEGRITY_SIGNATURES:
        return "source_acquisition_integrity"
    return "knowledge_capability"


def _episode_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("experiment_id", "")),
        str(record.get("provenance", {}).get("source_artifact", "")),
        str(record.get("failure_signature", "")),
    )


def summarize_failure_signatures(
    records: Iterable[dict[str, Any]],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    strategies = strategy_index(catalog)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["failure_signature"]].append(record)

    summaries: list[dict[str, Any]] = []
    for signature, items in grouped.items():
        strategy = strategies.get(signature)
        if strategy is None:
            raise ValueError(f"observed signature has no strategy: {signature}")
        lane = classify_lane(signature)
        experiments = {str(item.get("experiment_id", "")) for item in items}
        tasks = {str(item.get("task_id", "")) for item in items}
        sources = {
            str(item.get("provenance", {}).get("source_artifact", "")) for item in items
        }
        episodes = {_episode_key(item) for item in items}
        category = str(items[0]["failure_category"])
        risk = str(strategy["risk_level"])
        maturity = str(strategy["maturity"])
        score = (
            CATEGORY_IMPACT.get(category, 60)
            + min(len(experiments), 5) * 10
            + min(len(items), 10) * 2
            + MATURITY_ADJUSTMENT[maturity]
            - RISK_PENALTY[risk]
        )
        if lane != "knowledge_capability":
            score = 0
        summaries.append(
            {
                "schema_version": "0.1",
                "record_kind": "failure_signature_priority",
                "failure_signature": signature,
                "lane": lane,
                "raw_observations": len(items),
                "incident_episodes": len(episodes),
                "affected_experiments": len(experiments),
                "affected_tasks": len(tasks),
                "source_artifacts": len(sources),
                "failure_category": category,
                "failure_owner": str(items[0]["failure_owner"]),
                "strategy_id": strategy["strategy_id"],
                "strategy_maturity": maturity,
                "execution_policy": strategy["execution_policy"],
                "risk_level": risk,
                "research_priority_score": score,
                "capability_rank": None,
            }
        )

    capability = sorted(
        (item for item in summaries if item["lane"] == "knowledge_capability"),
        key=lambda item: (
            -item["research_priority_score"],
            -item["affected_experiments"],
            item["failure_signature"],
        ),
    )
    for rank, item in enumerate(capability, 1):
        item["capability_rank"] = rank
    return sorted(
        summaries,
        key=lambda item: (
            item["lane"] != "knowledge_capability",
            item["capability_rank"] or 10_000,
            -item["raw_observations"],
            item["failure_signature"],
        ),
    )


def lane_totals(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    totals = {
        "knowledge_capability": 0,
        "operational_infrastructure": 0,
        "source_acquisition_integrity": 0,
    }
    for record in records:
        totals[classify_lane(record["failure_signature"])] += 1
    return totals
