import json

import pytest

from esg_reliable_discovery.ollama_client import OllamaError
from esg_reliable_discovery.task_runner import (
    _inject_framework_fields,
    _model_content_schema,
    _response_schema,
    _task_conditioned_schema,
    _validate_cards,
    run_task,
)


def test_response_schema_respects_single_and_multiple_card_contracts():
    card_schema = {"type": "object"}
    assert _response_schema(card_schema, 1, 1) is card_schema
    multiple = _response_schema(card_schema, 1, 3)
    assert multiple["type"] == "array"
    assert multiple["minItems"] == 1
    assert multiple["maxItems"] == 3


def test_multiple_card_schema_hoists_definitions_for_root_references():
    card_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"evidence": {"$ref": "#/$defs/evidence"}},
        "$defs": {"evidence": {"type": "string"}},
    }
    multiple = _response_schema(card_schema, 1, 3)
    assert "$defs" not in multiple["items"]
    assert multiple["$defs"] == card_schema["$defs"]
    assert multiple["items"]["properties"]["evidence"]["$ref"] == "#/$defs/evidence"


def test_v1_schema_excludes_only_framework_owned_fields():
    full = {
        "$id": "full",
        "title": "full",
        "type": "object",
        "required": ["finding_id", "task_id", "company_id", "company", "claim", "provenance"],
        "properties": {
            "finding_id": {},
            "task_id": {},
            "company_id": {},
            "company": {},
            "claim": {},
            "provenance": {},
        },
    }
    policy = {
        "framework_injected_fields": [
            "finding_id",
            "task_id",
            "company_id",
            "company",
            "provenance",
        ]
    }
    content = _model_content_schema(full, policy)
    assert content["required"] == ["claim"]
    assert set(content["properties"]) == {"claim"}
    assert "$id" not in content


def test_v1_injection_is_deterministic_and_does_not_mutate_model_content():
    model_content = {"claim": "6.6 MW"}
    assembled = _inject_framework_fields(
        model_content,
        task={"task_id": "P0-TEXT-001"},
        context_manifest={
            "pages": [{"company_id": "US5949181045", "company_name": "Microsoft Corporation"}]
        },
        expected_provenance={"framework_version": "V1", "run_id": "RUN-1"},
        run_id="RUN-1",
    )
    assert model_content == {"claim": "6.6 MW"}
    assert assembled["finding_id"] == "RUN-1-card-001"
    assert assembled["company_id"] == "US5949181045"
    assert assembled["company"] == "Microsoft Corporation"
    assert assembled["provenance"]["annotation_source"] == "model"


def test_v2_contract_requires_task_specific_fields_without_embedding_answers():
    base = {
        "title": "base",
        "required": ["claim", "status", "anomaly_codes", "contrary_evidence"],
        "properties": {
            "claim": {"type": "string"},
            "status": {"enum": ["verified", "insufficient_information"]},
            "metric": {"type": "object"},
            "calculation": {"type": "object"},
            "rule_checks": {"type": "array"},
            "anomaly_codes": {"type": "array"},
            "contrary_evidence": {"type": "array"},
        },
    }
    contracts = {
        "contracts": {
            "deterministic_calculation": {
                "contract_id": "CALC",
                "allowed_finding_types": ["calculated_fact"],
                "required_fields": ["metric", "calculation", "rule_checks"],
                "allowed_statuses": ["verified"],
                "minimum_items": {"rule_checks": 1},
            }
        }
    }
    conditioned = _task_conditioned_schema(
        base,
        {"task_type": "deterministic_calculation", "allowed_claim_levels": ["L2"]},
        contracts,
    )
    assert {"metric", "calculation", "rule_checks"} <= set(conditioned["required"])
    assert conditioned["properties"]["status"]["enum"] == ["verified"]
    assert conditioned["properties"]["finding_type"]["enum"] == ["calculated_fact"]
    assert conditioned["properties"]["claim_level"]["enum"] == ["L2"]
    assert conditioned["properties"]["rule_checks"]["minItems"] == 1
    assert "6.6" not in json.dumps(conditioned)


def test_formal_runner_refuses_unlocked_model_before_reading_sources(tmp_path):
    config = tmp_path / "model.json"
    config.write_text(
        json.dumps(
            {
                "provider": "ollama",
                "deployment": "local",
                "base_url": "http://localhost:11434/api",
                "model": "unlocked:model",
                "expected_digest": None,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OllamaError, match="locked expected_digest"):
        run_task(
            model_config_path=config,
            task_pack_path=tmp_path / "missing-tasks.json",
            task_id="TASK",
            document_manifest_path=tmp_path / "missing-manifest.json",
            raw_root=tmp_path,
            system_prompt_path=tmp_path / "missing-prompt.txt",
            finding_schema_path=tmp_path / "missing-schema.json",
            archive_root=tmp_path / "archive",
            experiment_id="EXP",
            run_id="RUN",
            framework_version="V0",
        )


def test_card_validation_rejects_forged_provenance_and_evidence():
    card = {
        "task_id": "TASK-001",
        "claim_level": "L1",
        "company_id": "COMPANY-001",
        "company": "Example Company",
        "provenance": {"run_id": "forged"},
        "supporting_evidence": [
            {
                "document_id": "WRONG-DOC",
                "document_sha256": "f" * 64,
                "page": 99,
            }
        ],
        "contrary_evidence": [],
    }
    task = {
        "task_id": "TASK-001",
        "allowed_claim_levels": ["L1"],
        "expected_card_count": {"minimum": 1, "maximum": 1},
    }
    context = {
        "pages": [
            {
                "document_id": "DOC-001",
                "document_sha256": "a" * 64,
                "pdf_page": 7,
                "company_id": "COMPANY-001",
                "company_name": "Example Company",
            }
        ],
        "controlled_intervention": None,
    }
    cards, errors = _validate_cards(
        card,
        finding_schema={"type": "object"},
        task=task,
        context_manifest=context,
        expected_provenance={"run_id": "expected"},
    )
    assert len(cards) == 1
    assert "card_0:provenance_mismatch:run_id" in errors
    assert "card_0:invalid_evidence_locator:supporting_evidence" in errors
