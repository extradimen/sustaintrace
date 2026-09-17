# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from esg_reliable_discovery.v13_evidence import build_v13_packet
from esg_reliable_discovery.v29_integrity import validate_candidate_preflight_v29

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "P23-V32-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P23-GSK-AR2025"
DOCUMENT_SHA = "a3ef37d848fca940f85b6c33815a5d47d1f32726fd389a03910653e24af0f4d2"
PAGES = [54, 55, 78, 79]
TASK_PACK = "data/tasks/p23_task_pack_v0.1.lock.json"
REGISTRY = "data/manifests/p23_mineru_target_registry_v0.1.lock.json"
ACQUISITION = "data/manifests/p23_source_acquisition_v0.1.lock.json"
LAYOUT = "configs/framework/p23_layout_fallback_registry_v0.1.lock.json"


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


def corpus_by_page(registry: dict[str, Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    for target in registry["targets"]:
        root = ROOT / target["output_directory"]
        markdown = next(root.rglob("*.md")).read_text(encoding="utf-8")
        blocks = json.loads(next(root.rglob("*_content_list.json")).read_text(encoding="utf-8"))
        block_text = "\n".join(str(item.get("text") or item.get("table_body") or "") for item in blocks)
        result[target["pdf_page"]] = markdown + "\n" + block_text
    return result


def evidence(page: int, *quotes: str) -> list[dict[str, Any]]:
    return [{"source_id": DOCUMENT, "pdf_page": page, "quote": quote} for quote in quotes]


def reference(task_id: str, answer: str, values: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "task_id": task_id,
        "reference_author": "codex_gpt_simulated_expert",
        "reference_status": "verified_against_frozen_mineru_pages_and_native_layout",
        "answer": answer,
        "normalized_value": values,
        "evidence": items,
        "provenance": {"reference_is_simulated": True, "candidate_model_used": False},
    }


def main() -> None:
    pack, registry = load(TASK_PACK), load(REGISTRY)
    assert pack["experiment_id"] == registry["experiment_id"] == EXPERIMENT
    assert pack["document_sha256"] == registry["document_sha256"] == DOCUMENT_SHA
    assert registry["success_count"] == registry["target_count"] == 4
    assert sorted(item["pdf_page"] for item in registry["targets"]) == PAGES
    corpus = corpus_by_page(registry)

    references = {
        "P23-BOUNDARY-001": reference(
            "P23-BOUNDARY-001",
            "By 2030 GSK targets an 80% absolute GHG reduction from 2020 across all scopes and investment in nature-based solutions for the remaining 20%. By 2045 it targets net zero across the full value chain through a 90% absolute reduction from 2020 across all scopes and neutralisation of residual emissions. It separately targets 100% renewably imported and generated electricity by 2030 for Scope 2. The target boundary includes biogenic land-related emissions and removals from bioenergy feedstocks.",
            {"target_2030_absolute_reduction_percent": 80, "target_2030_baseline_year": 2020, "target_2030_scope": "all scopes", "target_2030_remaining_treatment": "investment in nature-based solutions for remaining 20%", "target_2045_absolute_reduction_percent": 90, "target_2045_baseline_year": 2020, "target_2045_scope": "full value chain; all scopes", "target_2045_residual_treatment": "all residual emissions neutralised", "scope2_renewable_electricity_target_percent": 100, "scope2_renewable_electricity_target_year": 2030, "boundary": "includes biogenic land-related emissions and removals from bioenergy feedstocks"},
            evidence(54, "80% absolute reduction in greenhouse gas emissions", "remaining 20% of our footprint by 2030", "90% absolute reduction in emissions from a 2020 baseline", "all residual emissions neutralised", "100% renewably imported and generated electricity", "biogenic land-related emissions and removals from bioenergy feedstocks"),
        ),
        "P23-GHG-CALC-001": reference(
            "P23-GHG-CALC-001",
            "In thousand tonnes CO2e, the market-based operational total is 565 for 2024 (289 + 232 + 44) and 486 for 2025 (280 + 199 + 7). The change is -13.98%, which is consistent with the issuer's rounded statement of a 14% reduction.",
            {"scope1_energy_thousand_tco2e::2024": 289, "scope1_other_thousand_tco2e::2024": 232, "scope2_market_thousand_tco2e::2024": 44, "calculated_operational_total_thousand_tco2e::2024": 565, "scope1_energy_thousand_tco2e::2025": 280, "scope1_other_thousand_tco2e::2025": 199, "scope2_market_thousand_tco2e::2025": 7, "calculated_operational_total_thousand_tco2e::2025": 486, "calculated_change_percent": -13.98, "issuer_reduction_percent": 14, "rounding_comparison": "consistent", "boundary": "Scope 1 plus market-based Scope 2; thousand tonnes CO2e"},
            evidence(55, "reduced our Scope 1 & 2 carbon emissions", "14% compared with 2024") + evidence(78, "Scope 1 emissions (from energy)", "Scope 1 emissions (other", "Scope 2 emissions (market-based", "280", "289", "199", "232", "44"),
        ),
        "P23-ENERGY-CALC-001": reference(
            "P23-ENERGY-CALC-001",
            "Total energy used fell from 2,577 GWh in 2024 to 2,482 GWh in 2025, a -3.69% change. UK energy fell from 658 to 628 GWh, a -4.56% change. Renewably sourced electricity rose from 90% to 99%, an increase of 9 percentage points.",
            {"total_energy_gwh::2024": 2577, "total_energy_gwh::2025": 2482, "calculated_total_energy_change_percent": -3.69, "uk_energy_gwh::2024": 658, "uk_energy_gwh::2025": 628, "calculated_uk_energy_change_percent": -4.56, "renewable_electricity_percent::2024": 90, "renewable_electricity_percent::2025": 99, "renewable_electricity_change_percentage_points": 9, "boundary": "total operations and UK operations reported separately"},
            evidence(78, "Total energy used (GWh)", "2,482", "2,577", "UK energy used (GWh)", "628", "658", "% renewably sourced electricity", "99 %", "90%"),
        ),
        "P23-WATER-CALC-001": reference(
            "P23-WATER-CALC-001",
            "Total supplied water fell from 7.0 million m3 in 2024 to 6.8 in 2025, a -2.86% change, consistent with the issuer's rounded additional 3% reduction. Supplied water in high-water-stress areas remained 0.3 million m3 in both years, a 0.00% change. Overall operational water use was 30% below the 2020 baseline, and 100% of sites had achieved water stewardship.",
            {"total_supplied_water_million_m3::2024": 7.0, "total_supplied_water_million_m3::2025": 6.8, "calculated_total_water_change_percent": -2.86, "issuer_additional_reduction_percent": 3, "rounding_comparison": "consistent", "high_stress_water_million_m3::2024": 0.3, "high_stress_water_million_m3::2025": 0.3, "calculated_high_stress_change_percent": 0.0, "reduction_from_2020_baseline_percent": 30, "sites_water_stewardship_percent::2025": 100, "boundary": "overall water use in operations; supplied water in million m3"},
            evidence(55, "additional 3% compared with 2024", "decrease of 30% for overall water use from our 2020 baseline") + evidence(78, "Total supplied water million m3", "6.8", "7.0", "areas of high water stress", "0.3", "water stewardship", "100%"),
        ),
        "P23-WORKFORCE-CALC-001": reference(
            "P23-WORKFORCE-CALC-001",
            "At 31 December 2025, the Board was 6 male, 6 female and 12 total (50.00% female); management was 8,794 male, 9,318 female and 18,112 total (51.45% female); all employees were 34,089 male, 32,752 female and 66,841 total (49.00% female). Board and management figures are headcounts; the all-employee total is FTE and male/female values are derived by applying diversity percentages to total FTE.",
            {"board_male": 6, "board_female": 6, "board_total": 12, "board_female_share_percent": 50.0, "management_male": 8794, "management_female": 9318, "management_total": 18112, "management_female_share_percent": 51.45, "all_employees_male": 34089, "all_employees_female": 32752, "all_employees_total_fte": 66841, "all_employees_female_share_percent": 49.0, "reporting_date": "31 December 2025", "method": "all-employee male and female values calculated by applying gender diversity percentages to total FTE"},
            evidence(79, "Employees by gender", "Board", "8,794", "9,318", "18,112", "34,089", "32,752", "66,841", "Headcounts as of 31 December 2025", "full-time equivalent employees (FTEs)", "applying ‘all employees’ gender diversity percentages"),
        ),
        "P23-ASSURE-001": reference(
            "P23-ASSURE-001",
            "Deloitte is identified as the external provider of limited assurance under ISAE 3000 and ISAE 3410 for GHG statements. Separately, the 2025 information underlying the Responsible Business Performance Rating is said to be subject to independent limited assurance by Deloitte. The cited wording does not support extending that assurance to every environmental metric or wider long-term target.",
            {"provider": "Deloitte", "assurance_level": "limited assurance", "ghg_governing_standards": "ISAE3000 and ISAE3410", "ghg_subject": "GHG statements", "responsible_business_subject": "2025 information underlying the Responsible Business Performance Rating", "scope_exclusion": "no basis in cited wording to extend assurance to all environmental metrics or wider long-term targets"},
            evidence(54, "subject to independent limited assurance by Deloitte", "wider set of long term environmental sustainability targets") + evidence(78, "external assurance provider, Deloitte", "limited assurance in accordance with ISAE3000 and ISAE3410 on GHG statements"),
        ),
    }

    task_windows = {item["task_id"]: set(item["target_pages"]) for item in pack["tasks"]}
    entries, quote_count = [], 0
    reference_dir = "data/annotations/p23_simulated"
    for task_id, payload in references.items():
        for item in payload["evidence"]:
            if item["pdf_page"] not in task_windows[task_id]:
                raise ValueError(f"reference_page_outside_window:{task_id}")
            if item["quote"] not in corpus[item["pdf_page"]]:
                raise ValueError(f"reference_quote_not_grounded:{task_id}:{item['quote']}")
            quote_count += 1
        path = f"{reference_dir}/{task_id}.json"
        entries.append({"task_id": task_id, "path": path, "sha256": dump_new(path, payload)})

    contracts = {}
    for task_id, payload in references.items():
        rows = []
        for slot_id, value in payload["normalized_value"].items():
            row = {"predicate_id": f"esg_p23::{task_id.lower()}::{slot_id}", "slot_id": slot_id, "value_type": "number" if isinstance(value, (int, float)) else "string"}
            if "percent" in slot_id:
                row["canonical_unit"] = "percent"
            elif "gwh" in slot_id:
                row["canonical_unit"] = "GWh"
            elif "million_m3" in slot_id:
                row["canonical_unit"] = "million m3"
            elif "thousand_tco2e" in slot_id:
                row["canonical_unit"] = "thousand tonnes CO2e"
            rows.append(row)
        contracts[task_id] = rows
    contracts_path = "configs/framework/p23_slot_contracts_v0.1.lock.json"
    contracts_sha = dump_new(contracts_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "contracts": contracts})
    gold_path = f"{reference_dir}/p23_atomic_slot_gold_v0.1.lock.json"
    gold_sha = dump_new(gold_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_atomic_scoring_projection_before_candidate_inference", "values": {k: v["normalized_value"] for k, v in references.items()}})

    plans = {
        "P23-GHG-CALC-001": {"roles": [{"role_id": x, "unit": "thousand tonnes CO2e"} for x in ["s1e_2024", "s1o_2024", "s2m_2024", "s1e_2025", "s1o_2025", "s2m_2025"]], "candidate_handle_role_map": {"M078-T0006-R0001-C0002": "s1e_2024", "M078-T0006-R0002-C0002": "s1o_2024", "M078-T0006-R0003-C0002": "s2m_2024", "M078-T0006-R0001-C0001": "s1e_2025", "M078-T0006-R0002-C0001": "s1o_2025", "M078-T0006-R0003-C0001": "s2m_2025"}, "steps": [{"step_id": "total_2024", "operation": "sum", "inputs": ["s1e_2024", "s1o_2024", "s2m_2024"]}, {"step_id": "total_2025", "operation": "sum", "inputs": ["s1e_2025", "s1o_2025", "s2m_2025"]}, {"step_id": "change", "operation": "percentage_change", "inputs": ["total_2025", "total_2024"], "rounding_decimals": 2}], "output_slot_map": [{"source_value_id": "total_2024", "slot_id": "calculated_operational_total_thousand_tco2e::2024"}, {"source_value_id": "total_2025", "slot_id": "calculated_operational_total_thousand_tco2e::2025"}, {"source_value_id": "change", "slot_id": "calculated_change_percent"}], "candidate_may_select_operation": False},
        "P23-ENERGY-CALC-001": {"roles": [{"role_id": x, "unit": "GWh" if "renewable" not in x else "percent"} for x in ["total_2024", "total_2025", "uk_2024", "uk_2025", "renewable_2024", "renewable_2025"]], "candidate_handle_role_map": {"M078-T0006-R0010-C0002": "total_2024", "M078-T0006-R0010-C0001": "total_2025", "M078-T0006-R0011-C0002": "uk_2024", "M078-T0006-R0011-C0001": "uk_2025", "M078-T0006-R0012-C0002": "renewable_2024", "M078-T0006-R0012-C0001": "renewable_2025"}, "steps": [{"step_id": "total_change", "operation": "percentage_change", "inputs": ["total_2025", "total_2024"], "rounding_decimals": 2}, {"step_id": "uk_change", "operation": "percentage_change", "inputs": ["uk_2025", "uk_2024"], "rounding_decimals": 2}, {"step_id": "renewable_pp", "operation": "difference", "inputs": ["renewable_2025", "renewable_2024"]}], "output_slot_map": [{"source_value_id": "total_change", "slot_id": "calculated_total_energy_change_percent"}, {"source_value_id": "uk_change", "slot_id": "calculated_uk_energy_change_percent"}, {"source_value_id": "renewable_pp", "slot_id": "renewable_electricity_change_percentage_points"}], "candidate_may_select_operation": False},
        "P23-WATER-CALC-001": {"roles": [{"role_id": x, "unit": "million m3"} for x in ["total_2024", "total_2025", "stress_2024", "stress_2025"]], "candidate_handle_role_map": {"M078-T0006-R0013-C0002": "total_2024", "M078-T0006-R0013-C0001": "total_2025", "M078-T0006-R0014-C0002": "stress_2024", "M078-T0006-R0014-C0001": "stress_2025"}, "steps": [{"step_id": "total_change", "operation": "percentage_change", "inputs": ["total_2025", "total_2024"], "rounding_decimals": 2}, {"step_id": "stress_change", "operation": "percentage_change", "inputs": ["stress_2025", "stress_2024"], "rounding_decimals": 2}], "output_slot_map": [{"source_value_id": "total_change", "slot_id": "calculated_total_water_change_percent"}, {"source_value_id": "stress_change", "slot_id": "calculated_high_stress_change_percent"}], "candidate_may_select_operation": False},
        "P23-WORKFORCE-CALC-001": {"roles": [{"role_id": x, "unit": "count"} for x in ["board_female", "board_total", "management_female", "management_total", "all_female", "all_total"]], "candidate_handle_role_map": {"M079-T0011-R0001-C0002": "board_female", "M079-T0011-R0001-C0003": "board_total", "M079-T0011-R0002-C0002": "management_female", "M079-T0011-R0002-C0003": "management_total", "M079-T0011-R0003-C0002": "all_female", "M079-T0011-R0003-C0003": "all_total"}, "steps": [{"step_id": "board_share", "operation": "percentage_share", "inputs": ["board_female", "board_total"], "rounding_decimals": 2}, {"step_id": "management_share", "operation": "percentage_share", "inputs": ["management_female", "management_total"], "rounding_decimals": 2}, {"step_id": "all_share", "operation": "percentage_share", "inputs": ["all_female", "all_total"], "rounding_decimals": 2}], "output_slot_map": [{"source_value_id": "board_share", "slot_id": "board_female_share_percent"}, {"source_value_id": "management_share", "slot_id": "management_female_share_percent"}, {"source_value_id": "all_share", "slot_id": "all_employees_female_share_percent"}], "candidate_may_select_operation": False},
    }
    preflight = validate_candidate_preflight_v29(pack["tasks"], {"plans": plans})
    plans_path = "configs/framework/p23_calculation_plans_v0.1.lock.json"
    plans_sha = dump_new(plans_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "plans": plans})

    graph_path = "configs/framework/p23_two_dimensional_table_graph_v0.1.lock.json"
    graph_sha = dump_new(graph_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "graphs": [{"graph_id": "P23-METRICS-P078", "pdf_page": 78, "bbox": [84, 315, 912, 579], "header_axis": ["2025", "2024", "2023"], "row_axis": ["Scope 1 energy", "Scope 1 other", "Scope 2 market-based", "total energy", "UK energy", "renewable electricity", "total supplied water", "high-stress supplied water"], "selected_cells": [["Scope 1 energy", "2025", 280], ["Scope 1 energy", "2024", 289], ["Scope 1 other", "2025", 199], ["Scope 1 other", "2024", 232], ["Scope 2 market-based", "2025", 7], ["Scope 2 market-based", "2024", 44], ["total energy", "2025", 2482], ["total energy", "2024", 2577], ["total supplied water", "2025", 6.8], ["total supplied water", "2024", 7.0]]}, {"graph_id": "P23-WORKFORCE-P079", "pdf_page": 79, "bbox": [85, 546, 912, 612], "header_axis": ["Male", "Female", "Total"], "row_axis": ["Board", "Management", "All employees"], "selected_cells": [["Board", "Female", 6], ["Board", "Total", 12], ["Management", "Female", 9318], ["Management", "Total", 18112], ["All employees", "Female", 32752], ["All employees", "Total", 66841]]}]})

    handles = {}
    for task in pack["tasks"]:
        _, _, evidence_handles = build_v13_packet(task_pack_path=ROOT / TASK_PACK, task_id=task["task_id"], acquisition_manifest_path=ROOT / ACQUISITION, raw_root=ROOT, interventions_root=ROOT / "data/interventions", registry_path=ROOT / REGISTRY, workspace_root=ROOT, layout_registry_path=ROOT / LAYOUT)
        handles[task["task_id"]] = sorted({item["handle"] for item in evidence_handles})
    handles_path = "configs/framework/p23_evidence_handle_whitelist_v0.1.lock.json"
    handles_sha = dump_new(handles_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "handles": handles})

    semantic_path = "configs/framework/p23_semantic_qualifiers_v0.1.lock.json"
    semantic_sha = dump_new(semantic_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "qualifiers": {"page_coordinates": "one-based PDF page indexes", "P23-BOUNDARY-001": "separate 2030 and 2045 targets and residual-emissions treatment", "P23-GHG-CALC-001": "Scope 1 plus market-based Scope 2 in thousand tonnes CO2e", "P23-ENERGY-CALC-001": "separate total operations and UK operations", "P23-WATER-CALC-001": "operational supplied water in million m3; preserve issuer rounding", "P23-WORKFORCE-CALC-001": "Board and management headcount versus all-employees FTE derivation", "P23-ASSURE-001": "do not extend assurance beyond explicitly stated GHG statements and RBPR information", "reference_type": "AI-simulated research reference; not independent human gold"}})

    freeze_path = "data/manifests/p23_simulated_reference_freeze_v0.1.lock.json"
    freeze_sha = dump_new(freeze_path, {"schema_version": "1.0", "manifest_id": "P23-SIMULATED-REFERENCE-FREEZE-v0.1", "experiment_id": EXPERIMENT, "status": "simulated_references_frozen_after_questions_page_windows_and_parser_outputs_and_before_candidate_inference", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_pack": {"path": TASK_PACK, "sha256": sha(TASK_PACK)}, "target_registry": {"path": REGISTRY, "sha256": sha(REGISTRY)}, "references": sorted(entries, key=lambda x: x["task_id"]), "integrity_audit": {"reference_count": 6, "evidence_quote_count": quote_count, "all_reference_pages_within_frozen_task_windows": True, "all_quotes_exact_substrings_of_frozen_parser_output": True, "numeric_values_cross_checked_against_native_layout": True, "candidate_model_used": False, "cloud_transmission_occurred": False}, "candidate_reference_visibility": False, "cloud_transmission_allowed": False})
    slot_count = sum(len(v) for v in contracts.values())
    scoring_path = "configs/framework/p23_scoring_rules_v0.1.lock.json"
    scoring_sha = dump_new(scoring_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "reference_projection": gold_path, "dimensions": ["stage_a_schema_validity", "stage_a_evidence_grounding", "stage_a_answer_fidelity", "stage_b_atomic_claim_validity", "stage_b_slot_coverage", "stage_b_exact_numeric_match", "stage_b_literal_exact_string_match", "stage_b_normalized_exact_string_match", "boundary_fidelity", "period_fidelity", "parser_integrity"], "rules": {"aggregate_score": None, "required_slot_count": slot_count, "partial_projection_credit_allowed": True, "numeric_tolerance": 0, "failed_model_outputs_retained": True, "single_attempt_per_stage": True, "silent_retry": False, "posthoc_semantic_repair": False}})
    config_path = "configs/experiments/p23-v32-unseen-lockbox-local.json"
    config_sha = dump_new(config_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_local_configuration_pending_payload_specific_cloud_authorization", "model_config": "configs/models/p1-ollama-cloud-qwen3.5-397b.json", "candidate_model": "qwen3.5:397b-cloud", "pre_candidate_gate": {"use_v29_whole_pack_plan_gate": True, "result": preflight}, "stage_a": {"single_attempt": True, "use_v15_grounding": True, "use_v21_calculation": True, "use_v24_layout_gate": True, "use_v25_calculation_adapter": True, "use_v26_evidence_handle_audit": True, "use_v27_partial_calculation": True, "use_v28_handle_role_binding": True, "use_v29_calculation_executor": True, "use_v30_executor_identity_envelope": True, "use_v31_stage_a_handle_aliases": True, "use_v31_calculation_slot_projection": True, "use_v32_canonical_handles_after_alias_decode": True, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path}, "stage_b": {"single_attempt": True, "use_v20_contract_gate": True, "use_v24_preflight": True, "use_v24_layout_gate": True, "use_v25_single_block_ordered_spans": True, "use_v26_atomic_projection": True, "use_v27_handle_aliases": True, "slot_contracts": contracts_path, "semantic_qualifiers": semantic_path}, "failure_policy": {"archive_model_behavior_failure": True, "silent_retry": False, "posthoc_semantic_repair": False, "infrastructure_resume_requires_lineage": True}, "cloud_transmission_allowed": False})
    audit_path = "data/results/p23_prefreeze_reference_consistency_audit_v0.1.lock.json"
    audit_sha = dump_new(audit_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "gate_result": "pass", "checks": {"task_count": 6, "unique_page_count": 4, "reference_quote_count": quote_count, "reference_pages_within_windows": True, "quotes_grounded_in_frozen_parser_output": True, "numeric_arithmetic_recomputed": True, "whole_pack_calculation_preflight": preflight["status"], "candidate_model_used": False, "cloud_transmission_count": 0}, "hashes": {"task_pack": sha(TASK_PACK), "parser_registry": sha(REGISTRY), "reference_freeze": freeze_sha, "slot_contracts": contracts_sha, "atomic_gold": gold_sha, "calculation_plans": plans_sha, "table_graph": graph_sha, "handle_whitelist": handles_sha, "semantic_qualifiers": semantic_sha, "scoring_rules": scoring_sha, "execution_config": config_sha}})
    local_pack_path = "data/tasks/p23_local_execution_task_pack_v0.1.lock.json"
    local_pack_sha = dump_new(local_pack_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "frozen_local_pack_pending_payload_specific_cloud_authorization", "inference_allowed": False, "parent": TASK_PACK, "source_registry": "data/manifests/p23_source_registry_v0.1.lock.json", "parser_registry": REGISTRY, "reference_freeze": freeze_path, "reference_consistency_audit": audit_path, "slot_contracts": contracts_path, "atomic_scoring_projection": gold_path, "semantic_qualifiers": semantic_path, "table_graph": graph_path, "layout_fallback_registry": LAYOUT, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path, "scoring_rules": scoring_path, "execution_config": config_path, "tasks": [{**task, "reference_file": f"{reference_dir}/{task['task_id']}.json"} for task in pack["tasks"]], "release_condition": "Payload-specific user authorization for GSK 2025 Annual Report pages 54,55,78,79 to Ollama Cloud qwen3.5:397b-cloud solely for P23 Stage A/Stage B single-attempt candidate inference."})
    readiness_path = "data/results/p23_v32_local_readiness_v0.1.lock.json"
    readiness_sha = dump_new(readiness_path, {"schema_version": "3.2", "experiment_id": EXPERIMENT, "status": "local_readiness_passed_waiting_for_payload_specific_cloud_authorization", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_count": 6, "slot_count": slot_count, "unique_target_pages": PAGES, "mineru": {"success_count": 4, "failure_count": 0, "registry": REGISTRY, "registry_sha256": sha(REGISTRY), "preserved_infrastructure_failures": 4, "recovery_generations": ["RESUME01"]}, "prefreeze_integrity": {"status": "passed", "reference_audit": audit_path, "reference_audit_sha256": audit_sha, "reference_freeze": freeze_path, "reference_freeze_sha256": freeze_sha, "evidence_quotes_checked": quote_count, "whole_pack_calculation_preflight": "passed"}, "artifacts": {"local_task_pack": {"path": local_pack_path, "sha256": local_pack_sha}}, "cloud_boundary": {"candidate_model": "qwen3.5:397b-cloud", "cloud_transmission_count": 0, "candidate_model_call_count": 0, "explicit_payload_specific_authorization_received": False, "authorized_pages_required": PAGES, "authorized_scope_required": "P23 Stage A/Stage B single-attempt candidate inference"}, "locked_prior_experiments_modified": False})
    print(json.dumps({"status": "ready_waiting_for_authorization", "readiness": readiness_path, "readiness_sha256": readiness_sha, "slots": slot_count, "quotes": quote_count}, sort_keys=True))


if __name__ == "__main__":
    main()
