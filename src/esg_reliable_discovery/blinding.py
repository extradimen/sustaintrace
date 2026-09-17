from __future__ import annotations

import json
import random
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .hashing import sha256_file, sha256_json


def _load_cards(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    raise ValueError(f"Candidate file must contain one card or a list of cards: {path}")


def build_blind_pool(
    candidate_paths: list[str | Path],
    *,
    pool_id: str,
    task_id: str,
    seed: int,
    output_directory: str | Path,
    identity_map_path: str | Path,
    finding_schema: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    output_directory = Path(output_directory)
    identity_map_path = Path(identity_map_path)
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"Blind pool output directory is not empty: {output_directory}")
    if identity_map_path.exists():
        raise FileExistsError(f"Identity map already exists: {identity_map_path}")

    validator = Draft202012Validator(finding_schema)
    source_items: list[dict[str, Any]] = []
    for path_value in sorted(Path(path) for path in candidate_paths):
        for card_index, card in enumerate(_load_cards(path_value)):
            errors = sorted(validator.iter_errors(card), key=lambda error: list(error.path))
            if errors:
                raise ValueError(
                    f"Invalid finding card in {path_value} index {card_index}: {errors[0].message}"
                )
            if card["task_id"] != task_id:
                raise ValueError(
                    f"Candidate task mismatch in {path_value}: {card['task_id']} != {task_id}"
                )
            source_items.append(
                {
                    "path": path_value,
                    "card_index": card_index,
                    "card": card,
                    "source_card_sha256": sha256_json(card),
                }
            )
    if not source_items:
        raise ValueError("At least one candidate finding card is required")

    random.Random(seed).shuffle(source_items)
    timestamp = created_at or datetime.now(UTC).isoformat()
    output_directory.mkdir(parents=True, exist_ok=True)
    identity_map_path.parent.mkdir(parents=True, exist_ok=True)
    public_candidates = []
    private_identities = []
    for position, item in enumerate(source_items, start=1):
        blind_id = f"{pool_id}-C{position:04d}"
        blinded = deepcopy(item["card"])
        original_finding_id = blinded["finding_id"]
        original_provenance = deepcopy(blinded["provenance"])
        blinded["finding_id"] = blind_id
        blinded["provenance"]["model_snapshot"] = None
        blinded["provenance"]["run_id"] = "BLINDED"
        blinded["provenance"]["created_at"] = timestamp
        output_path = output_directory / f"{blind_id}.json"
        output_path.write_text(
            json.dumps(blinded, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        public_candidates.append(
            {
                "blind_id": blind_id,
                "order": position,
                "path": str(output_path),
                "candidate_sha256": sha256_file(output_path),
            }
        )
        private_identities.append(
            {
                "blind_id": blind_id,
                "source_path": str(item["path"]),
                "source_card_index": item["card_index"],
                "source_card_sha256": item["source_card_sha256"],
                "source_finding_id": original_finding_id,
                "model_snapshot": original_provenance.get("model_snapshot"),
                "run_id": original_provenance.get("run_id"),
            }
        )

    public_manifest = {
        "schema_version": "1.0",
        "pool_id": pool_id,
        "task_id": task_id,
        "randomization_seed": seed,
        "created_at": timestamp,
        "candidate_count": len(public_candidates),
        "pre_review_deduplication": False,
        "model_identity_in_public_pool": False,
        "candidates": public_candidates,
    }
    manifest_path = output_directory / "pool_manifest.json"
    manifest_path.write_text(
        json.dumps(public_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    identity_map = {
        "schema_version": "1.0",
        "pool_id": pool_id,
        "task_id": task_id,
        "public_manifest_sha256": sha256_file(manifest_path),
        "identities": private_identities,
    }
    identity_map_path.write_text(
        json.dumps(identity_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "public_manifest_path": str(manifest_path),
        "public_manifest_sha256": sha256_file(manifest_path),
        "identity_map_path": str(identity_map_path),
        "candidate_count": len(public_candidates),
    }


def build_blind_pool_paths(
    candidate_paths: list[str | Path],
    *,
    pool_id: str,
    task_id: str,
    seed: int,
    output_directory: str | Path,
    identity_map_path: str | Path,
    schema_path: str | Path,
) -> dict[str, Any]:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    return build_blind_pool(
        candidate_paths,
        pool_id=pool_id,
        task_id=task_id,
        seed=seed,
        output_directory=output_directory,
        identity_map_path=identity_map_path,
        finding_schema=schema,
    )
