from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evaluation/rq3_controlled_repair"


def test_rq3_evidence_metrics_preserve_distinct_denominators() -> None:
    metrics = json.loads(
        (OUTPUT / "SustainTrace_RQ3_Repair_Evidence_Metrics_v1.0.lock.json").read_text()
    )
    component = metrics["component_validation"]
    control = metrics["execution_control"]
    assert component["trials"] == 13
    assert component["components"] == 6
    assert component["distinct_reports"] == 7
    assert component["contract_passes"] == 6
    assert component["contract_failures"] == 7
    assert component["components_with_failure_then_new_unseen_positive_pass"] == 3
    assert component["unsafe_fact_writes"] == 0
    assert component["unsafe_trust_promotions"] == 0
    assert control["cases"] == 4
    assert control["safe_terminal_outcomes"] == 4
    assert control["safe_terminal_rate"] == 1.0
    assert control["source_artifact_modifications"] == 0


def test_rq3_cases_are_traceable_and_do_not_claim_writes() -> None:
    with (OUTPUT / "SustainTrace_RQ3_Repair_Evidence_Cases_v1.0.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 13
    assert len({row["component"] for row in rows}) == 6
    assert len({row["report_id"] for row in rows}) == 7
    assert all(row["fact_write_performed"] == "False" for row in rows)
    assert all(row["trust_promotion_performed"] == "False" for row in rows)
    for row in rows:
        path = ROOT / row["result_path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["result_sha256"]


def test_rq3_completion_and_output_hashes_are_valid() -> None:
    completion = json.loads(
        (OUTPUT / "SustainTrace_RQ3_Repair_Evidence_Completion_v1.0.lock.json").read_text()
    )
    assert completion["status"] == "complete"
    assert completion["historical_experiments_rerun"] is False
    assert completion["historical_results_rescored"] is False
    for record in completion["source_artifacts"] + completion["outputs"]:
        path = ROOT / record["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
