from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


NORMALIZATION: dict[str, dict[str, Any]] = {
    "fact-5aa3ea5a6ab667a59f54393a": {
        "entity": "Shell plc",
        "metric": "limited-assurance page-range coverage stated on source page 427",
        "period": "2025 assurance engagement",
        "unit": "PDF page range",
        "scope_boundary": "EY limited assurance coverage of the Sustainability Statements",
        "value": "335-425",
        "source_page": 427,
        "assurance_page": 427,
        "scope_basis": "direct_independent_statement",
        "scope_evidence": (
            "EY directly states that its limited assurance report covers the Sustainability "
            "Statements presented on pages 335–425, including incorporated references."
        ),
    },
    "fact-1f0a6b6a84c43bea2977dad6": {
        "entity": "Deutsche Telekom AG and Group",
        "metric": "Scope 1 GHG emissions",
        "period": "2025",
        "unit": "tCO2e",
        "scope_boundary": "Scope 1 component of gross Scope 1 and 2 market-based emissions",
        "value": 223790,
        "source_page": 133,
        "assurance_page": 370,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the entire 2025 Combined Sustainability Statement with limited "
            "assurance and names gross Scope 1 and 2 market-based emissions for "
            "reasonable assurance."
        ),
    },
    "fact-33dc52468b16e903f865b648": {
        "entity": "Novo Nordisk A/S Group",
        "metric": "Scope 3 GHG emissions",
        "period": "2025",
        "unit": "thousand tCO2e",
        "scope_boundary": "Group total Scope 3 reported in the Sustainability Statement",
        "value": 2507,
        "source_page": 66,
        "assurance_page": 123,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the Group Sustainability Statement for 1 January–31 December "
            "2025; the Scope 3 table is within that statement and no relevant exclusion is stated."
        ),
    },
    "fact-6649f777b0b46bbd59fc139b": {
        "entity": "Novo Nordisk A/S Group",
        "metric": "Scope 1 GHG emissions",
        "period": "2025",
        "unit": "thousand tCO2e",
        "scope_boundary": "Group Scope 1 reported in the Sustainability Statement",
        "value": 120,
        "source_page": 66,
        "assurance_page": 123,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the Group Sustainability Statement for 1 January–31 December "
            "2025; the Scope 1 table is inside that statement and no relevant exclusion is stated."
        ),
    },
    "fact-036a2fafecf906506c204e9f": {
        "entity": "Holcim Ltd Group",
        "metric": "Gross Scope 1 emissions",
        "period": "2025",
        "unit": "million tons CO2",
        "scope_boundary": "Group gross Scope 1",
        "value": 52,
        "source_page": 86,
        "assurance_page": 136,
        "scope_basis": "metric_explicitly_listed",
        "scope_evidence": (
            "EY Appendix 1 explicitly lists Absolute Scope 1 emissions – gross among the "
            "Sustainability Indicators covered by limited assurance."
        ),
    },
    "fact-83ca1141f0ee19439b487503": {
        "entity": "Holcim Ltd Group",
        "metric": "Total Scope 3 emissions",
        "period": "2025",
        "unit": "million tons CO2e",
        "scope_boundary": "Group total Scope 3",
        "value": 37,
        "source_page": 86,
        "assurance_page": 136,
        "scope_basis": "metric_explicitly_listed",
        "scope_evidence": (
            "EY Appendix 1 explicitly lists Absolute Scope 3 emissions – total among the "
            "Sustainability Indicators covered by limited assurance."
        ),
    },
    "fact-94fe27058106272d1ebcacae": {
        "entity": "Holcim Ltd Group",
        "metric": "independent assurance provider",
        "period": "2025 assurance engagement",
        "unit": "not applicable",
        "scope_boundary": (
            "selected Sustainability Indicators and Transition Plan Disclosures; not entire report"
        ),
        "value": "EY & Associés",
        "source_page": 136,
        "assurance_page": 136,
        "scope_basis": "direct_independent_statement",
        "scope_evidence": (
            "The signed independent verifier report directly identifies EY & Associés as "
            "the Independent Verifier."
        ),
    },
    "fact-7a44310a259b876217014b7e": {
        "entity": "BASF Group",
        "metric": "Gross Scope 1 emissions",
        "period": "2025",
        "unit": "million metric tons CO2e",
        "scope_boundary": "financial control",
        "value": 15.369,
        "source_page": 194,
        "assurance_page": 433,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the 2025 Combined Sustainability Statement; the E1 climate table "
            "is inside the statement and is not among the enumerated exclusions."
        ),
    },
    "fact-b90129f774c97eb243506ac2": {
        "entity": "BASF Group",
        "metric": "Gross market-based Scope 2 emissions",
        "period": "2025",
        "unit": "million metric tons CO2e",
        "scope_boundary": "financial control; market-based",
        "value": 1.901,
        "source_page": 194,
        "assurance_page": 433,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the 2025 Combined Sustainability Statement; the E1 climate table "
            "is inside the statement and is not among the enumerated exclusions."
        ),
    },
    "fact-f12a27b106577e00d9c60faf": {
        "entity": "BASF Group",
        "metric": "Total gross Scope 3 emissions",
        "period": "2025",
        "unit": "million metric tons CO2e",
        "scope_boundary": (
            "reported Scope 3 categories under the GHG Protocol; "
            "disclosed category exclusions apply"
        ),
        "value": 93.97,
        "source_page": 195,
        "assurance_page": 433,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the 2025 Combined Sustainability Statement; the E1 climate table "
            "is inside the statement and is not among the enumerated exclusions."
        ),
    },
    "fact-212785ada7dac75b836ae699": {
        "entity": "BASF Group",
        "metric": "Gross Scope 1 emissions, adjusted comparative",
        "period": "2024",
        "unit": "million metric tons CO2e",
        "scope_boundary": "financial control",
        "value": 15.556,
        "source_page": 194,
        "assurance_page": 433,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the 2025 Combined Sustainability Statement containing the "
            "adjusted 2024 comparative in the E1 climate table; no relevant exclusion is stated."
        ),
    },
    "fact-ef71816124680daff75eb6df": {
        "entity": "BASF Group",
        "metric": "Gross market-based Scope 2 emissions, adjusted comparative",
        "period": "2024",
        "unit": "million metric tons CO2e",
        "scope_boundary": "financial control; market-based",
        "value": 2.396,
        "source_page": 194,
        "assurance_page": 433,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the 2025 Combined Sustainability Statement containing the "
            "adjusted 2024 comparative in the E1 climate table; no relevant exclusion is stated."
        ),
    },
    "fact-8fe1c8be8ea7aa849072ba0f": {
        "entity": "BASF Group",
        "metric": "Total gross Scope 3 emissions, adjusted comparative",
        "period": "2024",
        "unit": "million metric tons CO2e",
        "scope_boundary": (
            "financial control; reported Scope 3 categories under the GHG Protocol; "
            "disclosed category exclusions apply"
        ),
        "value": 92.33,
        "source_page": 195,
        "assurance_page": 433,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": (
            "Deloitte covers the 2025 Combined Sustainability Statement containing the "
            "adjusted 2024 comparative in the E1 climate table; no relevant exclusion is stated."
        ),
    },
}


def add_normalization(
    fact_id: str,
    *,
    entity: str,
    metric: str,
    period: str,
    unit: str,
    boundary: str,
    value: Any,
    source_page: int,
    assurance_page: int,
    evidence: str,
) -> None:
    NORMALIZATION[fact_id] = {
        "entity": entity,
        "metric": metric,
        "period": period,
        "unit": unit,
        "scope_boundary": boundary,
        "value": value,
        "source_page": source_page,
        "assurance_page": assurance_page,
        "scope_basis": "whole_statement_inclusion_with_exclusions_checked",
        "scope_evidence": evidence,
    }


BMW_SCOPE = (
    "PwC covers the 2025 BMW Group Sustainability Report with limited assurance; the safety "
    "disclosure is inside the report and is not identified as excluded."
)
DT_SCOPE = (
    "Deloitte covers the 2025 Deutsche Telekom Combined Sustainability Statement with limited "
    "assurance; the disclosure is inside the statement and no relevant exclusion is stated."
)
NN_SCOPE = (
    "Deloitte covers the Novo Nordisk Group Sustainability Statement for 2025 with limited "
    "assurance; the disclosure is inside the statement and no relevant exclusion is stated."
)

add_normalization(
    "fact-62234554a98221e8c3ce2772",
    entity="BMW Group",
    metric="fatalities due to work-related accidents",
    period="2025",
    unit="count",
    boundary=(
        "all work-related fatalities stated for BMW Group sites; employees and external workers"
    ),
    value=4,
    source_page=178,
    assurance_page=372,
    evidence=BMW_SCOPE,
)

for fact_id, metric, period, unit, boundary, value, page in (
    (
        "fact-1f8cdc4d2a7d244d7ce169be",
        "total energy consumption",
        "2025",
        "MWh",
        "total energy consumption reported by Deutsche Telekom Group",
        11956990,
        131,
    ),
    (
        "fact-6ae0e913c820700806916dc9",
        "employees in International geography",
        "2025",
        "FTE",
        "Deutsche Telekom employees outside Germany, measured in FTEs",
        127327,
        109,
    ),
    (
        "fact-8da460bee64eb4ecb292f56f",
        "employees in Germany",
        "2025",
        "FTE",
        "Deutsche Telekom employees in Germany, measured in FTEs",
        70751,
        109,
    ),
    (
        "fact-b1ce8eff559dad748d0d183d",
        "employees in Germany",
        "2024",
        "FTE",
        "Deutsche Telekom employees in Germany, measured in FTEs",
        74550,
        109,
    ),
    (
        "fact-f4607bdd70e350a4cc5a322a",
        "employees in International geography",
        "2024",
        "FTE",
        "Deutsche Telekom employees outside Germany, measured in FTEs",
        123644,
        109,
    ),
):
    add_normalization(
        fact_id,
        entity="Deutsche Telekom AG and Group",
        metric=metric,
        period=period,
        unit=unit,
        boundary=boundary,
        value=value,
        source_page=page,
        assurance_page=370,
        evidence=DT_SCOPE,
    )

for fact_id, metric, period, unit, boundary, value, page in (
    (
        "fact-5c9806380a1237336b292178",
        "total energy consumption",
        "2025",
        "GWh",
        "Novo Nordisk total energy consumption related to own operations",
        1726,
        65,
    ),
    (
        "fact-78f2df4d250210c3cd7fe53e",
        "total energy consumption",
        "2024",
        "GWh",
        "Novo Nordisk total energy consumption related to own operations",
        1400,
        65,
    ),
    (
        "fact-896053181b213daa2d759c9d",
        "renewable energy consumption",
        "2025",
        "GWh",
        "Novo Nordisk energy consumption from renewable sources in own operations",
        984,
        65,
    ),
    (
        "fact-e42fb7592c311e4e31456c72",
        "total CapEx denominator",
        "2025",
        "mDKK",
        "Novo Nordisk total CapEx denominator in the adjusted EU Taxonomy overview",
        94249,
        80,
    ),
    (
        "fact-801e0154afff454f20f6cda2",
        "permanent employees",
        "2025",
        "headcount",
        "Novo Nordisk own-workforce employees with permanent employment contracts",
        64974,
        58,
    ),
    (
        "fact-be7af8998b7c2d573d35fc01",
        "temporary employees",
        "2025",
        "headcount",
        "Novo Nordisk own-workforce employees with temporary employment contracts",
        4531,
        58,
    ),
    (
        "fact-cea0a41e87c27cadecde5fcc",
        "temporary employees",
        "2024",
        "headcount",
        "Novo Nordisk own-workforce employees with temporary employment contracts",
        5487,
        58,
    ),
    (
        "fact-ec25d92c731e09bd196ea6f7",
        "permanent employees",
        "2024",
        "headcount",
        "Novo Nordisk own-workforce employees with permanent employment contracts",
        68669,
        58,
    ),
):
    add_normalization(
        fact_id,
        entity="Novo Nordisk A/S Group",
        metric=metric,
        period=period,
        unit=unit,
        boundary=boundary,
        value=value,
        source_page=page,
        assurance_page=123,
        evidence=NN_SCOPE,
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def dump_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def main() -> None:
    fact_path = KB / "fact_records.jsonl"
    review_path = KB / "independent_corroboration_reviews.jsonl"
    joint_path = KB / "joint_fact_qualifications.jsonl"
    facts = {record["record_id"]: record for record in load_jsonl(fact_path)}
    reviews = {record["fact_record_id"]: record for record in load_jsonl(review_path)}
    joints = {record["fact_record_id"]: record for record in load_jsonl(joint_path)}

    adjudications = []
    trusted_facts = []
    for fact_id, normalized in sorted(NORMALIZATION.items()):
        fact = facts[fact_id]
        review = reviews[fact_id]
        joint = joints[fact_id]
        if joint["qualification_status"] != "jointly_qualified_candidate":
            raise ValueError(f"{fact_id} is not jointly qualified")
        source = review["candidate_source"]
        assurance_path = ROOT / source["local_artifact"]
        if sha256_file(assurance_path) != source["local_artifact_sha256"]:
            raise ValueError(f"assurance artifact changed for {fact_id}")
        if fact["value"] != normalized["value"]:
            raise ValueError(f"value mismatch for {fact_id}")

        dimensions = {
            "entity": {
                "status": "matched",
                "normalized": normalized["entity"],
                "evidence": "issuer identity in the frozen report and assurance addressee",
            },
            "metric": {
                "status": "matched",
                "normalized": normalized["metric"],
                "evidence": normalized["scope_evidence"],
            },
            "period": {
                "status": "matched",
                "normalized": normalized["period"],
                "evidence": (
                    f"source page {normalized['source_page']} binds the value to "
                    f"{normalized['period']}; the assurance engagement covers the containing "
                    "2025 Combined Sustainability Statement"
                ),
            },
            "unit": {
                "status": "matched",
                "normalized": normalized["unit"],
                "evidence": (
                    "unit heading or literal on frozen source page "
                    f"{normalized['source_page']}"
                ),
            },
            "scope_boundary": {
                "status": "matched",
                "normalized": normalized["scope_boundary"],
                "evidence": (
                    "metric label, table header or disclosed boundary note in the frozen source"
                ),
            },
            "value": {
                "status": "matched",
                "normalized": normalized["value"],
                "evidence": (
                    "unique source-native binding on page "
                    f"{normalized['source_page']}; the value is "
                    "within the independently assured disclosure scope"
                ),
            },
        }
        adjudication_id = stable_id(
            "adj", {"fact_record_id": fact_id, "assurance_sha256": source["local_artifact_sha256"]}
        )
        adjudications.append(
            {
                "schema_version": "0.1",
                "record_kind": "tier_b_independent_adjudication",
                "adjudication_id": adjudication_id,
                "fact_record_id": fact_id,
                "task_id": fact["subject"]["task_id"],
                "assurance_scope_basis": normalized["scope_basis"],
                "dimensions": dimensions,
                "promotion_decision": {
                    "eligible": True,
                    "target_tier": "B",
                    "reason": (
                        "all_six_dimensions_match_and_independent_limited_assurance_is_frozen"
                    ),
                    "locked_experiments_modified": False,
                },
            }
        )

        promoted = copy.deepcopy(fact)
        promoted["knowledge_status"] = "promoted_validated_fact"
        promoted["trust_tier"] = "B"
        promoted["subject"]["entity_label"] = normalized["entity"]
        promoted["qualifiers"].update(
            {
                "period_literal": normalized["period"],
                "reference_period": normalized["period"],
                "normalized_unit": normalized["unit"],
                "scope_boundary": normalized["scope_boundary"],
                "value_origin": "source_disclosure_independently_assured",
                "answer_status": "verified",
            }
        )
        promoted["evidence"].append(
            {
                "source_id": f"ASSURANCE-{source['provider']}",
                "pdf_page": normalized["assurance_page"],
                "quote": normalized["scope_evidence"],
                "role": "independent_assurance_scope",
                "local_artifact": source["local_artifact"],
                "local_artifact_sha256": source["local_artifact_sha256"],
            }
        )
        promoted["provenance"] = {
            "source_artifact": source["local_artifact"],
            "source_sha256": source["local_artifact_sha256"],
            "reference_status": f"tier_b_adjudication:{adjudication_id}",
            "simulated": False,
        }
        promoted["promotion"] = {
            "eligible": True,
            "reason": f"passed_independent_adjudication:{adjudication_id}",
        }
        trusted_facts.append(promoted)

    adjudication_schema = json.loads(
        (ROOT / "schemas/knowledge/tier-b-independent-adjudication-v0.1.schema.json").read_text()
    )
    fact_schema = json.loads((ROOT / "schemas/knowledge/fact-record-v0.1.schema.json").read_text())
    validate_records(adjudications, adjudication_schema)
    validate_records(trusted_facts, fact_schema)
    adjudication_path = KB / "tier_b_independent_adjudications.jsonl"
    trusted_path = KB / "trusted_fact_records.jsonl"
    dump_jsonl(adjudication_path, adjudications)
    dump_jsonl(trusted_path, trusted_facts)

    counts = Counter(record["assurance_scope_basis"] for record in adjudications)
    summary = {
        "schema_version": "0.1",
        "status": "tier_b_promotion_overlay_complete",
        "adjudications": len(adjudications),
        "scope_basis_counts": dict(sorted(counts.items())),
        "promoted_to_tier_b": len(trusted_facts),
        "source_candidate_records_modified": 0,
        "locked_experiments_modified_or_rescored": False,
        "inputs": {
            "fact_records_sha256": sha256_file(fact_path),
            "independent_reviews_sha256": sha256_file(review_path),
            "joint_qualifications_sha256": sha256_file(joint_path),
        },
        "outputs": {
            "adjudications": {
                "path": adjudication_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(adjudication_path),
            },
            "trusted_facts": {
                "path": trusted_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(trusted_path),
            },
        },
        "next_gate": (
            "retain excluded items, model the 28 semantic boundary blockers, and expand "
            "controller validation and rollback"
        ),
    }
    summary_path = KB / "tier_b_independent_adjudication_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
