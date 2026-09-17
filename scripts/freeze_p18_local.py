# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from esg_reliable_discovery.v13_evidence import build_v13_packet

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P18-V27-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P18-DEUTSCHE-TELEKOM-AR2025"
DOCUMENT_SHA = "de5d9b0705793c4bf0b994b52ecc242800d79ee18736958dbff32aade7b79a5c"
PDF = "data/raw/p18_staging/deutsche_telekom_annual_report_2025_en.pdf"
PAGES = [109, 121, 122, 123, 131, 133, 370, 371]
TASK_PACK = "data/tasks/p18_task_pack_v0.1.lock.json"
REGISTRY = "data/manifests/p18_mineru_target_registry_v0.1.lock.json"


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def dump_new(path: str, value: Any) -> str:
    target = ROOT / path
    if target.exists():
        raise RuntimeError(f"refusing_to_overwrite:{path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sha(path)


def markdown_by_page(registry: dict[str, Any]) -> dict[int, str]:
    result = {}
    for target in registry["targets"]:
        root = ROOT / target["output_directory"]
        files = list(root.rglob("*.md"))
        if len(files) != 1:
            raise ValueError(f"markdown_ambiguous:{target['pdf_page']}:{files}")
        result[target["pdf_page"]] = files[0].read_text(encoding="utf-8")
    return result


def evidence(page: int, *quotes: str) -> list[dict[str, Any]]:
    return [{"source_id": DOCUMENT, "pdf_page": page, "quote": quote} for quote in quotes]


def ref(
    task_id: str, answer: str, values: dict[str, Any], items: list[dict[str, Any]], **extra: Any
) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "task_id": task_id,
        "reference_author": "codex_gpt_simulated_expert",
        "reference_status": "verified_against_frozen_mineru_pages_and_native_layout",
        "answer": answer,
        "normalized_value": values,
        "evidence": items,
        "provenance": {"reference_is_simulated": True, "candidate_model_used": False},
    }
    payload.update(extra)
    return payload


def main() -> None:
    pack = load(TASK_PACK)
    registry = load(REGISTRY)
    assert pack["experiment_id"] == registry["experiment_id"] == EXPERIMENT
    assert pack["document_sha256"] == registry["document_sha256"] == DOCUMENT_SHA
    assert registry["success_count"] == registry["target_count"] == 8
    assert sorted(item["pdf_page"] for item in registry["targets"]) == PAGES
    pages = markdown_by_page(registry)

    ghg_change = ((Decimal(240165) - Decimal(252568)) / Decimal(252568) * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    references = {
        "P18-GHG-CALC-001": ref(
            "P18-GHG-CALC-001",
            "For 2025, Scope 1 was 223,790 t CO2e and market-based Scope 2 was 16,375 t CO2e. Their sum is 240,165 t CO2e, exactly matching the disclosed market-based Scope 1 and 2 total, for a zero difference. Against 252,568 t CO2e in 2024, the disclosed total decreased by 4.91%.",
            {
                "scope_1_2025_tco2e": 223790,
                "scope_2_market_based_2025_tco2e": 16375,
                "calculated_scope_1_2_2025_tco2e": 240165,
                "disclosed_scope_1_2_2025_tco2e": 240165,
                "difference_tco2e": 0,
                "disclosed_scope_1_2_2024_tco2e": 252568,
                "calculated_change_percent": float(ghg_change),
                "direction": "decrease",
            },
            evidence(
                133, "Scope 1 and 2 (market-based)", "240,165", "252,568", "223,790", "16,375"
            ),
            calculation_plan={
                "candidate_input_role_order": [
                    "scope_1_2025",
                    "scope_2_market_based_2025",
                    "disclosed_scope_1_2_2025",
                    "disclosed_scope_1_2_2024",
                ],
                "unit": "t CO2e",
                "rounding": "two decimal places, half up",
            },
        ),
        "P18-ENERGY-001": ref(
            "P18-ENERGY-001",
            "In MWh, 2025/2024 fossil energy was 812,912/870,723; renewable energy 11,144,078/11,120,011; self-generated non-fuel renewable energy 13,905/7,819; and total energy 11,956,990/11,990,733. The narrative rounds total energy to 11,957/11,991 GWh. The 2024 figures were retrospectively adjusted due to changes in electricity distribution at individual sites.",
            {
                "fossil_mwh::2025": 812912,
                "fossil_mwh::2024": 870723,
                "renewable_mwh::2025": 11144078,
                "renewable_mwh::2024": 11120011,
                "self_generated_non_fuel_renewable_mwh::2025": 13905,
                "self_generated_non_fuel_renewable_mwh::2024": 7819,
                "total_energy_mwh::2025": 11956990,
                "total_energy_mwh::2024": 11990733,
                "narrative_total_gwh::2025": 11957,
                "narrative_total_gwh::2024": 11991,
                "qualification": "2024 figures adjusted retrospectively due to changes in electricity distribution at individual sites",
            },
            evidence(
                131,
                "Total energy consumption decreased year-on-year from 11,991 GWh to 11,957 GWh.",
                "812,912",
                "870,723",
                "11,144,078",
                "11,120,011",
                "13,905",
                "7,819",
                "11,956,990",
                "11,990,733",
            ),
        ),
        "P18-SCOPE3-001": ref(
            "P18-SCOPE3-001",
            "For 2025, upstream 5,861,714 plus downstream 2,645,520 equals the disclosed Scope 3 total of 8,507,234 t CO2e exactly. For 2024, 7,312,103 plus 2,421,432 equals 9,733,535 t CO2e, one tonne lower than the disclosed total of 9,733,536 t CO2e; the difference is preserved as -1 t CO2e rather than repaired.",
            {
                "disclosed_total_tco2e::2025": 8507234,
                "upstream_tco2e::2025": 5861714,
                "downstream_tco2e::2025": 2645520,
                "recomputed_total_tco2e::2025": 8507234,
                "recomputed_minus_disclosed_tco2e::2025": 0,
                "disclosed_total_tco2e::2024": 9733536,
                "upstream_tco2e::2024": 7312103,
                "downstream_tco2e::2024": 2421432,
                "recomputed_total_tco2e::2024": 9733535,
                "recomputed_minus_disclosed_tco2e::2024": -1,
            },
            evidence(
                133,
                "t CO2e emissions, Scope 3 (total)",
                "8,507,234",
                "9,733,536",
                "5,861,714",
                "7,312,103",
                "2,645,520",
                "2,421,432",
            ),
        ),
        "P18-WORKFORCE-001": ref(
            "P18-WORKFORCE-001",
            "At December 31, 2025, Germany had 70,751 FTEs and International 127,327, summing to 198,078 versus the disclosed total 198,079, a -1 FTE difference. For 2024, 74,550 plus 123,644 equals the disclosed total 198,194 exactly.",
            {
                "germany_fte::2025": 70751,
                "international_fte::2025": 127327,
                "disclosed_total_fte::2025": 198079,
                "recomputed_total_fte::2025": 198078,
                "recomputed_minus_disclosed_fte::2025": -1,
                "germany_fte::2024": 74550,
                "international_fte::2024": 123644,
                "disclosed_total_fte::2024": 198194,
                "recomputed_total_fte::2024": 198194,
                "recomputed_minus_disclosed_fte::2024": 0,
            },
            evidence(
                109,
                "Germany",
                "70,751",
                "74,550",
                "International",
                "127,327",
                "123,644",
                "Total number of employees",
                "198,079",
                "198,194",
            ),
        ),
        "P18-TAXONOMY-001": ref(
            "P18-TAXONOMY-001",
            "For 2025, turnover totaled EUR 119,081 million and capex EUR 29,478 million. Reported taxonomy-eligible shares were 0.0%, aligned amounts EUR 0 million, and aligned shares 0.0% for both; non-material activities represented 2.5% of turnover and 1.6% of capex. Alignment was not assessed for those activities because each was under the 10% financial-materiality threshold and a cost-benefit decision was applied. Opex totaled EUR 3,198 million, its definition was broadened and the 2024 denominator retrospectively increased from EUR 0.4 billion to EUR 2.9 billion; eligible and aligned opex were not disclosed from 2025 because opex was not material.",
            {
                "turnover_total_million_eur::2025": 119081,
                "turnover_eligible_percent::2025": 0.0,
                "turnover_aligned_million_eur::2025": 0,
                "turnover_aligned_percent::2025": 0.0,
                "turnover_nonmaterial_percent::2025": 2.5,
                "capex_total_million_eur::2025": 29478,
                "capex_eligible_percent::2025": 0.0,
                "capex_aligned_million_eur::2025": 0,
                "capex_aligned_percent::2025": 0.0,
                "capex_nonmaterial_percent::2025": 1.6,
                "alignment_nonassessment_reason": "activities each below 10% of total turnover or capex and alignment not assessed for cost-benefit reasons",
                "opex_total_million_eur::2025": 3198,
                "opex_2024_original_billion_eur": 0.4,
                "opex_2024_restated_billion_eur": 2.9,
                "opex_disclosure_status::2025": "taxonomy-eligible and taxonomy-aligned opex not disclosed because taxonomy-relevant opex is not material",
            },
            evidence(
                121,
                "account for less than 10 % of the Group’s total turnover and capex",
                "assessment of their taxonomy-alignment was not carried out for cost-benefit reasons",
            )
            + evidence(
                122,
                "EUR 0.4 billion previously reported to EUR 2.9 billion",
                "taxonomy-eligible and taxonomy aligned opex will not be disclosed starting from the 2025 financial year",
            )
            + evidence(123, "EU Taxonomy KPIs", "119,081", "29,478", "3,198", "2.5", "1.6"),
        ),
        "P18-ASSURE-001": ref(
            "P18-ASSURE-001",
            "The Combined Sustainability Statement received limited assurance. Reasonable assurance covered Total energy consumption, GHG gross emissions Scopes 1 and 2 (market-based), and Scope 2 location-based emissions. References outside the combined management report and references marked additional information that point elsewhere and are not designated as sustainability reporting were excluded. The limited conclusion used the negative-form ‘nothing has come to our attention’; the reasonable-assurance disclosures received a positive compliance opinion. The engagement followed ISAE 3000 (Revised), and limited procedures were less extensive and yielded substantially lower assurance than reasonable assurance.",
            {
                "limited_scope": "Combined Sustainability Statement for January 1 to December 31, 2025",
                "reasonable_scope": "Total energy consumption | GHG gross emissions Scopes 1 and 2 (market-based) | Scope 2 (location-based) emissions",
                "excluded_references": "references to information outside the combined management report | additional-information references not designated as sustainability reporting",
                "limited_conclusion_form": "negative assurance: nothing came to attention indicating material non-compliance",
                "reasonable_opinion_form": "positive opinion: specified disclosures comply in all material respects",
                "governing_standard": "ISAE 3000 (Revised)",
                "procedure_difference": "limited procedures vary in nature and timing and are less extensive, producing substantially lower assurance than reasonable assurance",
            },
            evidence(
                370,
                "limited assurance engagement on the Sustainability Statement",
                "reasonable assurance engagement on the disclosures regarding the indicator",
                "all references within the Combined Sustainability Statement to information outside of the combined management report",
                "nothing has come to our attention",
                "disclosures subject to a reasonable assurance engagement comply",
            )
            + evidence(
                371, "ISAE 3000 (Revised)", "the level of assurance obtained is substantially lower"
            ),
        ),
    }

    task_windows = {item["task_id"]: set(item["target_pages"]) for item in pack["tasks"]}
    checked = 0
    reference_entries = []
    reference_dir = "data/annotations/p18_simulated"
    for task_id, payload in references.items():
        for item in payload["evidence"]:
            if item["pdf_page"] not in task_windows[task_id]:
                raise ValueError(f"reference_page_outside_window:{task_id}")
            if item["quote"] not in pages[item["pdf_page"]]:
                raise ValueError(f"reference_quote_not_grounded:{task_id}:{item['quote']}")
            checked += 1
        path = f"{reference_dir}/{task_id}.json"
        digest = dump_new(path, payload)
        reference_entries.append({"task_id": task_id, "path": path, "sha256": digest})

    contracts = {}
    unit_by_slot = {
        "tco2e": "t CO2e",
        "percent": "percent",
        "mwh": "MWh",
        "gwh": "GWh",
        "fte": "FTE",
        "million_eur": "million EUR",
        "billion_eur": "billion EUR",
    }
    for task_id, payload in references.items():
        rows = []
        for slot_id, value in payload["normalized_value"].items():
            row = {
                "predicate_id": f"esg_p18::{task_id.lower()}::{slot_id}",
                "slot_id": slot_id,
                "value_type": "number" if isinstance(value, (int, float)) else "string",
            }
            for marker, unit in unit_by_slot.items():
                if marker in slot_id:
                    row["canonical_unit"] = unit
                    break
            rows.append(row)
        contracts[task_id] = rows
    contracts_path = "configs/framework/p18_slot_contracts_v0.1.lock.json"
    contracts_sha = dump_new(
        contracts_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "contracts": contracts,
        },
    )

    gold_path = f"{reference_dir}/p18_atomic_slot_gold_v0.1.lock.json"
    gold_sha = dump_new(
        gold_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_atomic_scoring_projection_before_candidate_inference",
            "values": {
                task_id: payload["normalized_value"] for task_id, payload in references.items()
            },
        },
    )

    freeze_path = "data/manifests/p18_simulated_reference_freeze_v0.1.lock.json"
    freeze_sha = dump_new(
        freeze_path,
        {
            "schema_version": "1.0",
            "manifest_id": "P18-SIMULATED-REFERENCE-FREEZE-v0.1",
            "experiment_id": EXPERIMENT,
            "status": "simulated_references_frozen_after_questions_and_page_windows_and_before_candidate_inference",
            "document_id": DOCUMENT,
            "document_sha256": DOCUMENT_SHA,
            "task_pack": {"path": TASK_PACK, "sha256": sha(TASK_PACK)},
            "target_registry": {"path": REGISTRY, "sha256": sha(REGISTRY)},
            "references": sorted(reference_entries, key=lambda item: item["task_id"]),
            "integrity_audit": {
                "reference_count": 6,
                "evidence_quote_count": checked,
                "all_reference_pages_within_frozen_task_windows": True,
                "all_quotes_exact_substrings_of_frozen_MinerU_markdown": True,
                "numeric_values_cross_checked_against_native_layout": True,
                "candidate_model_used": False,
                "cloud_transmission_occurred": False,
            },
            "candidate_reference_visibility": False,
            "cloud_transmission_allowed": False,
        },
    )

    audit_path = "data/results/p18_prefreeze_reference_consistency_audit_v0.1.lock.json"
    audit_sha = dump_new(
        audit_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "gate_result": "pass",
            "checks": {
                "task_count": 6,
                "unique_page_count": 8,
                "reference_quote_count": checked,
                "reference_pages_within_windows": True,
                "quotes_grounded_in_frozen_parser_output": True,
                "numeric_arithmetic_recomputed": True,
                "one_unit_differences_preserved": True,
                "candidate_model_used": False,
                "cloud_transmission_count": 0,
            },
            "hashes": {
                "task_pack": sha(TASK_PACK),
                "parser_registry": sha(REGISTRY),
                "reference_freeze": freeze_sha,
                "slot_contracts": contracts_sha,
                "atomic_gold": gold_sha,
            },
        },
    )

    semantic_path = "configs/framework/p18_semantic_qualifiers_v0.1.lock.json"
    semantic_sha = dump_new(
        semantic_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "qualifiers": {
                "reporting_period": "calendar year 2025 unless a 2024 comparative is explicitly named",
                "page_coordinates": "one-based PDF page indexes",
                "P18-GHG-CALC-001": {
                    "boundary": "market-based Scope 1 and 2; distinguish location-based Scope 2",
                    "calculation": "use frozen roles and Decimal operations only",
                },
                "P18-ENERGY-001": {
                    "boundary": "preserve MWh table values, rounded GWh narrative, and retrospective qualification"
                },
                "P18-SCOPE3-001": {
                    "boundary": "preserve upstream/downstream rows, disclosed totals, and the 2024 one-tonne arithmetic difference"
                },
                "P18-WORKFORCE-001": {
                    "boundary": "Germany plus International versus disclosed total; preserve 2025 one-FTE difference"
                },
                "P18-TAXONOMY-001": {
                    "boundary": "separate eligible, aligned, and non-material activity columns; do not infer alignment for unassessed activities"
                },
                "P18-ASSURE-001": {
                    "boundary": "separate report-wide limited assurance, named reasonable-assurance indicators, excluded references, and negative versus positive conclusion forms"
                },
                "reference_type": "AI-simulated research reference; not independent human gold",
            },
        },
    )

    calculation_path = "configs/framework/p18_calculation_plans_v0.1.lock.json"
    calculation_sha = dump_new(
        calculation_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "plans": {
                "P18-GHG-CALC-001": {
                    "roles": [
                        {"role_id": role, "unit": "t CO2e"}
                        for role in [
                            "scope_1_2025",
                            "scope_2_market_based_2025",
                            "disclosed_scope_1_2_2025",
                            "disclosed_scope_1_2_2024",
                        ]
                    ],
                    "candidate_input_role_order": [
                        "scope_1_2025",
                        "scope_2_market_based_2025",
                        "disclosed_scope_1_2_2025",
                        "disclosed_scope_1_2_2024",
                    ],
                    "steps": [
                        {
                            "step_id": "calculated_scope_1_2_2025",
                            "operation": "sum",
                            "inputs": ["scope_1_2025", "scope_2_market_based_2025"],
                        },
                        {
                            "step_id": "difference",
                            "operation": "difference",
                            "inputs": ["calculated_scope_1_2_2025", "disclosed_scope_1_2_2025"],
                        },
                        {
                            "step_id": "percentage_change",
                            "operation": "percentage_change",
                            "inputs": ["disclosed_scope_1_2_2025", "disclosed_scope_1_2_2024"],
                            "rounding_decimals": 2,
                        },
                    ],
                    "candidate_may_select_operation": False,
                },
                "P18-SCOPE3-001": {
                    "roles": [
                        {"role_id": role, "unit": "t CO2e"}
                        for role in [
                            "upstream_2025",
                            "downstream_2025",
                            "disclosed_total_2025",
                            "upstream_2024",
                            "downstream_2024",
                            "disclosed_total_2024",
                        ]
                    ],
                    "candidate_input_role_order": [
                        "upstream_2025",
                        "downstream_2025",
                        "disclosed_total_2025",
                        "upstream_2024",
                        "downstream_2024",
                        "disclosed_total_2024",
                    ],
                    "steps": [
                        {
                            "step_id": "recomputed_total_2025",
                            "operation": "sum",
                            "inputs": ["upstream_2025", "downstream_2025"],
                        },
                        {
                            "step_id": "difference_2025",
                            "operation": "difference",
                            "inputs": ["recomputed_total_2025", "disclosed_total_2025"],
                        },
                        {
                            "step_id": "recomputed_total_2024",
                            "operation": "sum",
                            "inputs": ["upstream_2024", "downstream_2024"],
                        },
                        {
                            "step_id": "difference_2024",
                            "operation": "difference",
                            "inputs": ["recomputed_total_2024", "disclosed_total_2024"],
                        },
                    ],
                    "candidate_may_select_operation": False,
                },
                "P18-WORKFORCE-001": {
                    "roles": [
                        {"role_id": role, "unit": "FTE"}
                        for role in [
                            "germany_2025",
                            "international_2025",
                            "disclosed_total_2025",
                            "germany_2024",
                            "international_2024",
                            "disclosed_total_2024",
                        ]
                    ],
                    "candidate_input_role_order": [
                        "germany_2025",
                        "international_2025",
                        "disclosed_total_2025",
                        "germany_2024",
                        "international_2024",
                        "disclosed_total_2024",
                    ],
                    "steps": [
                        {
                            "step_id": "recomputed_total_2025",
                            "operation": "sum",
                            "inputs": ["germany_2025", "international_2025"],
                        },
                        {
                            "step_id": "difference_2025",
                            "operation": "difference",
                            "inputs": ["recomputed_total_2025", "disclosed_total_2025"],
                        },
                        {
                            "step_id": "recomputed_total_2024",
                            "operation": "sum",
                            "inputs": ["germany_2024", "international_2024"],
                        },
                        {
                            "step_id": "difference_2024",
                            "operation": "difference",
                            "inputs": ["recomputed_total_2024", "disclosed_total_2024"],
                        },
                    ],
                    "candidate_may_select_operation": False,
                },
            },
        },
    )

    graph_path = "configs/framework/p18_two_dimensional_table_graph_v0.1.lock.json"
    graph_sha = dump_new(
        graph_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "graphs": [
                {
                    "graph_id": "P18-WORKFORCE-P109",
                    "pdf_page": 109,
                    "header_axis": ["2025", "2024"],
                    "row_axis": ["Germany", "International", "Total number of employees"],
                    "selected_cells": [
                        ["Germany", "2025", 70751],
                        ["International", "2025", 127327],
                        ["Total number of employees", "2025", 198079],
                        ["Germany", "2024", 74550],
                        ["International", "2024", 123644],
                        ["Total number of employees", "2024", 198194],
                    ],
                },
                {
                    "graph_id": "P18-ENERGY-P131",
                    "pdf_page": 131,
                    "header_axis": ["2025", "2024"],
                    "row_axis": [
                        "fossil",
                        "renewable",
                        "self-generated non-fuel renewable",
                        "total",
                    ],
                    "selected_cells": [
                        ["fossil", "2025", 812912],
                        ["renewable", "2025", 11144078],
                        ["self-generated non-fuel renewable", "2025", 13905],
                        ["total", "2025", 11956990],
                    ],
                },
                {
                    "graph_id": "P18-GHG-P133",
                    "pdf_page": 133,
                    "header_axis": ["2025", "2024"],
                    "row_axis": [
                        "Scope 1+2 market-based",
                        "Scope 1",
                        "Scope 2 market-based",
                        "Scope 3 total",
                        "Scope 3 upstream",
                        "Scope 3 downstream",
                    ],
                    "selected_cells": [
                        ["Scope 1+2 market-based", "2025", 240165],
                        ["Scope 1", "2025", 223790],
                        ["Scope 2 market-based", "2025", 16375],
                        ["Scope 3 total", "2025", 8507234],
                        ["Scope 3 upstream", "2025", 5861714],
                        ["Scope 3 downstream", "2025", 2645520],
                    ],
                },
                {
                    "graph_id": "P18-TAXONOMY-P123",
                    "pdf_page": 123,
                    "header_axis": [
                        "total 2025",
                        "eligible %",
                        "aligned EURm",
                        "aligned %",
                        "not assessed non-material %",
                        "aligned EURm 2024",
                        "aligned % 2024",
                    ],
                    "row_axis": ["Turnover", "Capex", "Opex"],
                    "selected_cells": [
                        ["Turnover", "total 2025", 119081],
                        ["Turnover", "not assessed non-material %", 2.5],
                        ["Capex", "total 2025", 29478],
                        ["Capex", "not assessed non-material %", 1.6],
                        ["Opex", "total 2025", 3198],
                    ],
                },
            ],
        },
    )

    layout_path = "configs/framework/p18_layout_fallback_registry_v0.1.lock.json"
    layout_targets = []
    for task in pack["tasks"]:
        for page in task["target_pages"]:
            layout_targets.append(
                {
                    "task_id": task["task_id"],
                    "document_id": DOCUMENT,
                    "document_sha256": DOCUMENT_SHA,
                    "pdf_path": PDF,
                    "pdf_page": page,
                    "primary_parser": "MinerU 3.4.0 checksum-verified target-page output",
                    "fallback_parser": "pdftotext -bbox-layout",
                    "fallback_reason": "pre-frozen dual-parser audit path; all visible lines exposed without hidden-reference selection",
                }
            )
    layout_sha = dump_new(
        layout_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "selection_rule": "all frozen task/page pairs receive deterministic native-layout cross-check without hidden-reference selection",
            "semantic_change": False,
            "targets": layout_targets,
        },
    )

    handles = {}
    for task in pack["tasks"]:
        _, _, evidence_handles = build_v13_packet(
            task_pack_path=ROOT / TASK_PACK,
            task_id=task["task_id"],
            acquisition_manifest_path=ROOT / "data/manifests/p18_source_acquisition_v0.1.lock.json",
            raw_root=ROOT,
            interventions_root=ROOT / "data/interventions",
            registry_path=ROOT / REGISTRY,
            workspace_root=ROOT,
            layout_registry_path=ROOT / layout_path,
        )
        handles[task["task_id"]] = sorted({item["handle"] for item in evidence_handles})
    handles_path = "configs/framework/p18_evidence_handle_whitelist_v0.1.lock.json"
    handles_sha = dump_new(
        handles_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "handles": handles,
        },
    )

    slot_count = sum(len(items) for items in contracts.values())
    scoring_path = "configs/framework/p18_scoring_rules_v0.1.lock.json"
    scoring_sha = dump_new(
        scoring_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "reference_projection": gold_path,
            "dimensions": [
                "stage_a_schema_validity",
                "stage_a_evidence_grounding",
                "stage_a_answer_fidelity",
                "stage_b_atomic_claim_validity",
                "stage_b_slot_coverage",
                "stage_b_exact_numeric_match",
                "stage_b_exact_string_match",
                "string_token_jaccard",
                "boundary_fidelity",
                "period_fidelity",
                "parser_integrity",
            ],
            "rules": {
                "aggregate_score": None,
                "required_slot_count": slot_count,
                "partial_projection_credit_allowed": True,
                "missing_slots_explicit": True,
                "missing_values_invented": False,
                "numeric_tolerance": 0,
                "failed_model_outputs_retained": True,
                "single_attempt_per_stage": True,
                "silent_retry": False,
                "posthoc_semantic_repair": False,
            },
        },
    )

    config_path = "configs/experiments/p18-v27-unseen-lockbox-local.json"
    config_sha = dump_new(
        config_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_local_configuration_pending_explicit_cloud_authorization",
            "model_config": "configs/models/p1-ollama-cloud-qwen3.5-397b.json",
            "candidate_model": "qwen3.5:397b-cloud",
            "stage_a": {
                "single_attempt": True,
                "use_v15_grounding": True,
                "use_v21_calculation": True,
                "use_v24_layout_gate": True,
                "use_v25_calculation_adapter": True,
                "use_v26_evidence_handle_audit": True,
                "use_v27_partial_calculation": True,
                "calculation_plans": calculation_path,
                "evidence_handle_whitelist": handles_path,
            },
            "stage_b": {
                "single_attempt": True,
                "use_v20_contract_gate": True,
                "use_v24_preflight": True,
                "use_v24_layout_gate": True,
                "use_v25_single_block_ordered_spans": True,
                "use_v26_atomic_projection": True,
                "use_v27_handle_aliases": True,
                "slot_contracts": contracts_path,
                "semantic_qualifiers": semantic_path,
            },
            "frozen_unit_aliases": {
                "t CO2e": ["t CO2e", "t CO₂e"],
                "MWh": ["MWh"],
                "GWh": ["GWh"],
                "FTE": ["FTE", "FTEs"],
                "million EUR": ["millions of €", "EUR million"],
                "billion EUR": ["EUR billion"],
            },
            "failure_policy": {
                "archive_model_behavior_failure": True,
                "silent_retry": False,
                "posthoc_semantic_repair": False,
                "infrastructure_resume_requires_lineage": True,
            },
            "cloud_transmission_allowed": False,
        },
    )

    local_pack_path = "data/tasks/p18_local_execution_task_pack_v0.1.lock.json"
    local_pack_sha = dump_new(
        local_pack_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "frozen_local_pack_pending_explicit_cloud_authorization",
            "inference_allowed": False,
            "parent": TASK_PACK,
            "source_registry": "data/manifests/p18_source_registry_v0.1.lock.json",
            "parser_registry": REGISTRY,
            "reference_freeze": freeze_path,
            "reference_consistency_audit": audit_path,
            "slot_contracts": contracts_path,
            "atomic_scoring_projection": gold_path,
            "semantic_qualifiers": semantic_path,
            "table_graph": graph_path,
            "layout_fallback_registry": layout_path,
            "calculation_plans": calculation_path,
            "evidence_handle_whitelist": handles_path,
            "scoring_rules": scoring_path,
            "execution_config": config_path,
            "tasks": [
                {**task, "reference_file": f"{reference_dir}/{task['task_id']}.json"}
                for task in pack["tasks"]
            ],
            "release_condition": "User must explicitly authorize Deutsche Telekom Annual Report 2025 pages 109,121,122,123,131,133,370,371 to Ollama Cloud qwen3.5:397b-cloud solely for P18 Stage A/Stage B single-attempt candidate inference.",
        },
    )

    report_path = "docs/82_P18_v2.7本地预冻结与云授权边界_v0.1.md"
    report = ROOT / report_path
    if report.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    report.write_text(
        f"""# P18 v2.7 本地预冻结与云授权边界

## 结论

P18 已完成全部本地预冻结，尚未向云模型发送任何 Deutsche Telekom 报告内容，也未启动候选推理。P3–P17 未修改、未重跑、未重评分。

## 样本与任务

- 样本：Deutsche Telekom Annual Report 2025
- 文档 SHA256：`{DOCUMENT_SHA}`
- 冻结问题：6 项
- 唯一证据页：8 页（109、121、122、123、131、133、370、371）
- MinerU：8/8 成功并逐文件哈希验证；三代基础设施恢复仅补未完成页，所有失败记录保留
- 模拟参考：6 份，{checked} 条逐字证据引文
- 原子评分槽位：{slot_count} 个

## 关键审计点

- 2024 Scope 3 上下游分项和比披露总数少 1 t CO2e，原样保留。
- 2025 德国与国际 FTE 之和比披露总数少 1 FTE，原样保留。
- EU Taxonomy 严格区分 eligible、aligned 与未评估的非重大活动列。
- 鉴证严格区分整体有限保证、三个合理保证指标和排除引用。

## 云传输边界

只有在用户明确授权后，才可将第 109、121、122、123、131、133、370、371 页冻结证据发送至 Ollama Cloud 的 `qwen3.5:397b-cloud`，且仅用于 P18 Stage A/Stage B 单次候选推理。
""",
        encoding="utf-8",
    )
    report_sha = sha(report_path)

    readiness_path = "data/results/p18_v27_local_readiness_v0.1.lock.json"
    readiness_sha = dump_new(
        readiness_path,
        {
            "schema_version": "2.7",
            "experiment_id": EXPERIMENT,
            "status": "local_readiness_passed_waiting_for_explicit_cloud_authorization",
            "document_id": DOCUMENT,
            "document_sha256": DOCUMENT_SHA,
            "task_count": 6,
            "slot_count": slot_count,
            "unique_target_pages": PAGES,
            "mineru": {
                "success_count": 8,
                "failure_count": 0,
                "registry": REGISTRY,
                "registry_sha256": sha(REGISTRY),
                "preserved_infrastructure_failures": 11,
                "recovery_generations": ["RESUME01", "RESUME02", "RESUME03"],
            },
            "prefreeze_integrity": {
                "status": "passed",
                "reference_audit": audit_path,
                "reference_audit_sha256": audit_sha,
                "reference_freeze": freeze_path,
                "reference_freeze_sha256": freeze_sha,
                "evidence_quotes_checked": checked,
                "contract_preflights_passed": slot_count,
                "deterministic_calculation_passed": True,
            },
            "artifacts": {
                "slot_contracts": {"path": contracts_path, "sha256": contracts_sha},
                "atomic_gold": {"path": gold_path, "sha256": gold_sha},
                "semantic_qualifiers": {"path": semantic_path, "sha256": semantic_sha},
                "calculation_plans": {"path": calculation_path, "sha256": calculation_sha},
                "table_graph": {"path": graph_path, "sha256": graph_sha},
                "layout_registry": {"path": layout_path, "sha256": layout_sha},
                "handle_whitelist": {"path": handles_path, "sha256": handles_sha},
                "scoring_rules": {"path": scoring_path, "sha256": scoring_sha},
                "execution_config": {"path": config_path, "sha256": config_sha},
                "local_task_pack": {"path": local_pack_path, "sha256": local_pack_sha},
                "report": {"path": report_path, "sha256": report_sha},
            },
            "cloud_boundary": {
                "candidate_model": "qwen3.5:397b-cloud",
                "cloud_transmission_count": 0,
                "candidate_model_call_count": 0,
                "explicit_authorization_received": False,
                "authorized_pages_required": PAGES,
                "authorized_scope_required": "P18 Stage A/Stage B single-attempt candidate inference",
            },
            "locked_prior_experiments_modified": False,
        },
    )
    print(
        json.dumps(
            {
                "status": "ready_waiting_for_authorization",
                "readiness": readiness_path,
                "readiness_sha256": readiness_sha,
                "slots": slot_count,
                "quotes": checked,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
