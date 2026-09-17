import json
from types import SimpleNamespace
from unittest.mock import patch

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.task_context import build_task_context


def test_task_context_verifies_source_and_publishes_hashes_not_text(tmp_path):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    document = raw_root / "report.pdf"
    document.write_bytes(b"%PDF-fake-test")
    digest = sha256_file(document)
    task_pack = {
        "tasks": [
            {
                "task_id": "TASK-001",
                "source_documents": [{"document_id": "DOC-001", "sha256": digest, "pages": [7]}],
                "intervention_id": None,
            }
        ]
    }
    manifest = {
        "documents": [
            {
                "document_id": "DOC-001",
                "sha256": digest,
                "local_path": "report.pdf",
                "company_id": "COMPANY-001",
                "company_name": "Example Company",
            }
        ]
    }
    task_path = tmp_path / "tasks.json"
    manifest_path = tmp_path / "manifest.json"
    task_path.write_text(json.dumps(task_pack), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with patch(
        "esg_reliable_discovery.task_context.subprocess.run",
        return_value=SimpleNamespace(stdout="A material climate-transition statement."),
    ):
        result = build_task_context(task_path, "TASK-001", manifest_path, raw_root)

    assert "A material climate-transition statement." in result["context_text"]
    public = result["public_manifest"]
    assert "A material climate-transition statement." not in json.dumps(public)
    assert public["pages"][0]["pdf_page"] == 7
    assert len(public["pages"][0]["text_sha256"]) == 64
    assert public["source_content_redistributed"] is False


def test_controlled_intervention_is_unambiguously_marked(tmp_path):
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    document = raw_root / "report.pdf"
    document.write_bytes(b"%PDF-fake-test")
    digest = sha256_file(document)
    task_path = tmp_path / "tasks.json"
    manifest_path = tmp_path / "manifest.json"
    interventions = tmp_path / "interventions"
    interventions.mkdir()
    task_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "task_id": "TASK-001",
                        "source_documents": [
                            {"document_id": "DOC-001", "sha256": digest, "pages": [1]}
                        ],
                        "intervention_id": "CI-001",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "DOC-001",
                        "sha256": digest,
                        "local_path": "report.pdf",
                        "company_id": "COMPANY-001",
                        "company_name": "Example Company",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (interventions / "CI-001.json").write_text(
        json.dumps({"intervention_id": "CI-001", "statement": "synthetic"}),
        encoding="utf-8",
    )
    with patch(
        "esg_reliable_discovery.task_context.subprocess.run",
        return_value=SimpleNamespace(stdout="Official source content."),
    ):
        result = build_task_context(
            task_path,
            "TASK-001",
            manifest_path,
            raw_root,
            interventions_root=interventions,
        )
    assert "NOT A COMPANY STATEMENT" in result["context_text"]
    assert result["public_manifest"]["controlled_intervention"]["researcher_created"] is True
