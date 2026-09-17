from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
GAPS = ROOT / "data/knowledge_bases/v0.1/knowledge_gap_records.jsonl"
OUTPUT = ROOT / (
    "data/results/heterogeneous_component_candidate_inventory_RESUME03_v0.1.lock.json"
)
COMPONENTS = [
    "FIELD_EVIDENCE_BINDING_INCOMPLETE",
    "PERIOD_ATTACHMENT_INCOMPLETE",
    "UNIT_ATTACHMENT_INCOMPLETE",
    "TABLE_CELL_BINDING_INCOMPLETE",
    "NATIVE_PDF_CORROBORATION_INCOMPLETE",
    "CALCULATION_LINEAGE_INCOMPLETE",
]
SECTORS = {
    "P10": "energy",
    "P11": "industrial_technology",
    "P12": "automotive",
    "P13": "electrical_equipment",
    "P14": "consumer_beauty",
    "P15": "pharmaceuticals",
    "P16": "pharmaceuticals",
    "P17": "automotive",
    "P18": "telecommunications",
    "P19": "pharmaceuticals",
    "P20": "building_materials",
    "P21": "chemicals",
    "P22": "life_sciences",
    "P23": "pharmaceuticals",
}
USED_DOCUMENTS = {
    "FIELD_EVIDENCE_BINDING_INCOMPLETE": {
        "P12-VOLKSWAGEN-AR2025",
        "P18-DEUTSCHE-TELEKOM-AR2025",
    },
    "PERIOD_ATTACHMENT_INCOMPLETE": {
        "P12-VOLKSWAGEN-AR2025",
        "P15-NOVARTIS-NFM2025",
        "P22-BAYER-AR2025",
    },
    "UNIT_ATTACHMENT_INCOMPLETE": {
        "P16-SANOFI-SS2025",
        "P22-BAYER-AR2025",
        "P23-GSK-AR2025",
    },
    "TABLE_CELL_BINDING_INCOMPLETE": {
        "P18-DEUTSCHE-TELEKOM-AR2025",
        "P19-NOVO-NORDISK-AR2025",
        "P21-BASF-AR2025",
        "P23-GSK-AR2025",
    },
    "NATIVE_PDF_CORROBORATION_INCOMPLETE": {
        "P17-BMW-GROUP-REPORT-2025",
        "P18-DEUTSCHE-TELEKOM-AR2025",
        "P19-NOVO-NORDISK-AR2025",
    },
    "CALCULATION_LINEAGE_INCOMPLETE": {"P22-BAYER-AR2025"},
}


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _layout(fact):
    quotes = [str(item.get("quote", "")) for item in fact.get("evidence", [])]
    if any("</td>" in quote for quote in quotes):
        return "structured_table"
    if any(re.fullmatch(r"[-+]?\d[\d,]*(?:\.\d+)?%?", quote.strip()) for quote in quotes):
        return "atomic_literal_collection"
    return "narrative_or_compound"


def _score(signature, fact):
    evidence = fact.get("evidence", [])
    value = fact.get("value")
    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    table = any("</td>" in str(item.get("quote", "")) for item in evidence)
    atomic = any(
        re.fullmatch(r"[-+]?\d[\d,]*(?:\.\d+)?%?", str(item.get("quote", "")).strip())
        for item in evidence
    )
    period = bool(fact.get("qualifiers", {}).get("period_literal"))
    preferences = {
        "FIELD_EVIDENCE_BINDING_INCOMPLETE": (len(evidence) == 1, atomic),
        "PERIOD_ATTACHMENT_INCOMPLETE": (numeric and period, table),
        "UNIT_ATTACHMENT_INCOMPLETE": (numeric, table),
        "TABLE_CELL_BINDING_INCOMPLETE": (numeric and table, period),
        "NATIVE_PDF_CORROBORATION_INCOMPLETE": (numeric and atomic, period),
        "CALCULATION_LINEAGE_INCOMPLETE": (
            str(fact.get("predicate", {}).get("canonical_key", "")).startswith("calculated"),
            table,
        ),
    }
    first, second = preferences[signature]
    return (int(first), int(second), -len(evidence), fact["record_id"])


def _used_facts():
    used = set()
    paths = list((ROOT / "data/manifests").glob("*.json"))
    paths.extend((ROOT / "tests").glob("*.py"))
    paths.extend((ROOT / "scripts").glob("*.py"))
    for path in paths:
        used.update(re.findall(r"fact-[0-9a-f]{24}", path.read_text()))
    return used


def main():
    if OUTPUT.exists():
        raise FileExistsError("refusing_to_overwrite_heterogeneous_candidate_inventory")
    facts = {item["record_id"]: item for item in _jsonl(FACTS)}
    used = _used_facts()
    pools = defaultdict(list)
    for gap in _jsonl(GAPS):
        signature = gap["gap_signature"]
        if signature not in COMPONENTS or gap["fact_record_id"] in used:
            continue
        fact = facts[gap["fact_record_id"]]
        metadata = (fact.get("subject", {}).get("document_metadata") or [{}])[0]
        path = metadata.get("local_path")
        if not path or not (ROOT / path).is_file():
            continue
        document_id = (fact.get("subject", {}).get("document_ids") or [""])[0]
        if document_id in USED_DOCUMENTS[signature]:
            continue
        pools[signature].append((document_id, gap, fact, metadata))

    components = []
    for signature in COMPONENTS:
        by_document = defaultdict(list)
        for item in pools[signature]:
            by_document[item[0]].append(item)
        representatives = []
        for _document_id, items in by_document.items():
            selected = max(items, key=lambda item: _score(signature, item[2]))
            representatives.append(selected)
        representatives.sort(key=lambda item: _score(signature, item[2]), reverse=True)
        selected = representatives[:4]
        components.append(
            {
                "component": signature,
                "available_facts": len(pools[signature]),
                "available_distinct_reports": len(by_document),
                "coverage_gap": (
                    "no_unexposed_source_report_available"
                    if not by_document
                    else "only_one_unexposed_source_report_available"
                    if len(by_document) == 1
                    else None
                ),
                "shortlist": [
                    {
                        "gap_id": gap["gap_id"],
                        "fact_record_id": fact["record_id"],
                        "task_id": fact["subject"]["task_id"],
                        "document_id": document_id,
                        "company": metadata.get("company"),
                        "sector": SECTORS.get(document_id.split("-")[0], "unclassified"),
                        "layout": _layout(fact),
                        "value_type": type(fact.get("value")).__name__,
                        "evidence_count": len(fact.get("evidence", [])),
                        "source_path": metadata["local_path"],
                        "source_sha256": metadata["sha256"],
                        "screening_only": True,
                    }
                    for document_id, gap, fact, metadata in selected
                ],
            }
        )
    output = {
        "schema_version": "0.1",
        "record_kind": "heterogeneous_component_candidate_inventory",
        "status": "candidate_inventory_complete_not_frozen_for_execution",
        "resume_lineage": {
            "parent": (
                "data/results/"
                "heterogeneous_component_candidate_inventory_RESUME02_v0.1.lock.json"
            ),
            "parent_sha256": "ed1057b07aa36b7c611fe8be0f969d541678dca0baf6cea5e85a53543a074db2",
            "reason": (
                "RESUME02 correctly excluded exposed reports but used an imprecise "
                "coverage-gap label when no unexposed calculation report remained"
            ),
            "parent_used_for_execution": False,
        },
        "selection_boundary": (
            "metadata and frozen evidence structure only; all fact IDs referenced by "
            "manifests, tests, or scripts were excluded; adapters were not executed on "
            "shortlisted samples"
        ),
        "components": components,
        "parent_hashes": {
            "fact_records": sha256_file(FACTS),
            "knowledge_gap_records": sha256_file(GAPS),
        },
        "safety": {
            "new_sample_executed": False,
            "fact_write_performed": False,
            "trust_promotion_performed": False,
            "cloud_transmission_performed": False,
        },
        "next_gate": (
            "audit shortlists against source pages, define positive and negative "
            "contracts, then freeze a single-execution manifest"
        ),
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({item["component"]: len(item["shortlist"]) for item in components}))


if __name__ == "__main__":
    main()
