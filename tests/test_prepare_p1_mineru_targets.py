from esg_reliable_discovery.p1_mineru_schedule import target_registry


def test_target_registry_deduplicates_document_pages():
    pack = {
        "tasks": [
            {"task_id": "A", "document_id": "DOC", "target_pages": [2, 3]},
            {"task_id": "B", "document_id": "DOC", "target_pages": [3]},
        ]
    }
    acquisition = {
        "documents": [
            {"document_id": "DOC", "sha256": "a" * 64, "local_path": "doc.pdf"}
        ]
    }
    registry = target_registry(pack, acquisition)
    assert len(registry) == 2
    assert registry[1]["pdf_page"] == 3
    assert registry[1]["task_ids"] == ["A", "B"]
