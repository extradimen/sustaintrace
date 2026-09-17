from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / (
    "data/results/heterogeneous_component_candidate_inventory_RESUME03_v0.1.lock.json"
)
FACTS = ROOT / "data/knowledge_bases/v0.1/fact_records.jsonl"
OUTPUT = ROOT / (
    "data/results/heterogeneous_component_source_page_audit_v0.1.lock.json"
)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _page_text(path: Path, page: int) -> str:
    result = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _literal(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _normalized(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def _quote_probe(quote: str) -> str | None:
    if "..." in quote:
        return None
    normalized = _normalized(quote)
    if not normalized:
        return None
    return normalized


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("refusing_to_overwrite_source_page_audit")
    inventory = json.loads(INVENTORY.read_text())
    facts = {item["record_id"]: item for item in _jsonl(FACTS)}
    page_cache: dict[tuple[str, int], str] = {}
    records = []
    for component in inventory["components"]:
        for candidate in component["shortlist"]:
            fact = facts[candidate["fact_record_id"]]
            source = ROOT / candidate["source_path"]
            hash_matches = source.is_file() and sha256_file(source) == candidate["source_sha256"]
            pages = sorted({int(item["pdf_page"]) for item in fact.get("evidence", [])})
            page_texts = {}
            errors = []
            for page in pages:
                key = (str(source), page)
                try:
                    page_cache.setdefault(key, _page_text(source, page))
                    page_texts[page] = page_cache[key]
                except (subprocess.CalledProcessError, UnicodeDecodeError) as exc:
                    errors.append({"page": page, "error": type(exc).__name__})
            literal = _literal(fact.get("value"))
            normalized_pages = {page: _normalized(text) for page, text in page_texts.items()}
            literal_pages = []
            if literal:
                probes = {literal.casefold(), literal.replace(",", "").casefold()}
                for page, text in normalized_pages.items():
                    compact = text.replace(",", "")
                    if any(probe in text or probe in compact for probe in probes):
                        literal_pages.append(page)
            quote_checks = []
            for evidence in fact.get("evidence", []):
                quote = str(evidence.get("quote", ""))
                probe = _quote_probe(quote)
                page = int(evidence["pdf_page"])
                quote_checks.append(
                    {
                        "page": page,
                        "quote": quote,
                        "check": (
                            "skipped_nonliteral_or_compound"
                            if probe is None
                            else "normalized_substring"
                        ),
                        "matched": (
                            None
                            if probe is None
                            else probe in normalized_pages.get(page, "")
                        ),
                    }
                )
            records.append(
                {
                    "component": component["component"],
                    "gap_id": candidate["gap_id"],
                    "fact_record_id": fact["record_id"],
                    "document_id": candidate["document_id"],
                    "source_path": candidate["source_path"],
                    "source_sha256": candidate["source_sha256"],
                    "source_hash_matches": hash_matches,
                    "evidence_pages": pages,
                    "page_text_extraction_passed": len(page_texts) == len(pages),
                    "value": fact.get("value"),
                    "literal_probe": literal,
                    "literal_pages": literal_pages,
                    "literal_present_on_evidence_page": bool(literal_pages),
                    "period_literal": fact.get("qualifiers", {}).get("period_literal"),
                    "quote_checks": quote_checks,
                    "errors": errors,
                    "screening_only": True,
                }
            )

    calculation_designs = [
        {
            "task_id": "HET-CALC-SHELL-SCOPE1-PCT-001",
            "document_id": "P10-SHELL-AR2025",
            "source_path": "data/raw/p10_staging/shell-annual-report-2025.pdf",
            "source_sha256": "90b21028e1616c41c7d73c3e996fd6128d837a41b38d432286e991aed3fbd9a1",
            "pdf_page": 369,
            "row_label": "Gross Scope 1 GHG emissions [C]",
            "unit": "million tonnes CO2e",
            "columns": {"2025": 69, "2024": 73},
            "operation": "percentage_change",
            "expression": "(69 - 73) / 73 * 100",
            "unrounded_expected": -5.47945205479452,
            "rounding": {"mode": "half_even", "decimal_places": 2},
            "rounded_expected": -5.48,
            "source_row_verified": True,
            "screening_only": True,
        },
        {
            "task_id": "HET-CALC-TOTALENERGIES-SCOPE12-PCT-001",
            "document_id": "P9-TOTALENERGIES-URD2025",
            "source_path": (
                "data/raw/p9_staging/"
                "totalenergies-universal-registration-document-2025-en.pdf"
            ),
            "source_sha256": "58e1798ad874228bb60ec110721e8880cefdd11802e2e392e619c0bbe9768c50",
            "pdf_page": 181,
            "row_label": "Scope 1+2",
            "unit": "Mt CO2e",
            "columns": {"2025": 33, "2024": 34},
            "operation": "percentage_change",
            "expression": "(33 - 34) / 34 * 100",
            "unrounded_expected": -2.941176470588235,
            "rounding": {"mode": "half_even", "decimal_places": 2},
            "rounded_expected": -2.94,
            "source_row_verified": True,
            "screening_only": True,
        },
    ]
    for design in calculation_designs:
        source = ROOT / design["source_path"]
        design["source_hash_matches"] = sha256_file(source) == design["source_sha256"]
        text = _normalized(_page_text(source, design["pdf_page"]))
        design["row_label_present"] = _normalized(design["row_label"]) in text
        design["year_columns_present"] = all(year in text for year in design["columns"])

    output = {
        "schema_version": "0.1",
        "record_kind": "heterogeneous_component_source_page_audit",
        "status": "source_page_audit_complete_not_frozen_for_execution",
        "parent": {"path": str(INVENTORY.relative_to(ROOT)), "sha256": sha256_file(INVENTORY)},
        "candidate_records": records,
        "calculation_designs": calculation_designs,
        "summary": {
            "candidate_records": len(records),
            "source_hashes_passed": sum(item["source_hash_matches"] for item in records),
            "page_extractions_passed": sum(item["page_text_extraction_passed"] for item in records),
            "candidate_literals_present": sum(
                item["literal_present_on_evidence_page"] for item in records
            ),
            "calculation_designs": len(calculation_designs),
            "calculation_source_rows_verified": sum(
                item["source_row_verified"]
                and item["source_hash_matches"]
                and item["row_label_present"]
                and item["year_columns_present"]
                for item in calculation_designs
            ),
        },
        "safety": {
            "adapter_executed": False,
            "fact_write_performed": False,
            "trust_promotion_performed": False,
            "cloud_transmission_performed": False,
        },
        "next_gate": "manual semantic review and positive/negative contract freeze",
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(output["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
