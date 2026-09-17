import json

from esg_reliable_discovery.archive import (
    RunArchive,
    build_model_manifest,
    redact_ollama_request,
)
from esg_reliable_discovery.ollama_client import OllamaResult


def test_archive_records_checksummed_run(tmp_path):
    archive = RunArchive.create(tmp_path, "experiment", "run-001")
    result = OllamaResult(
        request={"model": "x"},
        response={"message": {"content": "{}"}, "eval_count": 3},
        elapsed_seconds=1.2,
        request_sha256="a" * 64,
    )
    archive.record_result(result, model_manifest={"digest": "d"})
    assert (archive.run_dir / "SHA256SUMS").exists()
    metrics = json.loads((archive.run_dir / "metrics.json").read_text())
    assert metrics["eval_count"] == 3


def test_model_manifest_compacts_large_and_machine_specific_fields():
    raw = {
        "details": {"parameter_size": "1B"},
        "model_info": {
            "general.architecture": "test",
            "tokenizer.ggml.tokens": ["a", "b"],
        },
        "modelfile": "FROM /Users/private/models/blob",
        "license": "long license",
        "template": "{{ prompt }}",
        "tensors": [
            {"name": "a", "type": "Q4_K"},
            {"name": "b", "type": "Q4_K"},
        ],
    }
    manifest = build_model_manifest({"model": "test"}, raw, "digest")
    serialized = json.dumps(manifest)
    assert "/Users/private" not in serialized
    assert "tokenizer.ggml.tokens" not in serialized
    assert manifest["model_details"]["tensor_types"] == {"Q4_K": 2}
    assert manifest["model_details_sha256"]


def test_request_redaction_retains_hashes_not_source_content():
    request = {
        "model": "model:tag",
        "messages": [
            {
                "role": "user",
                "content": "copyrighted source page text",
                "images": ["base64-image-payload"],
            }
        ],
    }
    redacted = redact_ollama_request(request)
    serialized = json.dumps(redacted)
    assert "copyrighted source page text" not in serialized
    assert "base64-image-payload" not in serialized
    assert redacted["messages"][0]["content"]["character_count"] == 28
    assert redacted["messages"][0]["images"][0]["encoded_character_count"] == 20
    assert request["messages"][0]["content"] == "copyrighted source page text"


def test_archive_can_store_redacted_request(tmp_path):
    archive = RunArchive.create(tmp_path, "experiment", "redacted-run")
    result = OllamaResult(
        request={"model": "x", "messages": [{"role": "user", "content": "source text"}]},
        response={"message": {"content": "{}"}},
        elapsed_seconds=1.0,
        request_sha256="b" * 64,
    )
    archive.record_result(
        result,
        model_manifest={"digest": "d"},
        redact_request_content=True,
    )
    stored = json.loads((archive.run_dir / "request.json").read_text())
    assert stored["request_content_redacted"] is True
    assert "source text" not in json.dumps(stored)


def test_archive_records_execution_failure_without_model_output(tmp_path):
    archive = RunArchive.create(tmp_path, "experiment", "failed-run")
    archive.record_failure(
        request={"model": "x", "messages": [{"role": "user", "content": "source text"}]},
        error=TimeoutError("timed out"),
        elapsed_seconds=1200.0,
        model_manifest={"digest": "d"},
        stage="model_chat",
        redact_request_content=True,
        additional_json={"validation.json": {"status": "failed"}},
    )
    failure = json.loads((archive.run_dir / "failure.json").read_text())
    response = json.loads((archive.run_dir / "response.json").read_text())
    assert failure["error_type"] == "TimeoutError"
    assert failure["model_output_received"] is False
    assert response == {"model_output_received": False, "status": "execution_failed"}
    assert (archive.run_dir / "SHA256SUMS").exists()
