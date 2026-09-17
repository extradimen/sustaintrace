#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from esg_reliable_discovery.archive import build_model_manifest
from esg_reliable_discovery.config import ModelConfig
from esg_reliable_discovery.ollama_client import OllamaClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include the full model vocabulary; unsuitable for normal Git manifests.",
    )
    args = parser.parse_args()
    config = ModelConfig.from_path(args.config)
    client = OllamaClient(config)
    manifest = build_model_manifest(
        config.public_dict(),
        client.show_model(verbose=args.verbose),
        client.verify_digest(),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
