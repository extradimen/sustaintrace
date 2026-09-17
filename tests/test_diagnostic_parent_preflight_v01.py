import hashlib
import json
from pathlib import Path

from esg_reliable_discovery.diagnostic_preflight import (
    assess_diagnostic_parent_binding,
    run_preflighted_read_only_diagnostic,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


def _stores(tmp_path: Path) -> tuple[Path, Path]:
    facts = tmp_path / "facts.jsonl"
    gaps = tmp_path / "gaps.jsonl"
    _write_jsonl(facts, [{"record_id": "fact-1", "value": 3}])
    _write_jsonl(
        gaps,
        [
            {
                "gap_id": "gap-1",
                "fact_record_id": "fact-1",
                "gap_signature": "CALCULATION_LINEAGE_INCOMPLETE",
            }
        ],
    )
    return facts, gaps


def _fixture(**updates: str) -> dict:
    fixture = {
        "fixture_id": "fixture-1",
        "fact_record_id": "fact-1",
        "gap_id": "gap-1",
        "gap_signature": "CALCULATION_LINEAGE_INCOMPLETE",
    }
    fixture.update(updates)
    return fixture


def test_registered_parent_binding_records_store_hashes(tmp_path: Path) -> None:
    facts, gaps = _stores(tmp_path)
    result = assess_diagnostic_parent_binding(
        fact_record_id="fact-1",
        gap_id="gap-1",
        requested_signature="CALCULATION_LINEAGE_INCOMPLETE",
        satisfied_dimensions=["calculation_lineage"],
        fact_store_path=facts,
        gap_store_path=gaps,
    )
    assert result["status"] == "passed"
    assert result["blocking_reasons"] == []
    assert result["immutable_stores"]["facts"]["sha256"] == hashlib.sha256(
        facts.read_bytes()
    ).hexdigest()


def test_missing_gap_blocks_before_adapter_invocation(tmp_path: Path) -> None:
    facts, gaps = _stores(tmp_path)
    calls = []

    def runner(*args):
        calls.append(args)
        return {"status": "passed"}

    result = run_preflighted_read_only_diagnostic(
        fixture=_fixture(gap_id="gap-unregistered"),
        satisfied_dimensions=["calculation_lineage"],
        root=tmp_path,
        fact_store_path=facts,
        gap_store_path=gaps,
        diagnostic_runner=runner,
    )
    assert result["status"] == "blocked_before_execution"
    assert result["adapter_invocation_count"] == 0
    assert result["preflight"]["blocking_reasons"] == ["PARENT_GAP_NOT_REGISTERED"]
    assert calls == []


def test_registered_binding_invokes_adapter_exactly_once(tmp_path: Path) -> None:
    facts, gaps = _stores(tmp_path)
    calls = []

    def runner(fixture, fact, root):
        calls.append((fixture, fact, root))
        return {"status": "passed"}

    result = run_preflighted_read_only_diagnostic(
        fixture=_fixture(),
        satisfied_dimensions=["calculation_lineage"],
        root=tmp_path,
        fact_store_path=facts,
        gap_store_path=gaps,
        diagnostic_runner=runner,
    )
    assert result["status"] == "completed"
    assert result["adapter_invocation_count"] == 1
    assert len(calls) == 1
    assert calls[0][1]["record_id"] == "fact-1"


def test_mismatched_fact_signature_and_dimension_fail_closed(tmp_path: Path) -> None:
    facts, gaps = _stores(tmp_path)
    result = assess_diagnostic_parent_binding(
        fact_record_id="fact-missing",
        gap_id="gap-1",
        requested_signature="FIELD_EVIDENCE_BINDING_INCOMPLETE",
        satisfied_dimensions=["calculation_lineage"],
        fact_store_path=facts,
        gap_store_path=gaps,
    )
    assert result["status"] == "blocked"
    assert result["blocking_reasons"] == [
        "PARENT_FACT_NOT_REGISTERED",
        "PARENT_GAP_FACT_MISMATCH",
        "PARENT_GAP_SIGNATURE_MISMATCH",
        "REQUESTED_DIMENSION_UNAUTHORIZED",
    ]
