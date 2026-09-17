from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.binding_screens import screen_period_binding, screen_unit_binding
from esg_reliable_discovery.knowledge_base import sha256_file, stable_id

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/period_unit_binding_screens_v0.1"
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"


CASES = [
    {
        "name": "period_positive_bayer_scope2_2024",
        "screen": "period",
        "expected": "eligible",
        "gap_id": "gap-052434b1b74b03e947f2860e",
        "fact_record_id": "fact-2078328caf061dbd60529a1b",
        "native_source": {
            "path": "data/raw/p22_staging/bayer-annual-report-2025.pdf",
            "sha256": "0af4a9d19fd9d4cba72c1ec062802199873f2379f84112dc2db5dc9605ce769b",
        },
        "page": 151,
        "row_label": "Gross market-based Scope 2 GHG emissions",
        "value": "1.08",
        "parser_year": "2024",
    },
    {
        "name": "period_negative_volkswagen_assurance_collection",
        "screen": "period",
        "expected": "ineligible",
        "gap_id": "gap-025d82daf5d2667a9261ce50",
        "fact_record_id": "fact-9e87b181e47775b8c2ae43cf",
        "native_source": {
            "path": "data/raw/p12_staging/volkswagen-group-annual-report-2025.pdf",
            "sha256": "6f3f1b606fe771020dad30685ad0140114e0f23fd6f0921bd47f0975e07d4338",
        },
        "page": 659,
        "parser_year": "2025",
        "value": None,
        "row_label": None,
    },
    {
        "name": "unit_positive_bayer_accident_count",
        "screen": "unit",
        "expected": "eligible",
        "gap_id": "gap-12b7f5ce62900efec68c145a",
        "fact_record_id": "fact-f1d05716293b5d2e97a15ddb",
        "native_source": {
            "path": "data/raw/p22_staging/bayer-annual-report-2025.pdf",
            "sha256": "0af4a9d19fd9d4cba72c1ec062802199873f2379f84112dc2db5dc9605ce769b",
        },
        "page": 204,
        "row_label": "Recordable work-related accidents",
        "value": "439",
        "unit_marker_candidates": ["recordable work-related accidents"],
        "bound_quote": (
            "We registered a total of 403 recordable work-related accidents "
            "in 2025 (2024: 439)"
        ),
        "conversion_required": False,
    },
    {
        "name": "unit_negative_gsk_mixed_headcount_fte",
        "screen": "unit",
        "expected": "ineligible",
        "gap_id": "gap-1c29234908c5d89b966c136f",
        "fact_record_id": "fact-36f728f36d7cbbb489c033ad",
        "native_source": {
            "path": "data/raw/p23_staging/gsk-annual-report-2025.pdf",
            "sha256": "a3ef37d848fca940f85b6c33815a5d47d1f32726fd389a03910653e24af0f4d2",
        },
        "page": 79,
        "row_label": "Management",
        "value": "18112",
        "unit_marker_candidates": ["Headcounts", "full-time equivalent employees (FTEs)"],
        "bound_quote": "Headcounts as of 31 December 2025; full-time equivalent employees (FTEs)",
        "conversion_required": False,
    },
]


def main() -> None:
    summary_path = OUTPUT / "screen_summary.lock.json"
    if summary_path.exists():
        raise FileExistsError("refusing_to_overwrite_period_unit_screens")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    gaps = {
        item["gap_id"]: item
        for item in (json.loads(line) for line in GAPS.read_text().splitlines() if line)
    }
    results = []
    for case in CASES:
        if case["gap_id"] not in gaps:
            raise ValueError(f"parent_gap_missing:{case['gap_id']}")
        native = ROOT / case["native_source"]["path"]
        if sha256_file(native) != case["native_source"]["sha256"]:
            raise ValueError(f"native_hash_mismatch:{case['name']}")
        result = (
            screen_period_binding(case, ROOT)
            if case["screen"] == "period"
            else screen_unit_binding(case, ROOT)
        )
        if result["eligibility"] != case["expected"]:
            raise ValueError(f"unexpected_screen_result:{case['name']}")
        record = {
            "schema_version": "0.1",
            "record_kind": "deterministic_binding_screen",
            "screen_id": stable_id("binding-screen", {"case": case["name"], "result": result}),
            "case_name": case["name"],
            "gap_id": case["gap_id"],
            "fact_record_id": case["fact_record_id"],
            "result": result,
            "validation": {
                "source_hash_prevalidated": True,
                "fact_write_performed": False,
                "trust_promotion_performed": False,
                "semantic_inference_performed": False,
                "cloud_transmission_performed": False,
            },
        }
        path = OUTPUT / f"{case['name']}.screen.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        results.append(
            {
                "case_name": case["name"],
                "screen": case["screen"],
                "eligibility": result["eligibility"],
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
            }
        )
    summary = {
        "schema_version": "0.1",
        "status": "period_unit_exposed_screens_complete",
        "results": results,
        "eligible": sum(item["eligibility"] == "eligible" for item in results),
        "ineligible": sum(item["eligibility"] == "ineligible" for item in results),
        "fact_records_sha256": sha256_file(FACTS),
        "knowledge_gaps_sha256": sha256_file(GAPS),
        "fact_write_performed": False,
        "trust_promotion_performed": False,
        "cloud_transmission_performed": False,
        "next_gate": "freeze an unseen validation set for four diagnostics and two screeners",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"eligible": summary["eligible"], "ineligible": summary["ineligible"]}))


if __name__ == "__main__":
    main()
