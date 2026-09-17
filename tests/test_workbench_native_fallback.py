from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from esg_reliable_discovery.mineru_adapter import MinerUError
from esg_reliable_discovery.workbench_api import WorkbenchService
from esg_reliable_discovery.workbench_native_fallback import parse_with_native_pdf_layout


def _workspace(tmp_path: Path) -> Path:
    knowledge = tmp_path / "data/knowledge_bases/v0.1"
    knowledge.mkdir(parents=True)
    for name in ("fact_records.jsonl", "trusted_fact_records.jsonl", "failure_records.jsonl"):
        (knowledge / name).write_text("", encoding="utf-8")
    return tmp_path


def _verified_asset_audit() -> dict[str, object]:
    return {
        "state": "verified",
        "asset_count": 1,
        "asset_manifest_sha256": "a" * 64,
    }


def test_native_pdf_fallback_preserves_page_geometry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\nfixture")
    xhtml = """<doc><page width="612" height="792"><flow><block><line>
    <word xMin="10" yMin="20" xMax="60" yMax="30">Water</word>
    <word xMin="70" yMin="20" xMax="100" yMax="30">100</word>
    </line></block></flow></page></doc>"""

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        Path(command[-1]).write_text(xhtml, encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    record = parse_with_native_pdf_layout(source, tmp_path / "fallback")
    blocks = json.loads(
        (tmp_path / "fallback/native_fallback_content_list.json").read_text()
    )
    assert record["state"] == "completed"
    assert record["cloud_transfer_performed"] is False
    assert blocks[0]["text"] == "Water 100"
    assert blocks[0]["bbox"] == [0.0, 0.0, 612.0, 792.0]
    assert blocks[0]["native_layout_lines"][0]["bbox"] == [10.0, 20.0, 100.0, 30.0]


def test_workbench_falls_back_after_mineru_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    service._mineru_asset_audit = _verified_asset_audit()
    payload = b"%PDF-1.7\nminimal fixture"
    job = service.create_job(
        io.BytesIO(payload), content_length=len(payload), filename="report.pdf"
    )
    job_root = service.jobs_root / job["job_id"]

    def fail_mineru(*_: object, **__: object) -> None:
        parsed = job_root / "parsed"
        parsed.mkdir()
        (parsed / "esg_rd_mineru_run.json").write_text(
            json.dumps({"returncode": 1}), encoding="utf-8"
        )
        raise MinerUError("missing model weights")

    def fallback(*_: object, **__: object) -> dict[str, object]:
        parsed = job_root / "parsed_native_fallback"
        parsed.mkdir()
        (parsed / "native_fallback_content_list.json").write_text(
            json.dumps([{
                "type": "text",
                "text": "Water withdrawal m3 2025 100",
                "page_idx": 0,
                "bbox": [0, 0, 100, 100],
            }]),
            encoding="utf-8",
        )
        (parsed / "native_pdf_fallback_run.json").write_text(
            json.dumps({"state": "completed"}), encoding="utf-8"
        )
        return {"output_files": ["native_fallback_content_list.json"]}

    monkeypatch.setattr("esg_reliable_discovery.workbench_api.parse_with_mineru", fail_mineru)
    monkeypatch.setattr(
        "esg_reliable_discovery.workbench_api.parse_with_native_pdf_layout", fallback
    )
    service._parse_job(job["job_id"])
    completed = service.get_job(job["job_id"])
    assert completed["state"] == "local_analysis_completed"
    assert completed["parser_record"].endswith("parsed/esg_rd_mineru_run.json")
    assert completed["parser_fallback_record"].endswith("native_pdf_fallback_run.json")
    assert [item["event"] for item in completed["events"]][-3:] == [
        "native_pdf_fallback_started",
        "native_pdf_fallback_completed",
        "local_analysis_completed",
    ]
    assert completed["policy"]["cloud_transfer_authorized"] is False


def test_workbench_passes_locked_tools_config_to_mineru(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    service._mineru_asset_audit = _verified_asset_audit()
    payload = b"%PDF-1.7\nminimal fixture"
    job = service.create_job(
        io.BytesIO(payload), content_length=len(payload), filename="report.pdf"
    )
    job_root = service.jobs_root / job["job_id"]

    def parse(*_: object, **kwargs: object) -> dict[str, object]:
        assert kwargs["tools_config"] == service.mineru_tools_config
        parsed = job_root / "parsed"
        parsed.mkdir()
        (parsed / "report_content_list.json").write_text(
            json.dumps([{"type": "text", "text": "Introduction", "page_idx": 0}]),
            encoding="utf-8",
        )
        (parsed / "esg_rd_mineru_run.json").write_text("{}", encoding="utf-8")
        return {"output_files": ["report_content_list.json"]}

    monkeypatch.setattr("esg_reliable_discovery.workbench_api.parse_with_mineru", parse)
    service._parse_job(job["job_id"])
    completed = service.get_job(job["job_id"])
    assert completed["state"] == "local_analysis_completed"
    assert completed["mineru_asset_audit"]["state"] == "verified"
    assert "mineru_assets_verified" in [item["event"] for item in completed["events"]]


def test_failed_job_resume_does_not_repeat_mineru(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = WorkbenchService(_workspace(tmp_path))
    payload = b"%PDF-1.7\nminimal fixture"
    job = service.create_job(
        io.BytesIO(payload), content_length=len(payload), filename="report.pdf"
    )
    job_root = service.jobs_root / job["job_id"]
    audit = job_root / "parsed/esg_rd_mineru_run.json"
    audit.parent.mkdir()
    audit.write_text(json.dumps({"returncode": 1}), encoding="utf-8")
    job["state"] = "parse_failed"
    (job_root / "job.json").write_text(json.dumps(job), encoding="utf-8")

    monkeypatch.setattr(
        "esg_reliable_discovery.workbench_api.parse_with_mineru",
        lambda *_args, **_kwargs: pytest.fail("MinerU must not be repeated on resume"),
    )

    def fallback(*_: object, **__: object) -> dict[str, object]:
        parsed = job_root / "parsed_native_fallback"
        parsed.mkdir()
        (parsed / "native_fallback_content_list.json").write_text(
            json.dumps([{"type": "text", "text": "Introduction", "page_idx": 0}]),
            encoding="utf-8",
        )
        (parsed / "native_pdf_fallback_run.json").write_text("{}", encoding="utf-8")
        return {"output_files": ["native_fallback_content_list.json"]}

    monkeypatch.setattr(
        "esg_reliable_discovery.workbench_api.parse_with_native_pdf_layout", fallback
    )
    service._parse_job(job["job_id"])
    assert service.get_job(job["job_id"])["state"] == "local_analysis_completed"
