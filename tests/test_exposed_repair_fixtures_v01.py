import json
from pathlib import Path

import pytest

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.repair_fixtures import select_exposed_fixture


def test_selector_blocks_missing_native_source_then_uses_next_hash_valid_candidate(tmp_path):
    annotation = tmp_path / "annotation.json"
    annotation.write_text("{}")
    report = tmp_path / "report.pdf"
    report.write_bytes(b"pdf")
    facts = {
        "fact-" + "1" * 24: {
            "record_id": "fact-" + "1" * 24,
            "provenance": {
                "source_artifact": "annotation.json",
                "source_sha256": sha256_file(annotation),
            },
            "subject": {"document_metadata": [{"sha256": "0" * 64}]},
            "evidence": [],
        },
        "fact-" + "2" * 24: {
            "record_id": "fact-" + "2" * 24,
            "provenance": {
                "source_artifact": "annotation.json",
                "source_sha256": sha256_file(annotation),
            },
            "subject": {
                "document_metadata": [
                    {
                        "local_path": "report.pdf",
                        "sha256": sha256_file(report),
                    }
                ]
            },
            "evidence": [{"pdf_page": 2, "quote": "42"}],
        },
    }
    gaps = [
        {
            "gap_id": "gap-" + "1" * 24,
            "fact_record_id": "fact-" + "1" * 24,
            "task_id": "T1",
            "gap_signature": "NATIVE_PDF_CORROBORATION_INCOMPLETE",
        },
        {
            "gap_id": "gap-" + "2" * 24,
            "fact_record_id": "fact-" + "2" * 24,
            "task_id": "T2",
            "gap_signature": "NATIVE_PDF_CORROBORATION_INCOMPLETE",
        },
    ]
    queue = {
        item["gap_id"]: {"queue_id": "repair-queue-" + "a" * 24, "validator_id": "V"}
        for item in gaps
    }
    fixture, attempts = select_exposed_fixture(
        signature="NATIVE_PDF_CORROBORATION_INCOMPLETE",
        gaps=gaps,
        facts=facts,
        queue_items=queue,
        root=tmp_path,
        parent_hashes={"parent": "f" * 64},
    )
    assert attempts[0]["decision"] == "blocked"
    assert attempts[0]["blocking_reasons"] == ["unique_native_source_path_missing"]
    assert fixture["gap_id"] == "gap-" + "2" * 24
    assert fixture["execution_performed"] is False
    assert fixture["diagnostic_contract"]["fact_write_allowed"] is False


def test_selector_fails_closed_for_unknown_signature(tmp_path):
    with pytest.raises(ValueError, match="unsupported_fixture_signature"):
        select_exposed_fixture(
            signature="UNKNOWN",
            gaps=[],
            facts={},
            queue_items={},
            root=tmp_path,
            parent_hashes={},
        )


def test_frozen_fixture_summary_preserves_hashes_and_no_execution():
    root = Path(__file__).resolve().parents[1]
    summary_path = (
        root / "artifacts/second_repair_fixtures_v0.1/fixture_selection_summary.lock.json"
    )
    if not summary_path.exists():
        pytest.skip("fixture builder has not run")
    summary = json.loads(summary_path.read_text())
    assert summary["fixture_count"] == 4
    assert summary["execution_performed"] is False
    assert summary["fact_write_performed"] is False
    for item in summary["fixtures"]:
        assert sha256_file(root / item["fixture_path"]) == item["fixture_sha256"]
