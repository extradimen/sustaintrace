import json
from pathlib import Path

import pytest

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.p1_mineru_blocks import load_mineru_block_handles


def _fixture(tmp_path: Path):
    content = tmp_path / "content_list.json"
    content.write_text(
        json.dumps(
            [
                {"type": "text", "text": "Left column", "bbox": [0, 0, 40, 80], "page_idx": 0},
                {"type": "text", "text": "Right column", "bbox": [60, 0, 100, 80], "page_idx": 0},
            ]
        )
    )
    record = tmp_path / "run.json"
    record.write_text(
        json.dumps(
            {
                "returncode": 0,
                "input_sha256": "a" * 64,
                "start_page_zero_based": 48,
                "parser_probe": {"version": "3.4.0"},
            }
        )
    )
    return content, record


def test_mineru_blocks_preserve_columns_and_absolute_pdf_page(tmp_path: Path):
    content, record = _fixture(tmp_path)
    handles = load_mineru_block_handles(
        content_list_path=content,
        run_record_path=record,
        document_id="DOC",
        document_sha256="a" * 64,
        target_pdf_pages=[49],
    )
    assert [item["verbatim_text"] for item in handles] == ["Left column", "Right column"]
    assert handles[0]["handle"] == "M049-B0001"
    assert handles[0]["page"] == 49
    assert handles[0]["bbox"] == [0, 0, 40, 80]
    assert handles[0]["parser_version"] == "3.4.0"
    assert handles[0]["content_list_sha256"] == sha256_file(content)


def test_mineru_blocks_reject_source_hash_mismatch(tmp_path: Path):
    content, record = _fixture(tmp_path)
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        load_mineru_block_handles(
            content_list_path=content,
            run_record_path=record,
            document_id="DOC",
            document_sha256="b" * 64,
            target_pdf_pages=[49],
        )


def test_mineru_table_body_is_preserved_with_caption(tmp_path: Path):
    content, record = _fixture(tmp_path)
    content.write_text(
        json.dumps(
            [
                {
                    "type": "table",
                    "table_caption": ["GHG emissions"],
                    "table_footnote": ["Million metric tons"],
                    "table_body": "<table><tr><td>Total</td><td>91.64</td></tr></table>",
                    "bbox": [1, 2, 3, 4],
                    "page_idx": 0,
                }
            ]
        )
    )
    handles = load_mineru_block_handles(
        content_list_path=content,
        run_record_path=record,
        document_id="DOC",
        document_sha256="a" * 64,
        target_pdf_pages=[49],
    )
    assert handles[0]["block_type"] == "table"
    assert handles[0]["verbatim_text"].startswith("GHG emissions\nMillion metric tons\n<table>")
    assert "91.64" in handles[0]["verbatim_text"]


def test_mineru_table_can_be_split_into_caption_and_rows(tmp_path: Path):
    content, record = _fixture(tmp_path)
    content.write_text(
        json.dumps(
            [
                {
                    "type": "table",
                    "table_caption": ["GHG emissions"],
                    "table_body": (
                        "<table><tr><th>Metric</th><th>2024</th><th>2023</th></tr>"
                        "<tr><td>Total Scope 3</td><td>91.64</td><td>94.49</td></tr></table>"
                    ),
                    "bbox": [1, 2, 3, 4],
                    "page_idx": 0,
                }
            ]
        )
    )
    handles = load_mineru_block_handles(
        content_list_path=content,
        run_record_path=record,
        document_id="DOC",
        document_sha256="a" * 64,
        target_pdf_pages=[49],
        split_table_rows=True,
    )
    assert [item["handle"] for item in handles] == [
        "M049-T0001-R0000",
        "M049-T0001-R0001",
        "M049-T0001-R0002",
    ]
    assert handles[2]["verbatim_text"] == "Total Scope 3 | 91.64 | 94.49"
