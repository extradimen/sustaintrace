from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .hashing import sha256_bytes, sha256_file, sha256_text


class TaskContextError(RuntimeError):
    """Raised when a task source bundle cannot be reproduced safely."""


def _extract_page_text(document_path: Path, page: int) -> str:
    try:
        result = subprocess.run(
            [
                "pdftotext",
                "-f",
                str(page),
                "-l",
                str(page),
                "-layout",
                str(document_path),
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise TaskContextError(f"Unable to extract page {page} from {document_path}") from error
    text = result.stdout.strip()
    if not text:
        raise TaskContextError(f"Page {page} has no extractable text: {document_path}")
    return text


def _render_page_image(document_path: Path, page: int, dpi: int) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as directory:
        prefix = Path(directory) / "page"
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-singlefile",
                    "-r",
                    str(dpi),
                    "-png",
                    str(document_path),
                    str(prefix),
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as error:
            raise TaskContextError(f"Unable to render page {page} from {document_path}") from error
        image = prefix.with_suffix(".png").read_bytes()
    return base64.b64encode(image).decode("ascii"), sha256_bytes(image)


def build_task_context(
    task_pack_path: str | Path,
    task_id: str,
    document_manifest_path: str | Path,
    raw_root: str | Path,
    *,
    interventions_root: str | Path = "data/controlled_interventions",
    include_images: bool = False,
    image_dpi: int = 180,
    include_evidence_handles: bool = False,
) -> dict[str, Any]:
    task_pack = json.loads(Path(task_pack_path).read_text(encoding="utf-8"))
    matches = [task for task in task_pack["tasks"] if task["task_id"] == task_id]
    if len(matches) != 1:
        raise TaskContextError(f"Expected exactly one task {task_id}, found {len(matches)}")
    task = matches[0]
    document_manifest = json.loads(Path(document_manifest_path).read_text(encoding="utf-8"))
    documents = {item["document_id"]: item for item in document_manifest["documents"]}
    text_sections: list[str] = []
    images: list[str] = []
    page_records: list[dict[str, Any]] = []
    evidence_handles: list[dict[str, Any]] = []
    for source in task["source_documents"]:
        document_id = source["document_id"]
        if document_id not in documents:
            raise TaskContextError(f"Document not found in manifest: {document_id}")
        document = documents[document_id]
        if document.get("sha256") != source["sha256"]:
            raise TaskContextError(f"Task and manifest hashes disagree for {document_id}")
        relative_path = Path(document["local_path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise TaskContextError(f"Unsafe document path for {document_id}")
        document_path = Path(raw_root) / relative_path
        if not document_path.is_file() or sha256_file(document_path) != source["sha256"]:
            raise TaskContextError(f"Local source hash mismatch for {document_id}")
        for page in source["pages"]:
            page_text = _extract_page_text(document_path, page)
            source_handle = f"S{len(page_records) + 1:03d}"
            handle_text = f"; HANDLE {source_handle}" if include_evidence_handles else ""
            text_sections.append(
                f"=== OFFICIAL SOURCE: {document_id}; PDF page {page}; "
                f"SHA-256 {source['sha256']}{handle_text} ===\n{page_text}"
            )
            record = {
                "document_id": document_id,
                "document_sha256": source["sha256"],
                "company_id": document["company_id"],
                "company_name": document["company_name"],
                "pdf_page": page,
                "text_sha256": sha256_text(page_text),
                "text_character_count": len(page_text),
            }
            if include_images:
                encoded, image_hash = _render_page_image(document_path, page, image_dpi)
                images.append(encoded)
                record.update({"image_sha256": image_hash, "image_dpi": image_dpi})
            page_records.append(record)
            if include_evidence_handles:
                evidence_handles.append(
                    {
                        "source_handle": source_handle,
                        "source_type": "official_document_page",
                        "document_id": document_id,
                        "document_sha256": source["sha256"],
                        "page": page,
                    }
                )

    intervention_record = None
    if task.get("intervention_id"):
        intervention_path = Path(interventions_root) / f"{task['intervention_id']}.json"
        intervention = json.loads(intervention_path.read_text(encoding="utf-8"))
        if intervention.get("intervention_id") != task["intervention_id"]:
            raise TaskContextError("Controlled intervention identifier mismatch")
        intervention_handle = "I001"
        handle_text = f"; HANDLE {intervention_handle}" if include_evidence_handles else ""
        text_sections.append(
            "=== RESEARCHER-CREATED CONTROLLED INTERVENTION; NOT A COMPANY STATEMENT"
            f"{handle_text} ===\n"
            + json.dumps(intervention, ensure_ascii=False, sort_keys=True)
        )
        intervention_record = {
            "intervention_id": task["intervention_id"],
            "path": str(intervention_path),
            "sha256": sha256_file(intervention_path),
            "researcher_created": True,
        }
        if include_evidence_handles:
            evidence_handles.append(
                {
                    "source_handle": intervention_handle,
                    "source_type": "controlled_intervention",
                    "document_id": task["intervention_id"],
                    "document_sha256": sha256_file(intervention_path),
                    "page": 1,
                }
            )

    context_text = "\n\n".join(text_sections)
    return {
        "task": task,
        "context_text": context_text,
        "images": images,
        "public_manifest": {
            "task_id": task_id,
            "task_pack_path": str(task_pack_path),
            "task_pack_sha256": sha256_file(task_pack_path),
            "document_manifest_path": str(document_manifest_path),
            "document_manifest_sha256": sha256_file(document_manifest_path),
            "pages": page_records,
            "controlled_intervention": intervention_record,
            "evidence_handles": evidence_handles,
            "context_text_sha256": sha256_text(context_text),
            "context_text_character_count": len(context_text),
            "image_count": len(images),
            "source_content_redistributed": False,
        },
    }
