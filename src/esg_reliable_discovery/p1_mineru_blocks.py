from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .hashing import sha256_file


class _TableRowParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None


def _table_rows(table_body: str) -> list[str]:
    parser = _TableRowParser()
    parser.feed(table_body)
    return [" | ".join(cells) for cells in parser.rows]


def _block_text(block: dict[str, Any]) -> str | None:
    text = block.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    table_body = block.get("table_body")
    if isinstance(table_body, str) and table_body.strip():
        parts = []
        for key in ("table_caption", "table_footnote"):
            value = block.get(key, [])
            if isinstance(value, list):
                parts.extend(str(item).strip() for item in value if str(item).strip())
        parts.append(table_body.strip())
        return "\n".join(parts)
    return None


def load_mineru_block_handles(
    *, content_list_path: str | Path, run_record_path: str | Path,
    document_id: str, document_sha256: str, target_pdf_pages: list[int],
    split_table_rows: bool = False,
) -> list[dict[str, Any]]:
    content_path = Path(content_list_path)
    record_path = Path(run_record_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("returncode") != 0:
        raise ValueError("mineru_run_not_successful")
    if record.get("input_sha256") != document_sha256:
        raise ValueError("mineru_source_hash_mismatch")
    start_zero = record.get("start_page_zero_based")
    if not isinstance(start_zero, int):
        raise ValueError("mineru_start_page_missing")
    blocks = json.loads(content_path.read_text(encoding="utf-8"))
    handles = []
    for block_index, block in enumerate(blocks, start=1):
        relative_page = block.get("page_idx")
        if not isinstance(relative_page, int):
            continue
        pdf_page = start_zero + relative_page + 1
        if pdf_page not in target_pdf_pages:
            continue
        if split_table_rows and block.get("type") == "table":
            table_body = block.get("table_body")
            if not isinstance(table_body, str) or not table_body.strip():
                continue
            caption = " ".join(
                str(item).strip() for item in block.get("table_caption", []) if str(item).strip()
            )
            parsed_rows = _table_rows(table_body)
            header_context = parsed_rows[0] if parsed_rows else None
            rows = ([caption] if caption else []) + parsed_rows
            for row_index, row in enumerate(rows):
                handles.append(
                    {
                        "handle": f"M{pdf_page:03d}-T{block_index:04d}-R{row_index:04d}",
                        "source_id": document_id,
                        "document_sha256": document_sha256,
                        "page": pdf_page,
                        "block_type": (
                            "table_caption"
                            if row_index == 0 and caption
                            else "table_row"
                        ),
                        "bbox": block.get("bbox"),
                        "verbatim_text": row,
                        "normalized_text": " ".join(row.split()),
                        "table_header_context": header_context,
                        "parser": "MinerU",
                        "parser_version": record["parser_probe"].get("version"),
                        "parser_run_sha256": sha256_file(record_path),
                        "content_list_sha256": sha256_file(content_path),
                    }
                )
            continue
        text = _block_text(block)
        if text is None:
            continue
        handles.append(
            {
                "handle": f"M{pdf_page:03d}-B{block_index:04d}",
                "source_id": document_id,
                "document_sha256": document_sha256,
                "page": pdf_page,
                "block_type": block.get("type", "unknown"),
                "bbox": block.get("bbox"),
                "verbatim_text": text,
                "normalized_text": " ".join(text.split()),
                "parser": "MinerU",
                "parser_version": record["parser_probe"].get("version"),
                "parser_run_sha256": sha256_file(record_path),
                "content_list_sha256": sha256_file(content_path),
            }
        )
    if not handles:
        raise ValueError("mineru_no_text_blocks_for_target_pages")
    return handles
