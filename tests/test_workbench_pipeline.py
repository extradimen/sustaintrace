from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.workbench_pipeline import analyze_mineru_output
from esg_reliable_discovery.workbench_repair import plan_workbench_repairs


def test_local_analysis_keeps_candidates_untrusted_and_coordinates(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed/report/auto"
    parsed.mkdir(parents=True)
    blocks = [
        {
            "type": "table",
            "table_body": (
                "<table><tr><td>Water consumption (m3)</td><td>2025</td></tr>"
                "<tr><td>Total</td><td>309,545</td></tr></table>"
            ),
            "bbox": [10, 20, 300, 400],
            "page_idx": 4,
        },
        {"type": "chart", "content": "", "bbox": [1, 2, 3, 4], "page_idx": 8},
    ]
    (parsed / "report_content_list.json").write_text(json.dumps(blocks), encoding="utf-8")

    summary = analyze_mineru_output(
        tmp_path / "parsed", tmp_path / "analysis", source_sha256="a" * 64
    )

    assert summary["candidate_records"] == 1
    assert summary["failure_records"] == 1
    candidate = json.loads((tmp_path / "analysis/candidate_records.jsonl").read_text())
    assert candidate["knowledge_status"] == "candidate_not_trusted"
    assert candidate["promotion"]["eligible"] is False
    assert candidate["evidence"]["pdf_page"] == 5
    assert candidate["evidence"]["bbox"] == [10, 20, 300, 400]
    assert summary["atomic_fact_candidates"] == 1
    assert summary["projection_validated_candidates"] == 1
    atomic = json.loads((tmp_path / "analysis/atomic_fact_candidates.jsonl").read_text())
    schema = json.loads(
        Path("schemas/knowledge/fact-record-v0.1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(atomic)
    assert atomic["value"] == 309545
    assert atomic["qualifiers"]["reference_period"] == 2025
    assert atomic["qualifiers"]["normalized_unit"] == "m3"
    audit = json.loads((tmp_path / "analysis/projection_audit_records.jsonl").read_text())
    assert audit["status"] == "passed"
    gate = json.loads((tmp_path / "analysis/promotion_gate_records.jsonl").read_text())
    assert gate["promotion_performed"] is False
    assert gate["decision"] == "blocked"
    plan = json.loads((tmp_path / "analysis/repair_plan_records.jsonl").read_text())
    schema = json.loads(
        Path("schemas/knowledge/workbench-repair-plan-v1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(plan)
    assert plan["decision"] == "supervised_candidate"
    assert plan["execution_performed"] is False
    assert plan["promotion_performed"] is False
    assert plan["cloud_transfer_performed"] is False
    dispatch = json.loads(
        (tmp_path / "analysis/repair_dispatch_records.jsonl").read_text()
    )
    dispatch_schema = json.loads(
        Path("schemas/knowledge/workbench-repair-dispatch-v1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(dispatch_schema).validate(dispatch)
    assert dispatch["decision"] == "blocked"
    assert "source_frozen_hash_valid" in dispatch["blocking_reasons"]
    assert dispatch["execution_started"] is False


def test_local_analysis_records_no_candidate_failure(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed/report/auto"
    parsed.mkdir(parents=True)
    (parsed / "report_content_list.json").write_text(
        json.dumps([{"type": "text", "text": "Introduction", "page_idx": 0}]),
        encoding="utf-8",
    )
    summary = analyze_mineru_output(
        tmp_path / "parsed", tmp_path / "analysis", source_sha256="b" * 64
    )
    assert summary["candidate_records"] == 0
    failure = json.loads((tmp_path / "analysis/failure_records.jsonl").read_text())
    assert failure["failure_signature"] == "PARSED_WITHOUT_ESG_NUMERIC_EVIDENCE"


def test_ambiguous_period_is_quarantined_before_promotion(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed/report/auto"
    parsed.mkdir(parents=True)
    (parsed / "report_content_list.json").write_text(
        json.dumps([{
            "type": "table",
            "table_body": (
                "<table><tr><td>GHG emissions tCO2e</td><td>2024</td>"
                "<td>2025</td><td>9,500</td></tr></table>"
            ),
            "bbox": [1, 2, 3, 4],
            "page_idx": 2,
        }]),
        encoding="utf-8",
    )
    summary = analyze_mineru_output(
        tmp_path / "parsed", tmp_path / "analysis", source_sha256="c" * 64
    )
    assert summary["projection_validated_candidates"] == 0
    assert summary["projection_quarantined"] == 1
    failure = json.loads((tmp_path / "analysis/failure_records.jsonl").read_text())
    assert failure["failure_signature"] == "SLOT_PROJECTION_INCOMPLETE"
    assert "PERIOD_BINDING_AMBIGUOUS" in failure["blocking_reasons"]
    plan = json.loads((tmp_path / "analysis/repair_plan_records.jsonl").read_text())
    routes = {route["blocking_reason"]: route for route in plan["routes"]}
    assert routes["PERIOD_BINDING_AMBIGUOUS"]["strategy_id"] == "RS-PARSER-FALLBACK"
    assert plan["decision"] == "supervised_candidate"


def test_unknown_repair_reason_fails_closed() -> None:
    catalog = json.loads(
        Path("configs/knowledge/repair_strategy_catalog_v0.1.json").read_text(
            encoding="utf-8"
        )
    )
    plans = plan_workbench_repairs(
        failures=[],
        promotion_gates=[{
            "fact_record_id": "fact-unknown",
            "dry_run_id": "gate-unknown",
            "decision": "blocked",
            "blocking_reasons": ["UNKNOWN_NEW_FAILURE"],
        }],
        strategy_catalog=catalog,
    )
    assert plans[0]["decision"] == "blocked_fail_closed"
    assert plans[0]["unresolved_blocking_reasons"] == ["UNKNOWN_NEW_FAILURE"]
    assert plans[0]["execution_performed"] is False


def test_frozen_source_allows_supervised_repair_dispatch(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\nfrozen")
    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    parsed = tmp_path / "parsed/report/auto"
    parsed.mkdir(parents=True)
    (parsed / "report_content_list.json").write_text(
        json.dumps([{
            "type": "table",
            "table_body": (
                "<table><tr><td>Water consumption (m3)</td><td>2025</td></tr>"
                "<tr><td>Total</td><td>309,545</td></tr></table>"
            ),
            "bbox": [10, 20, 300, 400],
            "page_idx": 4,
        }]),
        encoding="utf-8",
    )
    summary = analyze_mineru_output(
        tmp_path / "parsed",
        tmp_path / "analysis",
        source_sha256=digest,
        source_path=source,
        workspace_root=tmp_path,
    )
    dispatch = json.loads(
        (tmp_path / "analysis/repair_dispatch_records.jsonl").read_text()
    )
    assert summary["repair_dispatch_ready"] == 1
    assert dispatch["decision"] == "ready_for_supervised_execution"
    assert dispatch["checks"]["source_frozen_hash_valid"] is True
    assert dispatch["execution_started"] is False


def test_unique_two_axis_table_binding_executes_job_local_repair(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\nfrozen table")
    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    parsed = tmp_path / "parsed/report/auto"
    parsed.mkdir(parents=True)
    (parsed / "report_content_list.json").write_text(
        json.dumps([{
            "type": "table",
            "table_body": (
                "<table><tr><th>Indicator</th><th>Unit</th><th>2024</th><th>2025</th></tr>"
                "<tr><td>Water consumption</td><td>m3</td><td>100</td><td>120</td></tr>"
                "</table>"
            ),
            "bbox": [10, 20, 300, 400],
            "page_idx": 4,
        }]),
        encoding="utf-8",
    )
    summary = analyze_mineru_output(
        tmp_path / "parsed",
        tmp_path / "analysis",
        source_sha256=digest,
        source_path=source,
        workspace_root=tmp_path,
    )
    repaired = [
        json.loads(line)
        for line in (tmp_path / "analysis/repaired_fact_candidates.jsonl")
        .read_text()
        .splitlines()
    ]
    executions = [
        json.loads(line)
        for line in (tmp_path / "analysis/repair_execution_records.jsonl")
        .read_text()
        .splitlines()
    ]
    reviews = [
        json.loads(line)
        for line in (tmp_path / "analysis/promotion_review_records.jsonl")
        .read_text()
        .splitlines()
    ]
    assert summary["repaired_fact_candidates"] == 2
    assert summary["promotion_reviews_pending"] == 2
    assert {item["qualifiers"]["reference_period"] for item in repaired} == {2024, 2025}
    assert all(item["trust_tier"] == "C" for item in repaired)
    assert all(item["promotion"]["eligible"] is False for item in repaired)
    assert all(item["state"] == "postvalidation_passed" for item in executions)
    assert all(item["trusted_layer_modified"] is False for item in executions)
    assert all(item["state"] == "pending_review" for item in reviews)
    assert all(item["promotion_performed"] is False for item in reviews)


def test_duplicate_table_values_are_rolled_back_without_derived_fact(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\nduplicate table value")
    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    parsed = tmp_path / "parsed/report/auto"
    parsed.mkdir(parents=True)
    (parsed / "report_content_list.json").write_text(
        json.dumps([{
            "type": "table",
            "table_body": (
                "<table><tr><th>Indicator</th><th>Unit</th><th>2024</th><th>2025</th></tr>"
                "<tr><td>Water consumption</td><td>m3</td><td>100</td><td>100</td></tr>"
                "</table>"
            ),
            "bbox": [10, 20, 300, 400],
            "page_idx": 4,
        }]),
        encoding="utf-8",
    )
    summary = analyze_mineru_output(
        tmp_path / "parsed",
        tmp_path / "analysis",
        source_sha256=digest,
        source_path=source,
        workspace_root=tmp_path,
    )
    executions = [
        json.loads(line)
        for line in (tmp_path / "analysis/repair_execution_records.jsonl")
        .read_text()
        .splitlines()
    ]
    assert summary["repaired_fact_candidates"] == 0
    assert summary["repair_executions_rolled_back"] == 2
    assert all(item["state"] == "rolled_back" for item in executions)
    assert all(item["rollback_performed"] is True for item in executions)
    assert all(item["derived_fact_record_id"] is None for item in executions)
    assert summary["promotion_reviews_pending"] == 0
