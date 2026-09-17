from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.v17_causal_epistemics import (
    classify_attribution_and_causal_identification,
)
from esg_reliable_discovery.v17_multifragment import (
    project_grounded_string_fragments,
)
from esg_reliable_discovery.v17_threshold import (
    compare_recalculated_to_issuer_threshold,
)

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "research_archive/P7-V16-UNSEEN-LOCKBOX-V01/runs"
OUT = ROOT / "data/results/v17_p7_exposed_failure_development_v0.1.lock.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    calc_path = RUNS / "P7-CALC-001-QWEN397B-v16-stage-a-r1/normalized_output.json"
    intensity_path = RUNS / "P7-INTENSITY-001-QWEN397B-v16-stage-a-r1/normalized_output.json"
    assure_path = RUNS / "P7-ASSURE-001-QWEN397B-v16-stage-a-r1/normalized_output.json"
    calc = load(calc_path)
    intensity = load(intensity_path)
    assure = load(assure_path)
    threshold = compare_recalculated_to_issuer_threshold(
        deterministic_calculation=calc["deterministic_calculation"],
        issuer_claim={"operator":"more_than","threshold_percent":50},
    )
    intensity_evidence = [
        {"handle":item["source_handle"],"verbatim_text":item["verbatim_excerpt"]}
        for item in intensity["resolved_evidence"]
    ]
    attribution = classify_attribution_and_causal_identification(
        issuer_attribution="contributing to a group carbon intensity in 2025 of 1.79",
        evidence=intensity_evidence,
    )
    assure_evidence = [
        {"handle":item["source_handle"],"verbatim_text":item["verbatim_excerpt"]}
        for item in assure["resolved_evidence"]
    ]
    assurance_subject = project_grounded_string_fragments(
        fragments=[
            {
                "evidence_handle":"M089-B0013",
                "verbatim_value":(
                    "selected Environmental and Social (E&S) "
                    "Key Performances Indicators"
                ),
            },
            {"evidence_handle":"M089-B0014","verbatim_value":"EU Taxonomy report"},
        ],
        evidence=assure_evidence,
    )
    result = {
        "schema_version":"1.0",
        "experiment_id":"V17-P7-EXPOSED-FAILURE-DEV-V01",
        "status":"completed",
        "created_at":datetime.now(UTC).isoformat(),
        "not_a_lockbox_result":True,
        "model_requests_sent":0,
        "candidate_outputs_reused_without_modification":True,
        "p7_archive_modified":False,
        "results":{
            "P7-CALC-001-DEV":threshold,
            "P7-INTENSITY-001-DEV":attribution,
            "P7-ASSURE-001-DEV":assurance_subject,
        },
        "source_artifacts":{
            str(path.relative_to(ROOT)):sha256_file(path)
            for path in (calc_path,intensity_path,assure_path)
        },
        "interpretation":(
            "All three exposed P7 limitations now have deterministic "
            "representations; unseen generalization remains untested."
        ),
    }
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
