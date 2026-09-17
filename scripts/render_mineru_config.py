#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PLACEHOLDER = "__MINERU_MODELS_ROOT__"


def render(template: Path, models_root: Path) -> dict:
    payload = json.loads(template.read_text(encoding="utf-8"))
    configured = payload["models-dir"]["pipeline"]
    if configured != PLACEHOLDER:
        raise ValueError(f"Expected template placeholder {PLACEHOLDER}, got {configured!r}")
    resolved = models_root.resolve()
    if not (resolved / "models").is_dir():
        raise ValueError(f"Snapshot root does not contain models/: {resolved}")
    payload["models-dir"]["pipeline"] = str(resolved)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = render(args.template, args.models_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote local MinerU config: {args.output}")


if __name__ == "__main__":
    main()
