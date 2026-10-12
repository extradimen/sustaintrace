from __future__ import annotations

import hashlib

import pytest

from esg_reliable_discovery.softwarex_comparative_runner import (
    CONTRACT_V2_ID,
    contract_v2_instructions,
)


def _report(document_id: str, sha256: str) -> dict:
    return {
        "document_id": document_id,
        "company": "Example plc",
        "title": "Example Report 2025",
        "local_path": "data/raw/example.pdf",
        "sha256": sha256,
        "file_size_bytes": 100,
    }


def test_v2_rejects_any_e1_document_hash_or_task_overlap() -> None:
    from scripts.prepare_softwarex_comparative_benchmark_v2 import assert_unseen

    e1 = {
        "reports": [_report("E1-DOC", "a" * 64)],
        "tasks": [{"task_id": "E1-TASK"}],
    }
    with pytest.raises(ValueError, match="document_ids"):
        assert_unseen(
            {"reports": [_report("E1-DOC", "b" * 64)], "tasks": []}, e1
        )
    with pytest.raises(ValueError, match="document_hashes"):
        assert_unseen(
            {"reports": [_report("E2-DOC", "a" * 64)], "tasks": []}, e1
        )
    with pytest.raises(ValueError, match="task_ids"):
        assert_unseen(
            {"reports": [_report("E2-DOC", "b" * 64)], "tasks": [{"task_id": "E1-TASK"}]},
            e1,
        )


def test_v2_contract_has_stable_identifier_and_digest() -> None:
    assert CONTRACT_V2_ID == "SUSTAINTRACE-SOFTX-EXECUTABLE-CONTRACT-v2.0"
    digest = hashlib.sha256(contract_v2_instructions().encode("utf-8")).hexdigest()
    assert len(digest) == 64
