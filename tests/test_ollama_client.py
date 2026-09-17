import json
from unittest.mock import patch

import pytest

from esg_reliable_discovery.config import ModelConfig
from esg_reliable_discovery.ollama_client import OllamaClient, OllamaError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def config(expected_digest=None):
    return ModelConfig(
        provider="ollama",
        deployment="local",
        base_url="http://localhost:11434/api",
        model="model:tag",
        expected_digest=expected_digest,
        options={"temperature": 0},
    )


@patch("urllib.request.urlopen")
def test_chat_builds_non_streaming_request(urlopen):
    urlopen.return_value = FakeResponse({"message": {"content": "ok"}, "eval_count": 1})
    result = OllamaClient(config()).chat([{"role": "user", "content": "hello"}])
    assert result.response["message"]["content"] == "ok"
    assert result.request["stream"] is False
    assert len(result.request_sha256) == 64


@patch("urllib.request.urlopen")
def test_digest_mismatch_fails(urlopen):
    urlopen.return_value = FakeResponse({"models": [{"name": "model:tag", "digest": "actual"}]})
    with pytest.raises(OllamaError, match="Digest mismatch"):
        OllamaClient(config(expected_digest="expected")).verify_digest()


def test_missing_cloud_key_fails(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    cloud = ModelConfig(
        provider="ollama",
        deployment="cloud",
        base_url="https://ollama.com/api",
        model="cloud-model",
        api_key_env="OLLAMA_API_KEY",
    )
    with pytest.raises(OllamaError, match="Missing API key"):
        OllamaClient(cloud).list_models()
