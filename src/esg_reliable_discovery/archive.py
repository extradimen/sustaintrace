from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .hashing import sha256_file, sha256_json, sha256_text
from .ollama_client import OllamaResult


@dataclass
class RunArchive:
    root: Path
    experiment_id: str
    run_id: str

    @classmethod
    def create(cls, root: str | Path, experiment_id: str, run_id: str) -> RunArchive:
        archive = cls(Path(root), experiment_id, run_id)
        archive.run_dir.mkdir(parents=True, exist_ok=False)
        return archive

    @property
    def run_dir(self) -> Path:
        return self.root / self.experiment_id / "runs" / self.run_id

    def write_json(self, name: str, payload: Any) -> Path:
        path = self.run_dir / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def record_result(
        self,
        result: OllamaResult,
        *,
        model_manifest: dict[str, Any],
        normalized_output: Any | None = None,
        redact_request_content: bool = False,
        additional_json: dict[str, Any] | None = None,
    ) -> None:
        request = (
            redact_ollama_request(result.request) if redact_request_content else result.request
        )
        self.write_json("request.json", request)
        self.write_json("response.json", result.response)
        self.write_json("model_manifest.json", model_manifest)
        if normalized_output is not None:
            self.write_json("normalized_output.json", normalized_output)
        for name, payload in (additional_json or {}).items():
            if not name.endswith(".json") or Path(name).name != name:
                raise ValueError("Additional archive names must be plain .json filenames")
            self.write_json(name, payload)
        metrics = {
            "elapsed_seconds": result.elapsed_seconds,
            "request_sha256": result.request_sha256,
            "prompt_eval_count": result.response.get("prompt_eval_count"),
            "eval_count": result.response.get("eval_count"),
            "total_duration": result.response.get("total_duration"),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.write_json("metrics.json", metrics)
        refresh_run_checksums(self.run_dir)

    def record_failure(
        self,
        *,
        request: dict[str, Any],
        error: BaseException,
        elapsed_seconds: float,
        model_manifest: dict[str, Any],
        stage: str,
        redact_request_content: bool = False,
        additional_json: dict[str, Any] | None = None,
    ) -> None:
        archived_request = redact_ollama_request(request) if redact_request_content else request
        self.write_json("request.json", archived_request)
        self.write_json(
            "response.json",
            {
                "status": "execution_failed",
                "model_output_received": False,
            },
        )
        self.write_json("model_manifest.json", model_manifest)
        self.write_json(
            "failure.json",
            {
                "stage": stage,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "model_output_received": False,
                "posthoc_model_output_repair_applied": False,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        for name, payload in (additional_json or {}).items():
            if not name.endswith(".json") or Path(name).name != name:
                raise ValueError("Additional archive names must be plain .json filenames")
            self.write_json(name, payload)
        self.write_json(
            "metrics.json",
            {
                "elapsed_seconds": elapsed_seconds,
                "request_sha256": sha256_json(request),
                "prompt_eval_count": None,
                "eval_count": None,
                "total_duration": None,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        refresh_run_checksums(self.run_dir)


def verify_run_checksums(run_directory: str | Path) -> None:
    run_directory = Path(run_directory)
    checksum_path = run_directory / "SHA256SUMS"
    if not checksum_path.is_file():
        raise FileNotFoundError(f"Missing archive checksum file: {checksum_path}")
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        target = run_directory / name.strip()
        actual = sha256_file(target)
        if actual != expected:
            raise ValueError(f"Archive checksum mismatch: {target}")


def refresh_run_checksums(run_directory: str | Path) -> Path:
    run_directory = Path(run_directory)
    checksums = [
        f"{sha256_file(path)}  {path.name}" for path in sorted(run_directory.glob("*.json"))
    ]
    checksum_path = run_directory / "SHA256SUMS"
    checksum_path.write_text("\n".join(checksums) + "\n", encoding="utf-8")
    return checksum_path


def redact_ollama_request(request: dict[str, Any]) -> dict[str, Any]:
    """Replace copyrighted prompt bodies and image payloads with reproducibility metadata."""
    redacted = json.loads(json.dumps(request))
    for message in redacted.get("messages", []):
        content = message.get("content")
        if isinstance(content, str):
            message["content"] = {
                "redacted": True,
                "sha256": sha256_text(content),
                "character_count": len(content),
            }
        images = message.get("images")
        if isinstance(images, list):
            message["images"] = [
                {
                    "redacted": True,
                    "sha256": sha256_text(str(image)),
                    "encoded_character_count": len(str(image)),
                }
                for image in images
            ]
    redacted["request_content_redacted"] = True
    return redacted


def build_model_manifest(
    config: dict[str, Any], model_details: dict[str, Any], digest: str | None
) -> dict[str, Any]:
    model_info = {
        key: value
        for key, value in model_details.get("model_info", {}).items()
        if value is not None
        and not key.startswith("tokenizer.ggml.tokens")
        and not key.startswith("tokenizer.ggml.merges")
    }
    tensors = model_details.get("tensors", [])
    tensor_types: dict[str, int] = {}
    for tensor in tensors:
        tensor_type = str(tensor.get("type", "unknown"))
        tensor_types[tensor_type] = tensor_types.get(tensor_type, 0) + 1
    compact_details = {
        "capabilities": model_details.get("capabilities", []),
        "details": model_details.get("details", {}),
        "model_info": model_info,
        "modified_at": model_details.get("modified_at"),
        "parameters": model_details.get("parameters"),
        "tensor_count": len(tensors),
        "tensor_types": tensor_types,
        "large_fields_sha256": {
            key: sha256_json(model_details.get(key))
            for key in ("license", "modelfile", "template", "tensors")
            if key in model_details
        },
    }
    return {
        "config": config,
        "config_sha256": sha256_json(config),
        "resolved_digest": digest,
        "model_details": compact_details,
        "model_details_sha256": sha256_json(model_details),
        "captured_at": datetime.now(UTC).isoformat(),
    }
