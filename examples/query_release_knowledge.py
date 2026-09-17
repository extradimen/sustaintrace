"""Minimal read-only query against the SustainTrace release knowledge seed."""
from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.release_runtime import initialize_workspace


def main() -> None:
    workspace = Path("example-workspace")
    initialize_workspace(workspace)
    knowledge = workspace / "data/knowledge_bases/v0.1"
    entities = [
        json.loads(line)
        for line in (knowledge / "entity_registry.jsonl").read_text().splitlines()
        if line
    ]
    edges = [
        json.loads(line)
        for line in (knowledge / "relation_edges.jsonl").read_text().splitlines()
        if line
    ]
    selected = entities[0]
    related = [row for row in edges if row["subject_entity_id"] == selected["entity_id"]]
    print(json.dumps({"entity": selected, "trusted_edges": related}, indent=2))


if __name__ == "__main__":
    main()
