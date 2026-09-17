from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def semantic_text_from_content_list(path: str | Path) -> str:
    """Project MinerU text blocks without changing their order or wording."""
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("mineru_content_list_must_be_a_list")
    lines = []
    for block in payload:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def select_mineru_text_source(directory: str | Path) -> Path:
    """Prefer non-empty Markdown, then fall back to semantic content-list text."""
    root = Path(directory)
    markdown = list(root.rglob("*.md"))
    if len(markdown) != 1:
        raise RuntimeError(f"expected_one_markdown:{root}:{len(markdown)}")
    if markdown[0].read_text(encoding="utf-8", errors="replace").strip():
        return markdown[0]
    content_lists = [
        path
        for path in root.rglob("*_content_list.json")
        if not path.name.endswith("_content_list_v2.json")
    ]
    if len(content_lists) != 1:
        raise RuntimeError(f"expected_one_content_list:{root}:{len(content_lists)}")
    if not semantic_text_from_content_list(content_lists[0]).strip():
        raise RuntimeError(f"empty_mineru_semantic_text:{root}")
    return content_lists[0]


def read_mineru_text_source(path: str | Path) -> str:
    source = Path(path)
    if source.name.endswith("_content_list.json"):
        return semantic_text_from_content_list(source)
    return source.read_text(encoding="utf-8", errors="replace")
