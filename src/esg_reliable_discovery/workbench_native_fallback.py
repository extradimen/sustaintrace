from __future__ import annotations

import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .layout_fallback import layout_line_records


class NativePDFFallbackError(RuntimeError):
    """Raised when the auditable native-PDF fallback cannot recover text."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def parse_with_native_pdf_layout(
    source_pdf: str | Path,
    output_dir: str | Path,
    *,
    executable: str = "pdftotext",
) -> dict[str, Any]:
    """Create MinerU-compatible page blocks with Poppler geometry and an audit record."""
    source = Path(source_pdf).resolve()
    output = Path(output_dir).resolve()
    audit_path = output / "native_pdf_fallback_run.json"
    content_path = output / "native_fallback_content_list.json"
    if audit_path.exists() and content_path.exists():
        record = json.loads(audit_path.read_text(encoding="utf-8"))
        if (
            record.get("state") == "completed"
            and record.get("source_sha256") == sha256_file(source)
        ):
            return record
        raise NativePDFFallbackError("Existing native fallback output is not safely reusable")
    if output.exists() and any(output.iterdir()):
        raise NativePDFFallbackError("Native fallback output directory is not empty")
    output.mkdir(parents=True, exist_ok=True)

    started_at = _now()
    command = [executable, "-bbox-layout", "-enc", "UTF-8", str(source), "OUTPUT_XHTML"]
    try:
        with tempfile.TemporaryDirectory(prefix="esg-rd-workbench-native-") as directory:
            xhtml_path = Path(directory) / "layout.xhtml"
            result = subprocess.run(
                [executable, "-bbox-layout", "-enc", "UTF-8", str(source), str(xhtml_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode != 0:
                raise NativePDFFallbackError(
                    f"pdftotext returned {result.returncode}: {result.stderr.strip()}"
                )
            root = ET.fromstring(xhtml_path.read_text(encoding="utf-8"))
    except (OSError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        raise NativePDFFallbackError(str(exc)) from exc

    pages = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "page"]
    blocks: list[dict[str, Any]] = []
    line_count = 0
    for page_index, page in enumerate(pages):
        lines = layout_line_records(ET.tostring(page, encoding="unicode"))
        line_count += len(lines)
        text = "\n".join(line["text"] for line in lines).strip()
        if not text:
            continue
        width = float(page.attrib.get("width", 0.0))
        height = float(page.attrib.get("height", 0.0))
        blocks.append(
            {
                "type": "text",
                "text": text,
                "page_idx": page_index,
                "bbox": [0.0, 0.0, width, height],
                "parser": "poppler_pdftotext_bbox_layout",
                "native_layout_lines": lines,
            }
        )
    if not blocks:
        raise NativePDFFallbackError("Native PDF fallback recovered no visible text")

    _atomic_json(content_path, blocks)
    record = {
        "schema_version": "1.0",
        "record_kind": "workbench_native_pdf_fallback_run",
        "state": "completed",
        "started_at": started_at,
        "completed_at": _now(),
        "source_path": str(source),
        "source_sha256": sha256_file(source),
        "parser": "poppler_pdftotext_bbox_layout",
        "command": command,
        "page_blocks": len(blocks),
        "visible_lines": line_count,
        "output_files": [content_path.name],
        "coordinate_system": "PDF points from pdftotext bbox-layout",
        "selection_rule": "all_visible_lines_no_hidden_reference_selection",
        "cloud_transfer_performed": False,
    }
    _atomic_json(audit_path, record)
    return record
