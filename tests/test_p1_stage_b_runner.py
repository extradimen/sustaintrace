import json
from pathlib import Path

from esg_reliable_discovery.archive import refresh_run_checksums
from esg_reliable_discovery.p1_stage_b_runner import build_stage_b_packet


def test_stage_b_packet_uses_only_parent_resolved_evidence(tmp_path: Path):
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "normalized_output.json").write_text(json.dumps({
        "framework_evidence_state": "supported",
        "model_output": {"answer": "BASF reported 0.027."},
        "resolved_evidence": [{
            "source_handle": "M200-T0001-R0008",
            "verbatim_excerpt": "CH4 | 0.027 | 0.022",
        }],
    }))
    (parent / "task_context_manifest.json").write_text(json.dumps({"task_id": "P1-02-2"}))
    refresh_run_checksums(parent)
    ontology_path = tmp_path / "ontology.json"
    ontology_path.write_text(json.dumps({
        "metrics": {"m": {"label": "M", "allowed_units": ["u"],
                            "allowed_scopes": ["s"]}},
        "units": {"u": {"label": "U"}}, "scopes": {"s": {"label": "S"}},
    }))
    source_registry = tmp_path / "sources.json"
    source_registry.write_text(json.dumps({"candidates": [{
        "document_id": "DOC", "company": "BASF SE", "eligibility_status": "eligible",
        "sha256": "locked-sha",
    }]}))
    handles = [
        {"handle": "M200-T0001-R0008", "source_id": "DOC", "page": 200,
         "verbatim_text": "CH4 | 0.027 | 0.022", "table_header_context": "2024 | 2023",
         "document_sha256": "locked-sha"},
        {"handle": "M200-T0001-R0009", "source_id": "DOC", "page": 200,
         "verbatim_text": "Other secret row", "document_sha256": "locked-sha"},
    ]
    packet, manifest, evidence, _, subject = build_stage_b_packet(
        parent_run_directory=parent, available_handles=handles,
        ontology_path=ontology_path, source_registry_path=source_registry,
    )
    assert [item["handle"] for item in evidence] == ["M200-T0001-R0008"]
    assert "Other secret row" not in json.dumps(packet)
    assert manifest["full_report_visible_to_stage_b"] is False
    assert subject == {"entity_id": "ENTITY::DOC", "entity_label": "BASF SE"}
