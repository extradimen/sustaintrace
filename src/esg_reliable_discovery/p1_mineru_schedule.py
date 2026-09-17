from __future__ import annotations

from collections import defaultdict


def target_registry(task_pack: dict, acquisition: dict) -> list[dict]:
    documents = {item["document_id"]: item for item in acquisition["documents"]}
    tasks_by_target: dict[tuple[str, int], list[str]] = defaultdict(list)
    for task in task_pack["tasks"]:
        for page in task["target_pages"]:
            tasks_by_target[(task["document_id"], page)].append(task["task_id"])
    registry = []
    for (document_id, page), task_ids in sorted(tasks_by_target.items()):
        document = documents[document_id]
        registry.append(
            {
                "target_id": f"{document_id}-p{page:04d}",
                "document_id": document_id,
                "document_sha256": document["sha256"],
                "local_path": document["local_path"],
                "pdf_page": page,
                "task_ids": sorted(task_ids),
            }
        )
    return registry
