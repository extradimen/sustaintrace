from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    deployment: str
    base_url: str
    model: str
    expected_digest: str | None = None
    api_key_env: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 600
    notes: str = ""

    @classmethod
    def from_path(cls, path: str | Path) -> ModelConfig:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**payload)

    def public_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "deployment": self.deployment,
            "base_url": self.base_url,
            "model": self.model,
            "expected_digest": self.expected_digest,
            "api_key_env": self.api_key_env,
            "options": self.options,
            "timeout_seconds": self.timeout_seconds,
            "notes": self.notes,
        }
