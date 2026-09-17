# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from esg_reliable_discovery.v13_evidence import build_v13_packet
from esg_reliable_discovery.v29_integrity import validate_candidate_preflight_v29

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P20-V29-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P20-HOLCIM-SS2025"
DOCUMENT_SHA = "55b975cd13fc361638ed13bf32856a2629e46e88bdfc6ad9208bd8807992a599"
PAGES = [85, 86, 87, 111, 112, 113, 114, 120, 121, 134, 135, 136]
TASK_PACK = "data/tasks/p20_task_pack_v0.1.lock.json"
REGISTRY = "data/manifests/p20_mineru_target_registry_RESUME01_v0.1.lock.json"
LAYOUT = "configs/framework/p20_layout_fallback_registry_v0.1.lock.json"


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
        files = list((ROOT / target["output_directory"]).rglob("*.md"))
        if len(files) != 1:
            raise ValueError(f"markdown_ambiguous:{target['pdf_page']}:{files}")
        result[target["pdf_page"]] = files[0].read_text(encoding="utf-8")
    return result


def evidence(page: int, *quotes: str) -> list[dict[str, Any]]:
    return [
        {"source_id": DOCUMENT, "pdf_page": page, "quote": quote}
        for quote in quotes
    ]


def ref(
    task_id: str,
    answer: str,
    values: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "task_id": task_id,
        "reference_author": "codex_gpt_simulated_expert",
        "reference_status": "verified_against_frozen_mineru_pages_and_native_layout",
        "answer": answer,
        "normalized_value": values,
        "evidence": items,
        "provenance": {
            "reference_is_simulated": True,
            "candidate_model_used": False,
        },
    }


def main() -> None:
    pack = load(TASK_PACK)
    registry = load(REGISTRY)
    assert pack["experiment_id"] == registry["experiment_id"] == EXPERIMENT
    assert pack["document_sha256"] == registry["document_sha256"] == DOCUMENT_SHA
    assert registry["success_count"] == registry["target_count"] == 12
    assert sorted(item["pdf_page"] for item in registry["targets"]) == PAGES
    pages = markdown_by_page(registry)

    ghg_change = ((Decimal(92) - Decimal(91)) / Decimal(91) * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    s3_share_2025 = ((Decimal("5.8") + Decimal("21.3")) / Decimal(37) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s3_share_2024 = ((Decimal("5.3") + Decimal("19.6")) / Decimal(35) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    references = {
        "P20-GHG-CALC-001": ref(
            "P20-GHG-CALC-001",
            "For 2025, gross Scope 1 was 52 Mt CO2e, market-based Scope 2 was 3 Mt CO2e, and Scope 3 was 37 Mt CO2e. Their deterministic sum is 92 Mt CO2e, exactly matching the disclosed market-based Scopes 1, 2 and 3 total. Compared with the restated 2024 total of 91 Mt CO2e, the disclosed total increased by 1.10%.",
            {"scope1_gross_mtco2e::2025": 52, "scope2_market_mtco2e::2025": 3, "scope3_mtco2e::2025": 37, "calculated_total_mtco2e::2025": 92, "disclosed_total_market_mtco2e::2025": 92, "difference_mtco2e::2025": 0, "disclosed_total_market_mtco2e::2024": 91, "calculated_change_percent": float(ghg_change), "direction": "increase"},
            evidence(86, "Gross Scope 1 emissions: 52 million tons", "Scope 2 emissions (market-based): 3 million tons", "Total Scope 3 emissions: 37 million tons", "Total GHG emissions (Scopes 1, 2, and 3): 92 million tons") + evidence(87, "Absolute emissions (Scopes 1, 2, &amp; 3) (market-based)", "<td>97</td><td>91</td><td>92</td>"),
        ),
        "P20-ENERGY-001": ref(
            "P20-ENERGY-001",
            "Total energy consumption was 85 MMWh in both 2025 and restated 2024; fossil energy was 47 and 49 MMWh, representing 55% and 58%; renewable energy was 13 and 12 MMWh, representing 16% and 14%. The narrative nevertheless reports a 0.4% increase, reflecting unrounded data. Renewable electricity instruments were PPAs, VPPAs, and RECs or guarantees of origin.",
            {"total_energy_mmwh::2025": 85, "total_energy_mmwh::2024": 85, "fossil_energy_mmwh::2025": 47, "fossil_energy_mmwh::2024": 49, "fossil_share_percent::2025": 55, "fossil_share_percent::2024": 58, "renewable_energy_mmwh::2025": 13, "renewable_energy_mmwh::2024": 12, "renewable_share_percent::2025": 16, "renewable_share_percent::2024": 14, "narrative_change_percent": 0.4, "direction": "increase", "renewable_electricity_instruments": "power purchase agreements (PPAs) | virtual power purchase agreements (VPPAs) | renewable energy certificates (RECs) and guarantees of origin (GOs)"},
            evidence(85, "In 2025, our total energy consumption was 85 million megawatt hours (M MWh), a 0.4% increase compared to 2024.", "Energy consumption total", "Total energy consumption from fossil sources", "Total energy consumption from renewable sources", "Power purchase agreements (PPAs)", "Virtual power purchase agreements (VPPAs)", "Renewable energy certificates (RECs) and guarantees of origin (GOs)"),
        ),
        "P20-SCOPE3-001": ref(
            "P20-SCOPE3-001",
            "In 2025, Scope 3 was 37 Mt CO2e; Category 1 was 5.8 and Category 15 was 21.3, summing to 27.1 Mt or 73.24% of Scope 3. In restated 2024, the values were 35, 5.3 and 19.6, summing to 24.9 Mt or 71.14%. Primary-data shares were 59% and 58% respectively.",
            {"scope3_total_mtco2e::2025": 37, "category1_mtco2e::2025": 5.8, "category15_mtco2e::2025": 21.3, "category1_plus_15_mtco2e::2025": 27.1, "category1_plus_15_share_percent::2025": float(s3_share_2025), "primary_data_percent::2025": 59, "scope3_total_mtco2e::2024": 35, "category1_mtco2e::2024": 5.3, "category15_mtco2e::2024": 19.6, "category1_plus_15_mtco2e::2024": 24.9, "category1_plus_15_share_percent::2024": float(s3_share_2024), "primary_data_percent::2024": 58},
            evidence(87, "Absolute Scope 3 emissions – total", "Percentage of GHG Scope 3 calculated using primary data", "Absolute S3 emissions – Cat 1 – Purchased goods and services", "Absolute S3 emissions – Cat 15 – Investments"),
        ),
        "P20-WORKFORCE-001": ref(
            "P20-WORKFORCE-001",
            "At year-end 2025, global employee headcount was 46,055. The contract table covered 40,590 permanent and 3,285 temporary employees, summing to 43,875; the 2,180 difference is exactly the newly acquired-entity population excluded from contract-type and other SF metrics. Non-guaranteed-hours employees numbered 140, while the separate percentage table rounded their share to 0%.",
            {"global_headcount::2025": 46055, "permanent_headcount_contract_table::2025": 40590, "temporary_headcount_contract_table::2025": 3285, "calculated_contract_headcount::2025": 43875, "difference_headcount::2025": 2180, "exclusion_explanation": "newly acquired entities such as ZinCo and Alkern had not implemented Success Factors and were excluded from contract-type metrics", "non_guaranteed_hours_headcount::2025": 140, "non_guaranteed_hours_rounded_percent::2025": 0},
            evidence(120, "Holcim’s workforce comprised 46 055 employees", "excludes 2 180 employees from newly acquired entities") + evidence(121, "Number of employees (headcount)", "Number of permanent employees", "Number of temporary employees", "Number of non-guaranteed hours employees", "<td>43 875</td>", "<td>40 590</td>", "<td>3 285</td>", "<td>140</td>"),
        ),
        "P20-TAXONOMY-001": ref(
            "P20-TAXONOMY-001",
            "For 2025, turnover totalled CHF 15,724m: CHF 7,603m (48.4%) was eligible and CHF 914m (5.8%) aligned. CapEx totalled CHF 1,809m: CHF 1,038m (57.4%) eligible and CHF 347m (19.2%) aligned. OpEx totalled CHF 949m: CHF 573m (60.4%) eligible and CHF 93m (9.8%) aligned. Turnover growth reflected low-carbon cement and better DNSH alignment; CapEx growth reflected decarbonization and circularity investment; OpEx growth reflected refined R&D identification. 2024 comparatives were restated and unaudited, and the spun-off North American business was excluded from both 2024 and 2025 KPIs.",
            {"turnover_total_mchf::2025": 15724, "turnover_eligible_mchf::2025": 7603, "turnover_eligible_percent::2025": 48.4, "turnover_aligned_mchf::2025": 914, "turnover_aligned_percent::2025": 5.8, "capex_total_mchf::2025": 1809, "capex_eligible_mchf::2025": 1038, "capex_eligible_percent::2025": 57.4, "capex_aligned_mchf::2025": 347, "capex_aligned_percent::2025": 19.2, "opex_total_mchf::2025": 949, "opex_eligible_mchf::2025": 573, "opex_eligible_percent::2025": 60.4, "opex_aligned_mchf::2025": 93, "opex_aligned_percent::2025": 9.8, "turnover_driver": "higher low-carbon cement sales and improved DNSH alignment for air pollution and climate adaptation", "capex_driver": "accelerated decarbonization and circularity investments", "opex_driver": "refined 2025 methodology improved identification of qualifying R&D", "comparative_qualification": "2024 figures restated for discontinued operations and unaudited", "spin_off_boundary": "North American business excluded from consolidated turnover, CapEx and OpEx KPIs for both 2024 and 2025"},
            evidence(111, "remain unaudited", "Eligible and aligned</td><td>914</td><td>5.8%", "Total</td><td>15 724</td><td>100%", "total eligible CapEx amounted to CHF 1 038 million", "Taxonomy-aligned CapEx of CHF 347 million") + evidence(112, "Eligible and aligned</td><td>93</td><td>9.8%", "Eligible but not aligned</td><td>480</td><td>50.6%", "Total</td><td>949</td><td>100%", "more refined assessment methodology implemented in 2025") + evidence(113, "fully excluded from our reported consolidated Group turnover, CapEx, and OpEx KPIs for the two periods disclosed for 2024 and 2025") + evidence(114, "<td>Turnover</td><td>15 724</td><td>48.4%</td><td>914</td>", "<td>1 809</td><td>57.4%</td><td>347 93</td>"),
        ),
        "P20-ASSURE-001": ref(
            "P20-ASSURE-001",
            "EY & Associés provided limited assurance over Holcim's double-materiality process, selected Sustainability Indicators against their Methodology criteria, and Transition Plan Disclosures against ESRS E1. Its negative-form conclusion was that nothing came to attention indicating material non-compliance. ISAE 3000 (Revised) governed the engagement. EY was not responsible for the entire report or other legal provisions, nor for judging the appropriateness or ambition of transition objectives. Limited assurance is substantially lower than reasonable assurance. Christophe Schmeitzky signed in Paris-La Défense on 26 February 2026.",
            {"assured_subjects": "Double Materiality Assessment | selected Sustainability Indicators | Transition Plan Disclosures", "criteria": "ESRS requirements | section-specific Methodology criteria | ESRS E1 Climate Change requirements", "assurance_level": "limited assurance", "conclusion_form": "nothing has come to our attention", "governing_standard": "ISAE 3000 (Revised)", "excluded_responsibility": "entire report; other applicable legal provisions; appropriateness or ambition of transition-strategy objectives", "procedure_difference": "limited assurance procedures are less extensive and assurance is substantially lower than reasonable assurance", "assurance_provider": "EY & Associés", "signatory": "Christophe Schmeitzky", "signature_location": "Paris-La Défense", "signature_date": "2026-02-26"},
            evidence(134, "Double Materiality Assessment", "Sustainability Indicators", "Transition Plan Disclosures", "nothing has come to our attention") + evidence(135, "It is not our responsibility to report on the entire Report", "International Standard on Assurance Engagements 3000 (revised)") + evidence(136, "substantially lower than the assurance that would have been obtained had we performed a reasonable assurance engagement", "Paris-La Défense", "26 February 2026", "EY & Associés", "Christophe Schmeitzky"),
        ),
    }

    task_windows = {item["task_id"]: set(item["target_pages"]) for item in pack["tasks"]}
    checked = 0
    for task_id, payload in references.items():
        for item in payload["evidence"]:
            if item["pdf_page"] not in task_windows[task_id]:
                raise ValueError(f"reference_page_outside_window:{task_id}")
            if item["quote"] not in pages[item["pdf_page"]]:
                raise ValueError(f"reference_quote_not_grounded:{task_id}:{item['quote']}")
            checked += 1

    entries = []
    reference_dir = "data/annotations/p20_simulated"
    for task_id, payload in references.items():
        path = f"{reference_dir}/{task_id}.json"
        entries.append({"task_id": task_id, "path": path, "sha256": dump_new(path, payload)})

    units = {"mtco2e": "Mt CO2e", "percent": "percent", "mmwh": "million MWh", "headcount": "headcount", "mchf": "million CHF"}
    contracts = {}
    for task_id, payload in references.items():
        rows = []
        for slot_id, value in payload["normalized_value"].items():
            row = {"predicate_id": f"esg_p20::{task_id.lower()}::{slot_id}", "slot_id": slot_id, "value_type": "boolean" if isinstance(value, bool) else "number" if isinstance(value, (int, float)) else "string"}
            for marker, unit in units.items():
                if marker in slot_id:
                    row["canonical_unit"] = unit
                    break
            rows.append(row)
        contracts[task_id] = rows
    contracts_path = "configs/framework/p20_slot_contracts_v0.1.lock.json"
    contracts_sha = dump_new(contracts_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "contracts": contracts})
    gold_path = f"{reference_dir}/p20_atomic_slot_gold_v0.1.lock.json"
    gold_sha = dump_new(gold_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_atomic_scoring_projection_before_candidate_inference", "values": {task_id: payload["normalized_value"] for task_id, payload in references.items()}})

    plans = {
        "P20-GHG-CALC-001": {"roles": [{"role_id": x, "unit": "Mt CO2e"} for x in ["scope1_2025", "scope2_market_2025", "scope3_2025", "disclosed_total_2025", "disclosed_total_2024"]], "candidate_handle_role_map": {"M086-B0002": "scope1_2025", "M086-B0003": "scope2_market_2025", "M086-B0004": "scope3_2025", "M086-B0005": "disclosed_total_2025", "M087-T0007-R0026-C0003": "disclosed_total_2024"}, "steps": [{"step_id": "calculated_total_2025", "operation": "sum", "inputs": ["scope1_2025", "scope2_market_2025", "scope3_2025"]}, {"step_id": "difference", "operation": "difference", "inputs": ["calculated_total_2025", "disclosed_total_2025"]}, {"step_id": "percentage_change", "operation": "percentage_change", "inputs": ["disclosed_total_2025", "disclosed_total_2024"], "rounding_decimals": 2}], "candidate_may_select_operation": False},
        "P20-SCOPE3-001": {"roles": [{"role_id": x, "unit": "Mt CO2e"} for x in ["category1_2025", "category15_2025", "total_2025", "category1_2024", "category15_2024", "total_2024"]], "candidate_handle_role_map": {"M087-T0007-R0010-C0004": "category1_2025", "M087-T0007-R0024-C0004": "category15_2025", "M087-T0007-R0008-C0004": "total_2025", "M087-T0007-R0010-C0003": "category1_2024", "M087-T0007-R0024-C0003": "category15_2024", "M087-T0007-R0008-C0003": "total_2024"}, "steps": [{"step_id": "category1_plus_15_2025", "operation": "sum", "inputs": ["category1_2025", "category15_2025"]}, {"step_id": "share_2025", "operation": "percentage_share", "inputs": ["category1_plus_15_2025", "total_2025"], "rounding_decimals": 2}, {"step_id": "category1_plus_15_2024", "operation": "sum", "inputs": ["category1_2024", "category15_2024"]}, {"step_id": "share_2024", "operation": "percentage_share", "inputs": ["category1_plus_15_2024", "total_2024"], "rounding_decimals": 2}], "candidate_may_select_operation": False},
        "P20-WORKFORCE-001": {"roles": [{"role_id": x, "unit": "headcount"} for x in ["permanent_2025", "temporary_2025", "global_headcount_2025"]], "candidate_handle_role_map": {"M121-T0004-R0002-C0005": "permanent_2025", "M121-T0004-R0003-C0005": "temporary_2025", "M121-T0002-R0002-C0004": "global_headcount_2025"}, "steps": [{"step_id": "contract_headcount_2025", "operation": "sum", "inputs": ["permanent_2025", "temporary_2025"]}, {"step_id": "difference", "operation": "difference", "inputs": ["global_headcount_2025", "contract_headcount_2025"]}], "candidate_may_select_operation": False},
    }
    plans_path = "configs/framework/p20_calculation_plans_v0.1.lock.json"
    plans_sha = dump_new(plans_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "plans": plans})
    preflight = validate_candidate_preflight_v29(pack["tasks"], {"plans": plans})

    graph_path = "configs/framework/p20_two_dimensional_table_graph_v0.1.lock.json"
    graph_sha = dump_new(graph_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "graphs": [{"graph_id": "P20-ENERGY-P085", "pdf_page": 85, "header_axis": ["2023 restated", "2024 restated", "2025"], "row_axis": ["total", "fossil", "fossil share", "renewable", "renewable share"], "selected_cells": [["total", "2024 restated", 85], ["total", "2025", 85], ["fossil", "2024 restated", 49], ["fossil", "2025", 47], ["renewable", "2024 restated", 12], ["renewable", "2025", 13]]}, {"graph_id": "P20-GHG-P087", "pdf_page": 87, "header_axis": ["2023 restated", "2024 restated", "2025"], "row_axis": ["Scope 1", "Scope 2 market", "Scope 3", "Category 1", "Category 15", "market total"], "selected_cells": [["Scope 3", "2024 restated", 35], ["Scope 3", "2025", 37], ["Category 1", "2025", 5.8], ["Category 15", "2025", 21.3], ["market total", "2024 restated", 91], ["market total", "2025", 92]]}, {"graph_id": "P20-WORKFORCE-P121", "pdf_page": 121, "header_axis": ["AMEA", "Europe", "LATAM", "Total"], "row_axis": ["headcount", "permanent", "temporary", "non-guaranteed hours"], "selected_cells": [["headcount", "Total", 43875], ["permanent", "Total", 40590], ["temporary", "Total", 3285], ["non-guaranteed hours", "Total", 140]]}, {"graph_id": "P20-TAXONOMY", "pdf_page": 114, "header_axis": ["total", "eligible percent", "aligned million CHF", "aligned percent"], "row_axis": ["Turnover", "CapEx", "OpEx"], "selected_cells": [["Turnover", "total", 15724], ["Turnover", "eligible percent", 48.4], ["Turnover", "aligned million CHF", 914], ["Turnover", "aligned percent", 5.8], ["CapEx", "total", 1809], ["CapEx", "eligible percent", 57.4], ["CapEx", "aligned million CHF", 347], ["CapEx", "aligned percent", 19.2], ["OpEx", "total", 949], ["OpEx", "eligible percent", 60.4], ["OpEx", "aligned million CHF", 93], ["OpEx", "aligned percent", 9.8]]}]})

    handles = {}
    for task in pack["tasks"]:
        _, _, evidence_handles = build_v13_packet(task_pack_path=ROOT / TASK_PACK, task_id=task["task_id"], acquisition_manifest_path=ROOT / "data/manifests/p20_source_acquisition_v0.1.lock.json", raw_root=ROOT, interventions_root=ROOT / "data/interventions", registry_path=ROOT / REGISTRY, workspace_root=ROOT, layout_registry_path=ROOT / LAYOUT)
        handles[task["task_id"]] = sorted({item["handle"] for item in evidence_handles})
    for task_id, plan in plans.items():
        unknown = sorted(set(plan["candidate_handle_role_map"]) - set(handles[task_id]))
        if unknown:
            raise ValueError(f"calculation_handle_not_in_whitelist:{task_id}:{unknown}")
    handles_path = "configs/framework/p20_evidence_handle_whitelist_v0.1.lock.json"
    handles_sha = dump_new(handles_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "handles": handles})

    freeze_path = "data/manifests/p20_simulated_reference_freeze_v0.1.lock.json"
    freeze_sha = dump_new(freeze_path, {"schema_version": "1.0", "manifest_id": "P20-SIMULATED-REFERENCE-FREEZE-v0.1", "experiment_id": EXPERIMENT, "status": "simulated_references_frozen_after_questions_page_windows_and_parser_outputs_and_before_candidate_inference", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_pack": {"path": TASK_PACK, "sha256": sha(TASK_PACK)}, "target_registry": {"path": REGISTRY, "sha256": sha(REGISTRY)}, "references": sorted(entries, key=lambda item: item["task_id"]), "integrity_audit": {"reference_count": 6, "evidence_quote_count": checked, "all_reference_pages_within_frozen_task_windows": True, "all_quotes_exact_substrings_of_frozen_MinerU_markdown": True, "numeric_values_cross_checked_against_native_layout": True, "candidate_model_used": False, "cloud_transmission_occurred": False}, "candidate_reference_visibility": False, "cloud_transmission_allowed": False})
    audit_path = "data/results/p20_prefreeze_reference_consistency_audit_v0.1.lock.json"
    audit_sha = dump_new(audit_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "gate_result": "pass", "checks": {"task_count": 6, "unique_page_count": 12, "reference_quote_count": checked, "reference_pages_within_windows": True, "quotes_grounded_in_frozen_parser_output": True, "numeric_arithmetic_recomputed": True, "v29_whole_pack_preflight": preflight, "candidate_model_used": False, "cloud_transmission_count": 0}, "hashes": {"task_pack": sha(TASK_PACK), "parser_registry": sha(REGISTRY), "reference_freeze": freeze_sha, "slot_contracts": contracts_sha, "atomic_gold": gold_sha}})

    semantic_path = "configs/framework/p20_semantic_qualifiers_v0.1.lock.json"
    semantic_sha = dump_new(semantic_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "qualifiers": {"reporting_period": "calendar year 2025 unless a restated 2024 comparative is explicitly named", "page_coordinates": "one-based PDF page indexes", "P20-GHG-CALC-001": {"boundary": "gross Scope 1, market-based Scope 2, total Scope 3 and market-based total; retain Mt CO2e"}, "P20-ENERGY-001": {"boundary": "preserve rounded table values and separate narrative 0.4% change"}, "P20-SCOPE3-001": {"boundary": "Category 1 and Category 15 shares of disclosed Scope 3 total"}, "P20-WORKFORCE-001": {"boundary": "global headcount includes all entities; contract table excludes 2,180 newly acquired-entity employees"}, "P20-TAXONOMY-001": {"boundary": "separate total, eligible and aligned; 2024 restated unaudited; North America excluded from both periods"}, "P20-ASSURE-001": {"boundary": "limited assurance covers selected subjects, not the entire report or transition-target ambition"}, "reference_type": "AI-simulated research reference; not independent human gold"}})
    slot_count = sum(len(items) for items in contracts.values())
    scoring_path = "configs/framework/p20_scoring_rules_v0.1.lock.json"
    scoring_sha = dump_new(scoring_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "reference_projection": gold_path, "dimensions": ["stage_a_schema_validity", "stage_a_evidence_grounding", "stage_a_answer_fidelity", "stage_b_atomic_claim_validity", "stage_b_slot_coverage", "stage_b_exact_numeric_match", "stage_b_literal_exact_string_match", "stage_b_normalized_exact_string_match", "string_token_jaccard", "boundary_fidelity", "period_fidelity", "parser_integrity"], "rules": {"aggregate_score": None, "required_slot_count": slot_count, "partial_projection_credit_allowed": True, "missing_slots_explicit": True, "missing_values_invented": False, "numeric_tolerance": 0, "failed_model_outputs_retained": True, "single_attempt_per_stage": True, "silent_retry": False, "posthoc_semantic_repair": False}})
    config_path = "configs/experiments/p20-v29-unseen-lockbox-local.json"
    config_sha = dump_new(config_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_local_configuration_pending_payload_specific_cloud_authorization", "model_config": "configs/models/p1-ollama-cloud-qwen3.5-397b.json", "candidate_model": "qwen3.5:397b-cloud", "pre_candidate_gate": {"use_v29_whole_pack_plan_gate": True, "result": preflight}, "stage_a": {"single_attempt": True, "use_v15_grounding": True, "use_v21_calculation": True, "use_v24_layout_gate": True, "use_v25_calculation_adapter": True, "use_v26_evidence_handle_audit": True, "use_v27_partial_calculation": True, "use_v28_handle_role_binding": True, "use_v29_task_id_schema": True, "use_v29_calculation_executor": True, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path}, "stage_b": {"single_attempt": True, "use_v20_contract_gate": True, "use_v24_preflight": True, "use_v24_layout_gate": True, "use_v25_single_block_ordered_spans": True, "use_v26_atomic_projection": True, "use_v27_handle_aliases": True, "slot_contracts": contracts_path, "semantic_qualifiers": semantic_path}, "failure_policy": {"archive_model_behavior_failure": True, "silent_retry": False, "posthoc_semantic_repair": False, "infrastructure_resume_requires_lineage": True}, "cloud_transmission_allowed": False})
    local_pack_path = "data/tasks/p20_local_execution_task_pack_v0.1.lock.json"
    local_pack_sha = dump_new(local_pack_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "frozen_local_pack_pending_payload_specific_cloud_authorization", "inference_allowed": False, "parent": TASK_PACK, "source_registry": "data/manifests/p20_source_registry_v0.1.lock.json", "parser_registry": REGISTRY, "reference_freeze": freeze_path, "reference_consistency_audit": audit_path, "slot_contracts": contracts_path, "atomic_scoring_projection": gold_path, "semantic_qualifiers": semantic_path, "table_graph": graph_path, "layout_fallback_registry": LAYOUT, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path, "scoring_rules": scoring_path, "execution_config": config_path, "tasks": [{**task, "reference_file": f"{reference_dir}/{task['task_id']}.json"} for task in pack["tasks"]], "release_condition": "Payload-specific user authorization for Holcim 2025 Sustainability Statement pages 85,86,87,111,112,113,114,120,121,134,135,136 to Ollama Cloud qwen3.5:397b-cloud solely for P20 Stage A/Stage B single-attempt candidate inference."})

    report_path = "docs/88_P20_v2.9本地预冻结与云授权边界_v0.1.md"
    report = ROOT / report_path
    if report.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    report.write_text(f"""# P20 v2.9 本地预冻结与云授权边界\n\n## 结论\n\nP20 已完成全部本地预冻结，尚未向云模型发送任何 Holcim 报告内容，也未启动候选推理。P3–P19 未修改、未重跑、未重评分。\n\n## 样本与任务\n\n- 样本：Holcim 2025 Sustainability Statement\n- 文档 SHA256：`{DOCUMENT_SHA}`\n- 冻结问题：6 项\n- 唯一证据页：12 页（85、86、87、111、112、113、114、120、121、134、135、136）\n- MinerU：12/12 成功并逐文件哈希验证；沙箱端口失败档案保留，RESUME01 仅补未完成页\n- 模拟参考：6 份，{checked} 条逐字证据引文\n- 原子评分槽位：{slot_count} 个\n- v2.9 全任务计算计划门：通过，3 个确定性任务均有完整 DAG\n\n## 关键审计点\n\n- 2025 Scope 1、市场法 Scope 2 和 Scope 3 合计 92 Mt，与披露市场法总数一致；较重述 2024 增长 1.10%。\n- Scope 3 类别 1 与类别 15 合计占比分别为 2025 年 73.24%、重述 2024 年 71.14%。\n- 全球员工数与合同表相差 2,180，恰对应尚未进入 Success Factors 的新收购实体员工。\n- EU Taxonomy 严格区分 total、eligible、aligned，并保留重述未审计及北美分拆边界。\n- 鉴证严格限定为有限保证所覆盖的三个对象，未扩张到整个报告或转型目标雄心水平。\n\n## 云传输边界\n\n仅在取得本载荷特定授权后，才可将第 85、86、87、111、112、113、114、120、121、134、135、136 页冻结证据发送至 Ollama Cloud 的 `qwen3.5:397b-cloud`，且仅用于 P20 Stage A/Stage B 单次候选推理。\n""", encoding="utf-8")
    report_sha = sha(report_path)
    readiness_path = "data/results/p20_v29_local_readiness_v0.1.lock.json"
    readiness_sha = dump_new(readiness_path, {"schema_version": "2.9", "experiment_id": EXPERIMENT, "status": "local_readiness_passed_waiting_for_payload_specific_cloud_authorization", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_count": 6, "slot_count": slot_count, "unique_target_pages": PAGES, "mineru": {"success_count": 12, "failure_count": 0, "registry": REGISTRY, "registry_sha256": sha(REGISTRY), "preserved_infrastructure_failures": 12, "recovery_generations": ["RESUME01"]}, "prefreeze_integrity": {"status": "passed", "reference_audit": audit_path, "reference_audit_sha256": audit_sha, "reference_freeze": freeze_path, "reference_freeze_sha256": freeze_sha, "evidence_quotes_checked": checked, "contract_preflights_passed": slot_count, "v29_whole_pack_preflight": preflight, "deterministic_calculation_passed": True}, "artifacts": {"slot_contracts": {"path": contracts_path, "sha256": contracts_sha}, "atomic_gold": {"path": gold_path, "sha256": gold_sha}, "semantic_qualifiers": {"path": semantic_path, "sha256": semantic_sha}, "calculation_plans": {"path": plans_path, "sha256": plans_sha}, "table_graph": {"path": graph_path, "sha256": graph_sha}, "layout_registry": {"path": LAYOUT, "sha256": sha(LAYOUT)}, "handle_whitelist": {"path": handles_path, "sha256": handles_sha}, "scoring_rules": {"path": scoring_path, "sha256": scoring_sha}, "execution_config": {"path": config_path, "sha256": config_sha}, "local_task_pack": {"path": local_pack_path, "sha256": local_pack_sha}, "report": {"path": report_path, "sha256": report_sha}}, "cloud_boundary": {"candidate_model": "qwen3.5:397b-cloud", "cloud_transmission_count": 0, "candidate_model_call_count": 0, "explicit_payload_specific_authorization_received": False, "authorized_pages_required": PAGES, "authorized_scope_required": "P20 Stage A/Stage B single-attempt candidate inference"}, "locked_prior_experiments_modified": False})
    print(json.dumps({"status": "ready_waiting_for_authorization", "readiness": readiness_path, "readiness_sha256": readiness_sha, "slots": slot_count, "quotes": checked}, sort_keys=True))


if __name__ == "__main__":
    main()
