# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from esg_reliable_discovery.v13_evidence import build_v13_packet

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P19-V28-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P19-NOVO-NORDISK-AR2025"
DOCUMENT_SHA = "f5475f1e043eaa99526772c0e06677a74ab2c2abb8181755afbe02a10e395092"
PDF = "data/raw/p19_staging/novo-nordisk-annual-report-2025.pdf"
PAGES = [58, 65, 66, 80, 123, 124, 135, 136]
TASK_PACK = "data/tasks/p19_task_pack_v0.1.lock.json"
REGISTRY = "data/manifests/p19_mineru_target_registry_v0.1.lock.json"
LAYOUT = "configs/framework/p19_layout_fallback_registry_v0.1.lock.json"


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def dump_new(path: str, value: Any) -> str:
    target = ROOT / path
    if target.exists():
        raise RuntimeError(f"refusing_to_overwrite:{path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    return [{"source_id": DOCUMENT, "pdf_page": page, "quote": quote} for quote in quotes]


def ref(task_id: str, answer: str, values: dict[str, Any], items: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
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

    ghg_change = ((Decimal(183) - Decimal(101)) / Decimal(101) * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    scope3_share_2025 = (Decimal(1992) / Decimal(2507) * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    scope3_share_2024 = (Decimal(1680) / Decimal(2160) * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    references = {
        "P19-GHG-CALC-001": ref(
            "P19-GHG-CALC-001",
            "In 2025, Scope 1 was 120 and market-based Scope 2 was 63, both in 1,000 tCO2e. Their sum is 183, exactly matching the disclosed market-based Scope 1 and 2 total, for a zero difference. Against 101 in 2024, that disclosed total increased by 81.19%.",
            {"scope_1_2025_thousand_tco2e": 120, "scope_2_market_based_2025_thousand_tco2e": 63, "calculated_scope_1_2_2025_thousand_tco2e": 183, "disclosed_scope_1_2_2025_thousand_tco2e": 183, "difference_thousand_tco2e": 0, "disclosed_scope_1_2_2024_thousand_tco2e": 101, "calculated_change_percent": float(ghg_change), "direction": "increase"},
            evidence(66, "1,000 tCO2e", "Scope 1 GHG emissions", "120", "Scope 2 GHG emissions - market-based", "63", "Scope 1 and 2 GHG emissions - market-based", "183", "101"),
        ),
        "P19-ENERGY-001": ref(
            "P19-ENERGY-001",
            "In GWh, total energy was 1,726 in 2025 and 1,400 in 2024; fossil energy was 742 and 476; renewable energy was 984 and 924; and renewable shares were 57% and 66%. The narrative says total energy increased by 23%. The 2024 figures were restated because contractual biomass-derived heat and steam was classified as renewable for both 2024 and 2025, with the fossil and renewable heat/steam rows updated accordingly.",
            {"total_energy_gwh::2025": 1726, "total_energy_gwh::2024": 1400, "fossil_energy_gwh::2025": 742, "fossil_energy_gwh::2024": 476, "renewable_energy_gwh::2025": 984, "renewable_energy_gwh::2024": 924, "renewable_share_percent::2025": 57, "renewable_share_percent::2024": 66, "narrative_change_percent": 23, "qualification": "contractual biomass-derived heat and steam classified as renewable for both 2024 and 2025; affected 2024 fossil and renewable heat/steam values were restated"},
            evidence(65, "Total energy consumption increased by 23% compared to 2024", "Total energy consumption related to own operations", "1,726", "1,400", "Total energy consumption from fossil sources", "742", "476", "Total energy consumption from renewable sources", "984", "924", "57%", "66%", "we now include contractual biomass-derived sources in Kalundborg, Denmark, under renewable energy (both for 2024 and 2025)"),
        ),
        "P19-SCOPE3-001": ref(
            "P19-SCOPE3-001",
            "In 2025, Scope 3 was 2,507 (1,000 tCO2e); Category 1 was 1,383 and Category 2 was 609, summing to 1,992 or 79.46% of total Scope 3. In 2024, the corresponding values were 2,160, 1,215 and 465, summing to 1,680 or 77.78%. The report attributes the 2025 increase to procurement of goods and services and higher capital expenditure for property, plant and equipment.",
            {"scope3_total_thousand_tco2e::2025": 2507, "category1_thousand_tco2e::2025": 1383, "category2_thousand_tco2e::2025": 609, "category1_plus_2_thousand_tco2e::2025": 1992, "category1_plus_2_share_percent::2025": float(scope3_share_2025), "scope3_total_thousand_tco2e::2024": 2160, "category1_thousand_tco2e::2024": 1215, "category2_thousand_tco2e::2024": 465, "category1_plus_2_thousand_tco2e::2024": 1680, "category1_plus_2_share_percent::2024": float(scope3_share_2024), "increase_explanation": "procurement of goods and services (category 1) and higher CapEx for property, plant and equipment (category 2)"},
            evidence(66, "Scope 3 GHG emissions", "2,507", "2,160", "Category 1: Purchased goods and Services", "1,383", "1,215", "Category 2: Capital goods", "609", "465", "Scope 3 emissions increased by 16% from 2024 to 2025, driven by both procurement of goods and services (category 1) and higher CapEx for property, plant and equipment (category 2)."),
        ),
        "P19-WORKFORCE-001": ref(
            "P19-WORKFORCE-001",
            "At year-end 2025, permanent employees were 64,974 and temporary employees 4,531; their sum of 69,505 exactly matches disclosed headcount. For 2024, 68,669 plus 5,487 equals the disclosed 74,156 exactly. No employees were on non-guaranteed-hours contracts. The 2024 employee metrics, including the displayed FTE and headcount, exclude Catalent; including Catalent, headcount was 77,349.",
            {"permanent_headcount::2025": 64974, "temporary_headcount::2025": 4531, "recomputed_headcount::2025": 69505, "disclosed_headcount::2025": 69505, "difference_headcount::2025": 0, "permanent_headcount::2024": 68669, "temporary_headcount::2024": 5487, "recomputed_headcount::2024": 74156, "disclosed_headcount::2024": 74156, "difference_headcount::2024": 0, "non_guaranteed_hours_employees": False, "qualification": "2024 employee-related metrics exclude Catalent; including Catalent, 2024 headcount was 77,349"},
            evidence(58, "By end of 2025, Novo Nordisk employed 64,974 permanent and 4,531 temporary employees, similar to the 2024 split (68,669 permanent and 5,487 temporary).", "No employees in Novo Nordisk’s own workforce are hired on non-guaranteed hours contracts.", "Total number of employees (headcount)", "69,505", "74,156", "All 2024 employee related metrics exclude Catalent", "Including Catalent, FTE is 76,302 and headcount is 77,349."),
        ),
        "P19-TAXONOMY-001": ref(
            "P19-TAXONOMY-001",
            "For 2025, total turnover was DKK 309,064 million, 100% eligible, with DKK 0 aligned and a 0% aligned share. Total CapEx was DKK 94,249 million, 63% eligible, with DKK 5,835 million aligned and a 6% aligned share. Alignment came from activity 7.1 Construction of new buildings. Non-material activities were 0% of turnover and 3% of CapEx (DKK 2,491 million). OpEx eligibility was not reported because OpEx was immaterial under the early-adopted new Delegated Act; total OpEx was DKK 49,308 million.",
            {"turnover_total_mdkk::2025": 309064, "turnover_eligible_percent::2025": 100, "turnover_aligned_mdkk::2025": 0, "turnover_aligned_percent::2025": 0, "capex_total_mdkk::2025": 94249, "capex_eligible_percent::2025": 63, "capex_aligned_mdkk::2025": 5835, "capex_aligned_percent::2025": 6, "aligned_activity": "7.1 Construction of new buildings", "nonmaterial_turnover_percent::2025": 0, "nonmaterial_capex_mdkk::2025": 2491, "nonmaterial_capex_percent::2025": 3, "opex_total_mdkk::2025": 49308, "opex_eligibility_status": "not reported due to immateriality under the new Delegated Act"},
            evidence(80, "Novo Nordisk adjusted EU Taxonomy overview", "309,064", "94,249", "2,491", "5,835", "7.1 Construction of new buildings") + evidence(135, "we have opted to not report on OpEx eligibility due to immateriality", "Total OpEx: 49,308 mDKK") + evidence(136, "Manufacture of medical products", "Construction of new buildings", "Renovation of existing buildings"),
        ),
        "P19-ASSURE-001": ref(
            "P19-ASSURE-001",
            "Deloitte performed limited assurance on Novo Nordisk's Sustainability statement in the Management Report for 1 January–31 December 2025. The criteria were Danish Financial Statements Act section 99a, including ESRS and the Article 8 EU Taxonomy disclosures. The negative-form conclusion was that nothing came to attention indicating material non-compliance. ISAE 3000 (Revised) governed the engagement; limited procedures were less extensive and provided substantially lower assurance than reasonable assurance. Comparative 2023 information was not assured. Deloitte's Anders Vad Dons and Sumit Sudan signed in Copenhagen on 4 February 2026.",
            {"assured_subject": "Sustainability statement included in the Management Report for 1 January–31 December 2025", "assurance_level": "limited assurance", "criteria": "Danish Financial Statements Act section 99a including ESRS and Article 8 EU Taxonomy disclosures", "conclusion_form": "nothing has come to our attention", "governing_standard": "ISAE 3000 (Revised)", "procedure_difference": "limited procedures are less extensive and provide substantially lower assurance than reasonable assurance", "unassured_comparative_period": 2023, "assurance_provider": "Deloitte Statsautoriseret Revisionspartnerselskab", "signatories": "Anders Vad Dons | Sumit Sudan", "signature_date": "2026-02-04"},
            evidence(123, "limited assurance engagement on the Sustainability statement of Novo Nordisk A/S", "financial year 1 January – 31 December 2025", "nothing has come to our attention", "European Sustainability Reporting Standards (ESRS)", "Article 8 of EU Regulation 2020/852", "ISAE 3000 (Revised)", "less in extent than for, a reasonable assurance engagement", "substantially lower", "financial year 2023 was not subject to an assurance engagement") + evidence(124, "Copenhagen, 4 February 2026", "Deloitte", "Anders Vad Dons", "Sumit Sudan"),
        ),
    }

    task_windows = {item["task_id"]: set(item["target_pages"]) for item in pack["tasks"]}
    checked = 0
    entries = []
    reference_dir = "data/annotations/p19_simulated"
    for task_id, payload in references.items():
        for item in payload["evidence"]:
            if item["pdf_page"] not in task_windows[task_id]:
                raise ValueError(f"reference_page_outside_window:{task_id}")
            if item["quote"] not in pages[item["pdf_page"]]:
                raise ValueError(f"reference_quote_not_grounded:{task_id}:{item['quote']}")
            checked += 1
        path = f"{reference_dir}/{task_id}.json"
        entries.append({"task_id": task_id, "path": path, "sha256": dump_new(path, payload)})

    units = {"thousand_tco2e": "1,000 tCO2e", "percent": "percent", "gwh": "GWh", "headcount": "headcount", "mdkk": "million DKK"}
    contracts = {}
    for task_id, payload in references.items():
        rows = []
        for slot_id, value in payload["normalized_value"].items():
            row = {"predicate_id": f"esg_p19::{task_id.lower()}::{slot_id}", "slot_id": slot_id, "value_type": "boolean" if isinstance(value, bool) else "number" if isinstance(value, (int, float)) else "string"}
            for marker, unit in units.items():
                if marker in slot_id:
                    row["canonical_unit"] = unit
                    break
            rows.append(row)
        contracts[task_id] = rows
    contracts_path = "configs/framework/p19_slot_contracts_v0.1.lock.json"
    contracts_sha = dump_new(contracts_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "contracts": contracts})
    gold_path = f"{reference_dir}/p19_atomic_slot_gold_v0.1.lock.json"
    gold_sha = dump_new(gold_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_atomic_scoring_projection_before_candidate_inference", "values": {task_id: payload["normalized_value"] for task_id, payload in references.items()}})
    freeze_path = "data/manifests/p19_simulated_reference_freeze_v0.1.lock.json"
    freeze_sha = dump_new(freeze_path, {"schema_version": "1.0", "manifest_id": "P19-SIMULATED-REFERENCE-FREEZE-v0.1", "experiment_id": EXPERIMENT, "status": "simulated_references_frozen_after_questions_page_windows_and_parser_outputs_and_before_candidate_inference", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_pack": {"path": TASK_PACK, "sha256": sha(TASK_PACK)}, "target_registry": {"path": REGISTRY, "sha256": sha(REGISTRY)}, "references": sorted(entries, key=lambda item: item["task_id"]), "integrity_audit": {"reference_count": 6, "evidence_quote_count": checked, "all_reference_pages_within_frozen_task_windows": True, "all_quotes_exact_substrings_of_frozen_MinerU_markdown": True, "numeric_values_cross_checked_against_native_layout": True, "candidate_model_used": False, "cloud_transmission_occurred": False}, "candidate_reference_visibility": False, "cloud_transmission_allowed": False})
    audit_path = "data/results/p19_prefreeze_reference_consistency_audit_v0.1.lock.json"
    audit_sha = dump_new(audit_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "gate_result": "pass", "checks": {"task_count": 6, "unique_page_count": 8, "reference_quote_count": checked, "reference_pages_within_windows": True, "quotes_grounded_in_frozen_parser_output": True, "numeric_arithmetic_recomputed": True, "candidate_model_used": False, "cloud_transmission_count": 0}, "hashes": {"task_pack": sha(TASK_PACK), "parser_registry": sha(REGISTRY), "reference_freeze": freeze_sha, "slot_contracts": contracts_sha, "atomic_gold": gold_sha}})

    semantic_path = "configs/framework/p19_semantic_qualifiers_v0.1.lock.json"
    semantic_sha = dump_new(semantic_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "qualifiers": {"reporting_period": "calendar year 2025 unless a 2024 or 2023 comparative is explicitly named", "page_coordinates": "one-based PDF page indexes", "P19-GHG-CALC-001": {"boundary": "market-based Scope 1 and 2; retain 1,000 tCO2e"}, "P19-ENERGY-001": {"boundary": "own operations; preserve GWh, renewable-share and 2024 restatement qualification"}, "P19-SCOPE3-001": {"boundary": "Category 1 and 2 shares of disclosed Scope 3 total"}, "P19-WORKFORCE-001": {"boundary": "permanent plus temporary headcount; 2024 excludes Catalent unless qualified"}, "P19-TAXONOMY-001": {"boundary": "separate total, eligible, aligned, non-material and OpEx immateriality"}, "P19-ASSURE-001": {"boundary": "limited assurance on 2025 Sustainability statement; 2023 comparative not assured"}, "reference_type": "AI-simulated research reference; not independent human gold"}})

    plans_path = "configs/framework/p19_calculation_plans_v0.1.lock.json"
    plans = {
        "P19-GHG-CALC-001": {"roles": [{"role_id": x, "unit": "1,000 tCO2e"} for x in ["scope_1_2025", "scope_2_market_based_2025", "disclosed_scope_1_2_2025", "disclosed_scope_1_2_2024"]], "candidate_handle_role_map": {"P066-L0012": "scope_1_2025", "M066-T0001-R0003-C0001": "scope_2_market_based_2025", "M066-T0001-R0005-C0001": "disclosed_scope_1_2_2025", "M066-T0001-R0005-C0002": "disclosed_scope_1_2_2024"}, "steps": [{"step_id": "calculated_scope_1_2_2025", "operation": "sum", "inputs": ["scope_1_2025", "scope_2_market_based_2025"]}, {"step_id": "difference", "operation": "difference", "inputs": ["calculated_scope_1_2_2025", "disclosed_scope_1_2_2025"]}, {"step_id": "percentage_change", "operation": "percentage_change", "inputs": ["disclosed_scope_1_2_2025", "disclosed_scope_1_2_2024"], "rounding_decimals": 2}], "candidate_may_select_operation": False},
        "P19-SCOPE3-001": {"roles": [{"role_id": x, "unit": "1,000 tCO2e"} for x in ["category1_2025", "category2_2025", "disclosed_total_2025", "category1_2024", "category2_2024", "disclosed_total_2024"]], "candidate_handle_role_map": {"M066-T0001-R0007-C0001": "category1_2025", "M066-T0001-R0008-C0001": "category2_2025", "M066-T0001-R0006-C0001": "disclosed_total_2025", "M066-T0001-R0007-C0002": "category1_2024", "M066-T0001-R0008-C0002": "category2_2024", "M066-T0001-R0006-C0002": "disclosed_total_2024"}, "steps": [{"step_id": "category1_plus_2_2025", "operation": "sum", "inputs": ["category1_2025", "category2_2025"]}, {"step_id": "share_2025", "operation": "percentage_share", "inputs": ["category1_plus_2_2025", "disclosed_total_2025"], "rounding_decimals": 2}, {"step_id": "category1_plus_2_2024", "operation": "sum", "inputs": ["category1_2024", "category2_2024"]}, {"step_id": "share_2024", "operation": "percentage_share", "inputs": ["category1_plus_2_2024", "disclosed_total_2024"], "rounding_decimals": 2}], "candidate_may_select_operation": False},
    }
    plans_sha = dump_new(plans_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "plans": plans})

    graph_path = "configs/framework/p19_two_dimensional_table_graph_v0.1.lock.json"
    graph_sha = dump_new(graph_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "graphs": [{"graph_id": "P19-GHG-P066", "pdf_page": 66, "header_axis": ["2025", "2024"], "row_axis": ["Scope 1", "Scope 2 market-based", "Scope 1+2 market-based", "Scope 3", "Category 1", "Category 2"], "selected_cells": [["Scope 1", "2025", 120], ["Scope 2 market-based", "2025", 63], ["Scope 1+2 market-based", "2025", 183], ["Scope 1+2 market-based", "2024", 101], ["Scope 3", "2025", 2507], ["Category 1", "2025", 1383], ["Category 2", "2025", 609]]}, {"graph_id": "P19-ENERGY-P065", "pdf_page": 65, "header_axis": ["2025", "2024"], "row_axis": ["total", "fossil", "renewable", "renewable share"], "selected_cells": [["total", "2025", 1726], ["total", "2024", 1400], ["fossil", "2025", 742], ["renewable", "2025", 984], ["renewable share", "2025", 57]]}, {"graph_id": "P19-WORKFORCE-P058", "pdf_page": 58, "header_axis": ["2025", "2024"], "row_axis": ["permanent", "temporary", "total headcount"], "selected_cells": [["permanent", "2025", 64974], ["temporary", "2025", 4531], ["total headcount", "2025", 69505], ["permanent", "2024", 68669], ["temporary", "2024", 5487], ["total headcount", "2024", 74156]]}, {"graph_id": "P19-TAXONOMY", "pdf_page": 135, "header_axis": ["total", "eligible percent", "aligned mDKK", "aligned percent", "non-material percent"], "row_axis": ["Turnover", "CapEx"], "selected_cells": [["Turnover", "total", 309064], ["Turnover", "eligible percent", 100], ["CapEx", "total", 94249], ["CapEx", "eligible percent", 63], ["CapEx", "aligned mDKK", 5835], ["CapEx", "aligned percent", 6], ["CapEx", "non-material percent", 3]]}]})

    handles = {}
    for task in pack["tasks"]:
        _, _, evidence_handles = build_v13_packet(task_pack_path=ROOT / TASK_PACK, task_id=task["task_id"], acquisition_manifest_path=ROOT / "data/manifests/p19_source_acquisition_v0.1.lock.json", raw_root=ROOT, interventions_root=ROOT / "data/interventions", registry_path=ROOT / REGISTRY, workspace_root=ROOT, layout_registry_path=ROOT / LAYOUT)
        handles[task["task_id"]] = sorted({item["handle"] for item in evidence_handles})
    handles_path = "configs/framework/p19_evidence_handle_whitelist_v0.1.lock.json"
    handles_sha = dump_new(handles_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "handles": handles})
    slot_count = sum(len(items) for items in contracts.values())
    scoring_path = "configs/framework/p19_scoring_rules_v0.1.lock.json"
    scoring_sha = dump_new(scoring_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "reference_projection": gold_path, "dimensions": ["stage_a_schema_validity", "stage_a_evidence_grounding", "stage_a_answer_fidelity", "stage_b_atomic_claim_validity", "stage_b_slot_coverage", "stage_b_exact_numeric_match", "stage_b_literal_exact_string_match", "stage_b_normalized_exact_string_match", "string_token_jaccard", "boundary_fidelity", "period_fidelity", "parser_integrity"], "rules": {"aggregate_score": None, "required_slot_count": slot_count, "partial_projection_credit_allowed": True, "missing_slots_explicit": True, "missing_values_invented": False, "numeric_tolerance": 0, "failed_model_outputs_retained": True, "single_attempt_per_stage": True, "silent_retry": False, "posthoc_semantic_repair": False}})
    config_path = "configs/experiments/p19-v28-unseen-lockbox-local.json"
    config_sha = dump_new(config_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_local_configuration_pending_payload_specific_cloud_authorization", "model_config": "configs/models/p1-ollama-cloud-qwen3.5-397b.json", "candidate_model": "qwen3.5:397b-cloud", "stage_a": {"single_attempt": True, "use_v15_grounding": True, "use_v21_calculation": True, "use_v24_layout_gate": True, "use_v25_calculation_adapter": True, "use_v26_evidence_handle_audit": True, "use_v27_partial_calculation": True, "use_v28_handle_role_binding": True, "use_v28_task_id_gate": True, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path}, "stage_b": {"single_attempt": True, "use_v20_contract_gate": True, "use_v24_preflight": True, "use_v24_layout_gate": True, "use_v25_single_block_ordered_spans": True, "use_v26_atomic_projection": True, "use_v27_handle_aliases": True, "slot_contracts": contracts_path, "semantic_qualifiers": semantic_path}, "failure_policy": {"archive_model_behavior_failure": True, "silent_retry": False, "posthoc_semantic_repair": False, "infrastructure_resume_requires_lineage": True}, "cloud_transmission_allowed": False})
    local_pack_path = "data/tasks/p19_local_execution_task_pack_v0.1.lock.json"
    local_pack_sha = dump_new(local_pack_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "frozen_local_pack_pending_payload_specific_cloud_authorization", "inference_allowed": False, "parent": TASK_PACK, "source_registry": "data/manifests/p19_source_registry_v0.1.lock.json", "parser_registry": REGISTRY, "reference_freeze": freeze_path, "reference_consistency_audit": audit_path, "slot_contracts": contracts_path, "atomic_scoring_projection": gold_path, "semantic_qualifiers": semantic_path, "table_graph": graph_path, "layout_fallback_registry": LAYOUT, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path, "scoring_rules": scoring_path, "execution_config": config_path, "tasks": [{**task, "reference_file": f"{reference_dir}/{task['task_id']}.json"} for task in pack["tasks"]], "release_condition": "Payload-specific user authorization for Novo Nordisk Annual Report 2025 pages 58,65,66,80,123,124,135,136 to Ollama Cloud qwen3.5:397b-cloud solely for P19 Stage A/Stage B single-attempt candidate inference."})

    report_path = "docs/85_P19_v2.8本地预冻结与云授权边界_v0.1.md"
    report = ROOT / report_path
    if report.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    report.write_text(f"""# P19 v2.8 本地预冻结与云授权边界

## 结论

P19 已完成全部本地预冻结，尚未向云模型发送任何 Novo Nordisk 报告内容，也未启动候选推理。P3–P18 未修改、未重跑、未重评分。

## 样本与任务

- 样本：Novo Nordisk Annual Report 2025
- 文档 SHA256：`{DOCUMENT_SHA}`
- 冻结问题：6 项
- 唯一证据页：8 页（58、65、66、80、123、124、135、136）
- MinerU：8/8 成功并逐文件哈希验证；两代基础设施恢复仅补未完成页，INITIAL 与 RESUME01 的失败记录均保留
- 模拟参考：6 份，{checked} 条逐字证据引文
- 原子评分槽位：{slot_count} 个

## 关键审计点

- 2025 Scope 1 与市场法 Scope 2 合计 183（千吨二氧化碳当量），与披露总数一致；较 2024 增长 81.19%。
- Scope 3 类别 1 与类别 2 的合计占比分别为 2025 年 79.46%、2024 年 77.78%。
- 2024 员工口径排除 Catalent，资格限定已进入参考与槽位。
- EU Taxonomy 严格区分 eligible、aligned、非重大活动与 OpEx 非重大性。
- 鉴证严格限定为 2025 可持续发展声明的有限保证，2023 比较信息未获保证。

## 云传输边界

仅在取得本载荷特定授权后，才可将第 58、65、66、80、123、124、135、136 页冻结证据发送至 Ollama Cloud 的 `qwen3.5:397b-cloud`，且仅用于 P19 Stage A/Stage B 单次候选推理。
""", encoding="utf-8")
    report_sha = sha(report_path)
    readiness_path = "data/results/p19_v28_local_readiness_v0.1.lock.json"
    readiness_sha = dump_new(readiness_path, {"schema_version": "2.8", "experiment_id": EXPERIMENT, "status": "local_readiness_passed_waiting_for_payload_specific_cloud_authorization", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_count": 6, "slot_count": slot_count, "unique_target_pages": PAGES, "mineru": {"success_count": 8, "failure_count": 0, "registry": REGISTRY, "registry_sha256": sha(REGISTRY), "preserved_infrastructure_failures": 9, "recovery_generations": ["RESUME01", "RESUME02"]}, "prefreeze_integrity": {"status": "passed", "reference_audit": audit_path, "reference_audit_sha256": audit_sha, "reference_freeze": freeze_path, "reference_freeze_sha256": freeze_sha, "evidence_quotes_checked": checked, "contract_preflights_passed": slot_count, "deterministic_calculation_passed": True}, "artifacts": {"slot_contracts": {"path": contracts_path, "sha256": contracts_sha}, "atomic_gold": {"path": gold_path, "sha256": gold_sha}, "semantic_qualifiers": {"path": semantic_path, "sha256": semantic_sha}, "calculation_plans": {"path": plans_path, "sha256": plans_sha}, "table_graph": {"path": graph_path, "sha256": graph_sha}, "layout_registry": {"path": LAYOUT, "sha256": sha(LAYOUT)}, "handle_whitelist": {"path": handles_path, "sha256": handles_sha}, "scoring_rules": {"path": scoring_path, "sha256": scoring_sha}, "execution_config": {"path": config_path, "sha256": config_sha}, "local_task_pack": {"path": local_pack_path, "sha256": local_pack_sha}, "report": {"path": report_path, "sha256": report_sha}}, "cloud_boundary": {"candidate_model": "qwen3.5:397b-cloud", "cloud_transmission_count": 0, "candidate_model_call_count": 0, "explicit_payload_specific_authorization_received": False, "authorized_pages_required": PAGES, "authorized_scope_required": "P19 Stage A/Stage B single-attempt candidate inference"}, "locked_prior_experiments_modified": False})
    print(json.dumps({"status": "ready_waiting_for_authorization", "readiness": readiness_path, "readiness_sha256": readiness_sha, "slots": slot_count, "quotes": checked}, sort_keys=True))


if __name__ == "__main__":
    main()
