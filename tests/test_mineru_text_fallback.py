from __future__ import annotations

import json
from pathlib import Path

import pytest

from esg_reliable_discovery.mineru_text_fallback import (
    read_mineru_text_source,
    select_mineru_text_source,
    semantic_text_from_content_list,
)


def write_output(root: Path, markdown: str, blocks: list[dict]) -> tuple[Path, Path]:
    output = root / "document" / "auto"
    output.mkdir(parents=True)
    markdown_path = output / "document.md"
    content_path = output / "document_content_list.json"
    markdown_path.write_text(markdown, encoding="utf-8")
    content_path.write_text(json.dumps(blocks), encoding="utf-8")
    return markdown_path, content_path


def test_nonempty_markdown_remains_primary(tmp_path: Path) -> None:
    markdown, _ = write_output(tmp_path, "issuer text\n", [{"text": "fallback"}])
    assert select_mineru_text_source(tmp_path) == markdown
    assert read_mineru_text_source(markdown) == "issuer text\n"


def test_empty_markdown_uses_ordered_content_list_text(tmp_path: Path) -> None:
    _, content = write_output(
        tmp_path,
        "",
        [
            {"type": "page_number", "text": "4"},
            {"type": "header", "text": " Assurance conclusion "},
            {"type": "footer", "text": ""},
        ],
    )
    assert select_mineru_text_source(tmp_path) == content
    assert semantic_text_from_content_list(content) == "4\nAssurance conclusion"
    assert read_mineru_text_source(content) == "4\nAssurance conclusion"


def test_empty_markdown_and_empty_content_are_rejected(tmp_path: Path) -> None:
    write_output(tmp_path, "", [{"type": "footer", "text": ""}])
    with pytest.raises(RuntimeError, match="empty_mineru_semantic_text"):
        select_mineru_text_source(tmp_path)
