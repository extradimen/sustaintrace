#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file
from esg_reliable_discovery.postvalidation_attachment import (
    build_diagnostic_result_envelope,
)

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "artifacts/v39_volvo_repeated_value_table_unseen_RESUME01_v0.1/result.lock.json"
EXPOSED_FAILURE = ROOT / "artifacts/v40_normalized_envelope_unseen_v0.1/result.lock.json"
OUTPUT = ROOT / "artifacts/v41_raw_result_envelope_development_v0.1/development_summary.lock.json"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("refusing_to_overwrite_v41_development")
    payload = json.loads(PARENT.read_text())
    envelope = build_diagnostic_result_envelope(
        payload=payload,
        diagnostic_path=str(PARENT.relative_to(ROOT)),
        parent_fact_id="fact-8b592f76837c3f3219cad2d7",
        parent_gap_id="v39-unseen-derived-gap",
        case_id="V39-TABLE-UNSEEN-VOLVO-001",
        root=ROOT,
    )
    result = {
        "schema_version": "0.1",
        "development_id": "V4.1-RAW-RESULT-ENVELOPE-DEVELOPMENT-V01",
        "status": "development_regression_passed"
        if envelope["normalized_status"] == "passed"
        else "development_regression_failed",
        "development_source": {
            "path": str(EXPOSED_FAILURE.relative_to(ROOT)),
            "sha256": sha256_file(EXPOSED_FAILURE),
        },
        "parent_diagnostic": {
            "path": str(PARENT.relative_to(ROOT)),
            "sha256": sha256_file(PARENT),
            "modified": False,
        },
        "observed": {
            "normalized_status": envelope["normalized_status"],
            "blocking_reasons": envelope["blocking_reasons"],
            "component_result_path": envelope["identity_binding"][
                "component_result_path"
            ],
            "raw_payload_preserved": envelope["raw_payload"] == payload,
        },
        "attachment_generated": False,
        "reason": "the exposed parent gap is intentionally unregistered",
        "historical_result_modified": False,
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "gap_mutation_performed": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["observed"]))


if __name__ == "__main__":
    main()
