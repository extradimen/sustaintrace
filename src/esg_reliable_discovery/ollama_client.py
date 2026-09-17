from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import ModelConfig
from .hashing import sha256_json


class OllamaError(RuntimeError):
    """Raised when an Ollama endpoint returns an invalid or failed response."""


@dataclass(frozen=True)
class OllamaResult:
    request: dict[str, Any]
    response: dict[str, Any]
    elapsed_seconds: float
    request_sha256: str


class OllamaClient:
    def __init__(self, config: ModelConfig):
        if config.provider != "ollama":
            raise ValueError(f"Unsupported provider: {config.provider}")
        self.config = config

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key_env:
            key = os.environ.get(self.config.api_key_env)
            if not key:
                raise OllamaError(
                    f"Missing API key environment variable: {self.config.api_key_env}"
                )
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _request(
        self, method: str, endpoint: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise OllamaError(f"Ollama HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise OllamaError(f"Ollama connection failed: {error.reason}") from error
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise OllamaError("Ollama returned non-JSON output") from error

    def list_models(self) -> dict[str, Any]:
        return self._request("GET", "tags")

    def show_model(self, model: str | None = None, verbose: bool = False) -> dict[str, Any]:
        return self._request(
            "POST", "show", {"model": model or self.config.model, "verbose": verbose}
        )

    def verify_digest(self) -> str | None:
        models = self.list_models().get("models", [])
        selected = next(
            (
                item
                for item in models
                if item.get("name") == self.config.model or item.get("model") == self.config.model
            ),
            None,
        )
        if selected is None:
            return None
        digest = selected.get("digest")
        if self.config.expected_digest and digest != self.config.expected_digest:
            raise OllamaError(
                f"Digest mismatch for {self.config.model}: "
                f"expected {self.config.expected_digest}, got {digest}"
            )
        return digest

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        think: bool | str | None = None,
    ) -> OllamaResult:
        payload = self.build_chat_payload(messages, schema=schema, think=think)
        started = time.perf_counter()
        response = self._request("POST", "chat", payload)
        elapsed = time.perf_counter() - started
        return OllamaResult(
            request=payload,
            response=response,
            elapsed_seconds=elapsed,
            request_sha256=sha256_json(payload),
        )

    def build_chat_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        schema: dict[str, Any] | None = None,
        think: bool | str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": self.config.options,
        }
        if schema is not None:
            payload["format"] = schema
        if think is not None:
            payload["think"] = think
        return payload

    def embed(self, inputs: str | list[str]) -> OllamaResult:
        payload = {"model": self.config.model, "input": inputs}
        started = time.perf_counter()
        response = self._request("POST", "embed", payload)
        elapsed = time.perf_counter() - started
        return OllamaResult(
            request=payload,
            response=response,
            elapsed_seconds=elapsed,
            request_sha256=sha256_json(payload),
        )
