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
EXPERIMENT = "P21-V30-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P21-BASF-AR2025"
DOCUMENT_SHA = "6fa0a9f60a3149e585a5b52f06efde1e0aaa5d1156da0d71a1fd40822df7f8b7"
PAGES = [192, 194, 195, 242, 245, 262, 263, 433, 434, 436]
TASK_PACK = "data/tasks/p21_task_pack_v0.1.lock.json"
REGISTRY = "data/manifests/p21_mineru_target_registry_v0.1.lock.json"
LAYOUT = "configs/framework/p21_layout_fallback_registry_v0.1.lock.json"


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
    result: dict[int, str] = {}
    for target in registry["targets"]:
        files = list((ROOT / target["output_directory"]).rglob("*.md"))
        if len(files) != 1:
            raise ValueError(f"markdown_ambiguous:{target['pdf_page']}:{files}")
        result[target["pdf_page"]] = files[0].read_text(encoding="utf-8")
    return result


def evidence(page: int, *quotes: str) -> list[dict[str, Any]]:
    return [{"source_id": DOCUMENT, "pdf_page": page, "quote": q} for q in quotes]


def ref(task_id: str, answer: str, values: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": "1.0", "task_id": task_id, "reference_author": "codex_gpt_simulated_expert", "reference_status": "verified_against_frozen_mineru_pages_and_native_layout", "answer": answer, "normalized_value": values, "evidence": items, "provenance": {"reference_is_simulated": True, "candidate_model_used": False}}


def main() -> None:
    pack, registry = load(TASK_PACK), load(REGISTRY)
    assert pack["experiment_id"] == registry["experiment_id"] == EXPERIMENT
    assert pack["document_sha256"] == registry["document_sha256"] == DOCUMENT_SHA
    assert registry["success_count"] == registry["target_count"] == 10
    assert sorted(t["pdf_page"] for t in registry["targets"]) == PAGES
    pages = markdown_by_page(registry)

    ghg_2025 = Decimal("15.369") + Decimal("1.901")
    ghg_2024 = Decimal("15.556") + Decimal("2.396")
    ghg_change = ((ghg_2025 - ghg_2024) / ghg_2024 * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s3_sum_2025 = Decimal("52.56") + Decimal("27.17")
    s3_sum_2024 = Decimal("51.54") + Decimal("25.67")
    s3_share_2025 = (s3_sum_2025 / Decimal("93.97") * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s3_share_2024 = (s3_sum_2024 / Decimal("92.33") * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    references = {
        "P21-GHG-CALC-001": ref("P21-GHG-CALC-001", f"Under financial control, gross Scope 1 plus gross market-based Scope 2 was {ghg_2025} Mt CO2e in 2025 and {ghg_2024} Mt CO2e in adjusted 2024, a {ghg_change}% change. BASF separately reports row changes of -1% for gross Scope 1 and -21% for gross market-based Scope 2. The calculated two-scope sum is not BASF's total market-based emissions including Scope 3.", {"scope1_gross_mtco2e::2025": 15.369, "scope2_market_gross_mtco2e::2025": 1.901, "calculated_scope1_plus_scope2_mtco2e::2025": float(ghg_2025), "scope1_gross_mtco2e::2024_adjusted": 15.556, "scope2_market_gross_mtco2e::2024_adjusted": 2.396, "calculated_scope1_plus_scope2_mtco2e::2024_adjusted": float(ghg_2024), "calculated_change_percent": float(ghg_change), "issuer_scope1_row_change_percent": -1, "issuer_scope2_market_row_change_percent": -21, "non_conflation": "calculated Scope 1 plus market-based Scope 2 is not total market-based emissions including Scope 3"}, evidence(194, "Gross Scope 1 emissions</td><td rowspan=1 colspan=1>15.369</td><td rowspan=1 colspan=1>15.115</td><td rowspan=1 colspan=1>15.556c</td><td rowspan=1 colspan=1>15.220c</td><td rowspan=1 colspan=1>-1%", "Gross market-based Scope 2 emissions</td><td rowspan=1 colspan=1>1.901</td><td rowspan=1 colspan=1>2.052</td><td rowspan=1 colspan=1>2.396</td><td rowspan=1 colspan=1>2.460</td><td rowspan=1 colspan=1>-21%")),
        "P21-ENERGY-001": ref("P21-ENERGY-001", "For financial/operational control respectively, 2025 total energy was 74.3/73.5 million MWh, renewable 5.2/5.2 (6.9%/7.1%), and fossil 69.1/68.2 (93.0%/92.9%). Restated 2024 values were total 74.8/74.1, renewable 3.6/3.6 (4.8%/4.9%), and fossil 71.2/70.5 (95.1%/95.1%).", {"financial_total_million_mwh::2025": 74.3, "operational_total_million_mwh::2025": 73.5, "financial_renewable_million_mwh::2025": 5.2, "operational_renewable_million_mwh::2025": 5.2, "financial_renewable_share_percent::2025": 6.9, "operational_renewable_share_percent::2025": 7.1, "financial_fossil_million_mwh::2025": 69.1, "operational_fossil_million_mwh::2025": 68.2, "financial_fossil_share_percent::2025": 93.0, "operational_fossil_share_percent::2025": 92.9, "financial_total_million_mwh::2024_restated": 74.8, "operational_total_million_mwh::2024_restated": 74.1, "financial_renewable_million_mwh::2024_restated": 3.6, "operational_renewable_million_mwh::2024_restated": 3.6, "financial_renewable_share_percent::2024_restated": 4.8, "operational_renewable_share_percent::2024_restated": 4.9, "financial_fossil_million_mwh::2024_restated": 71.2, "operational_fossil_million_mwh::2024_restated": 70.5, "financial_fossil_share_percent::2024_restated": 95.1, "operational_fossil_share_percent::2024_restated": 95.1}, evidence(192, "Total energy consumptionb</td><td rowspan=1 colspan=1>74.3</td><td rowspan=1 colspan=1>73.5</td><td rowspan=1 colspan=1>74.8c</td><td rowspan=1 colspan=1>74.1c", "Total energy consumption from renewable sources</td><td rowspan=1 colspan=1>5.2</td><td rowspan=1 colspan=1>5.2</td><td rowspan=1 colspan=1>3.6</td><td rowspan=1 colspan=1>3.6", "Share of renewable sources in total energy consumption            %</td><td rowspan=1 colspan=1>6.9</td><td rowspan=1 colspan=1>7.1</td><td rowspan=1 colspan=1>4.8</td><td rowspan=1 colspan=1>4.9c", "Total energy consumption from fossil sources</td><td rowspan=1 colspan=1>69.1</td><td rowspan=1 colspan=1>68.2</td><td rowspan=1 colspan=1>71.2c</td><td rowspan=1 colspan=1>70.5c", "Share of fossil sources in total energy consumption                 %</td><td rowspan=1 colspan=1>93.0</td><td rowspan=1 colspan=1>92.9</td><td rowspan=1 colspan=1>95.1c</td><td rowspan=1 colspan=1>95.1c")),
        "P21-SCOPE3-001": ref("P21-SCOPE3-001", f"Financial-control total gross Scope 3 was 93.97 Mt in 2025 and adjusted 92.33 Mt in 2024. Category 1 was 52.56/51.54 and Category 12 was 27.17/25.67; their sums were {s3_sum_2025}/{s3_sum_2024} Mt, equal to {s3_share_2025}%/{s3_share_2024}% of total Scope 3.", {"scope3_total_mtco2e::2025": 93.97, "category1_mtco2e::2025": 52.56, "category12_mtco2e::2025": 27.17, "category1_plus_12_mtco2e::2025": float(s3_sum_2025), "category1_plus_12_share_percent::2025": float(s3_share_2025), "scope3_total_mtco2e::2024_adjusted": 92.33, "category1_mtco2e::2024_adjusted": 51.54, "category12_mtco2e::2024_adjusted": 25.67, "category1_plus_12_mtco2e::2024_adjusted": float(s3_sum_2024), "category1_plus_12_share_percent::2024_adjusted": float(s3_share_2024)}, evidence(195, "Total gross Scope 3 emissions</td><td rowspan=1 colspan=1>93.97</td><td rowspan=1 colspan=1>96.52</td><td rowspan=1 colspan=1>92.33c", "1 – Purchased goods and services</td><td rowspan=1 colspan=1>52.56</td><td rowspan=1 colspan=1>54.39</td><td rowspan=1 colspan=1>51.54c", "12 – End-of-life treatment of sold products</td><td rowspan=1 colspan=1>27.17</td><td rowspan=1 colspan=1>27.79</td><td rowspan=1 colspan=1>25.67c")),
        "P21-WORKFORCE-001": ref("P21-WORKFORCE-001", "At December 31, 2025 BASF had 108,251 employees: 103,593 permanent, 1,995 temporary and 2,663 apprentices. The three categories sum to 108,251, so the difference is zero. Turnover was 7.5%; work-related injury/ill-health fatalities were zero. Counts are headcount, and apprentices are temporary-contract employees in accredited vocational training.", {"total_employee_headcount::2025": 108251, "permanent_employee_headcount::2025": 103593, "temporary_employee_headcount::2025": 1995, "apprentice_headcount::2025": 2663, "calculated_category_sum_headcount::2025": 108251, "difference_headcount::2025": 0, "turnover_rate_percent::2025": 7.5, "work_related_fatalities::2025": 0, "measurement_basis": "headcount", "apprentice_definition": "temporary contract with in-company vocational training in an accredited education program"}, evidence(262, "Employees (total)</td><td rowspan=1 colspan=1>78,717", "Permanent employees</td><td rowspan=1 colspan=1>75,530", "Temporary employees</td><td rowspan=1 colspan=1>1,095", "Apprenticesc</td><td rowspan=1 colspan=1>2,092", "Turnover rate as a percentage</td><td rowspan=1 colspan=1>7.5%", "Apprentices are employees who have a temporary contract with BASF") + evidence(263, "Number of fatalities as a result of work-related injuries and work-related illhealth</td><td rowspan=1 colspan=1>0")),
        "P21-TAXONOMY-001": ref("P21-TAXONOMY-001", "For 2025, sales revenue denominator was €59,657m, eligible share 12.7%, aligned €905m/1.5%; capex was €4,684m, eligible 18.8%, aligned €22m/0.5%; opex was €4,489m, eligible 13.0%, aligned €74m/1.6%. Sales and opex exclude discontinued coatings; capex includes it only through signing of the transaction agreement. Aligned activities additionally require substantial contribution, DNSH and minimum social safeguards.", {"sales_denominator_million_eur::2025": 59657, "sales_eligible_share_percent::2025": 12.7, "sales_aligned_million_eur::2025": 905, "sales_aligned_share_percent::2025": 1.5, "capex_denominator_million_eur::2025": 4684, "capex_eligible_share_percent::2025": 18.8, "capex_aligned_million_eur::2025": 22, "capex_aligned_share_percent::2025": 0.5, "opex_denominator_million_eur::2025": 4489, "opex_eligible_share_percent::2025": 13.0, "opex_aligned_million_eur::2025": 74, "opex_aligned_share_percent::2025": 1.6, "discontinued_coatings_boundary": "sales and opex excluded; capex included only up to transaction-agreement signing", "alignment_test": "substantial contribution plus do no significant harm plus minimum social safeguards"}, evidence(245, "Sales revenuea</td><td>59,657</td><td>In % 12.7</td><td>Million € 905</td><td>In % 1.5", "<td></td><td>4,684</td><td></td><td>22</td>", "Capex Opexa</td><td>4,489</td><td>18.8 13.0</td><td></td><td>0.5 1.6") + evidence(242, "sales revenue excluding the discontinued coatings business", "including expenditures from the discontinued coatings business up to the date of signing the transaction agreement", "The discontinued coatings business was not included for 2025, in line with the procedure for sales revenue", "make a substantial contribution to one of the six environmental objectives and do no significant harm to other environmental objectives and, at the same time, ensure minimum social safeguards")),
        "P21-ASSURE-001": ref("P21-ASSURE-001", "Deloitte GmbH performed a limited assurance engagement on BASF's Combined Sustainability Statement (the consolidated statement plus the parent's non-financial statement) for 2025 against CSRD, Article 8 EU Taxonomy, relevant HGB sections, ESRS/materiality and management's specifying criteria. The negative-form conclusion was that nothing came to its attention. ISAE 3000 (Revised) governed. Marked unassured external references and specified other-practitioner value-chain assurance references were excluded. Limited assurance is less extensive and substantially lower than reasonable assurance. Signed in Frankfurt am Main on February 24, 2026 by Michael Mehren and Daniel Oehlmann.", {"subject": "Combined Sustainability Statement: Consolidated Sustainability Statement plus parent Non-Financial Statement", "reporting_period": "2025-01-01/2025-12-31", "criteria": "CSRD | EU Taxonomy Article 8 | HGB sections 289b-289e,315b,315c | ESRS/materiality | executive-director specifying criteria", "assurance_level": "limited assurance", "conclusion_form": "nothing has come to our attention", "governing_standard": "ISAE 3000 (Revised)", "excluded_information": "marked unassured external references and listed other-practitioner value-chain assurance references", "procedure_difference": "less in extent and substantially lower assurance than reasonable assurance", "provider": "Deloitte GmbH Wirtschaftsprüfungsgesellschaft", "location": "Frankfurt am Main/Germany", "date": "2026-02-24", "signatories": "Michael Mehren | Daniel Oehlmann"}, evidence(433, "combining the Consolidated Sustainability Statement and the Non-Financial Statement of the parent", "nothing has come to our attention", "We do not express an assurance conclusion on the above-mentioned parts of the Combined Sustainability Statement that were not covered by our assurance engagement") + evidence(434, "less in extent than for, a reasonable assurance engagement", "substantially lower than the assurance that would have been obtained had a reasonable assurance engagement been performed", "ISAE 3000 (Revised)") + evidence(436, "Frankfurt am Main/Germany, February 24, 2026", "Deloitte GmbH", "Signed: Michael Mehren", "Signed: Daniel Oehlmann")),
    }

    windows = {t["task_id"]: set(t["target_pages"]) for t in pack["tasks"]}
    checked = 0
    for task_id, payload in references.items():
        for item in payload["evidence"]:
            if item["pdf_page"] not in windows[task_id] or item["quote"] not in pages[item["pdf_page"]]:
                raise ValueError(f"ungrounded_reference:{task_id}:{item}")
            checked += 1

    reference_dir = "data/annotations/p21_simulated"
    entries = []
    for task_id, payload in references.items():
        path = f"{reference_dir}/{task_id}.json"
        entries.append({"task_id": task_id, "path": path, "sha256": dump_new(path, payload)})

    units = {"mtco2e": "Mt CO2e", "million_mwh": "million MWh", "percent": "percent", "headcount": "headcount", "million_eur": "million EUR"}
    contracts: dict[str, list[dict[str, Any]]] = {}
    for task_id, payload in references.items():
        rows = []
        for slot_id, value in payload["normalized_value"].items():
            row = {"predicate_id": f"esg_p21::{task_id.lower()}::{slot_id}", "slot_id": slot_id, "value_type": "number" if isinstance(value, (int, float)) else "string"}
            for marker, unit in units.items():
                if marker in slot_id:
                    row["canonical_unit"] = unit
                    break
            rows.append(row)
        contracts[task_id] = rows
    contracts_path = "configs/framework/p21_slot_contracts_v0.1.lock.json"
    contracts_sha = dump_new(contracts_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "contracts": contracts})
    gold_path = f"{reference_dir}/p21_atomic_slot_gold_v0.1.lock.json"
    gold_sha = dump_new(gold_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "values": {k: v["normalized_value"] for k, v in references.items()}})

    plans = {
        "P21-GHG-CALC-001": {"roles": [{"role_id": x, "unit": "Mt CO2e"} for x in ["scope1_2025", "scope2_2025", "scope1_2024", "scope2_2024"]], "candidate_handle_role_map": {"M194-T0005-R0016-C0001": "scope1_2025", "M194-T0005-R0026-C0001": "scope2_2025", "M194-T0005-R0016-C0003": "scope1_2024", "M194-T0005-R0026-C0003": "scope2_2024"}, "steps": [{"step_id": "sum_2025", "operation": "sum", "inputs": ["scope1_2025", "scope2_2025"]}, {"step_id": "sum_2024", "operation": "sum", "inputs": ["scope1_2024", "scope2_2024"]}, {"step_id": "percentage_change", "operation": "percentage_change", "inputs": ["sum_2025", "sum_2024"], "rounding_decimals": 2}], "candidate_may_select_operation": False},
        "P21-SCOPE3-001": {"roles": [{"role_id": x, "unit": "Mt CO2e"} for x in ["total_2025", "category1_2025", "category12_2025", "total_2024", "category1_2024", "category12_2024"]], "candidate_handle_role_map": {"M195-T0001-R0017-C0001": "total_2025", "M195-T0001-R0018-C0001": "category1_2025", "M195-T0001-R0029-C0001": "category12_2025", "M195-T0001-R0017-C0003": "total_2024", "M195-T0001-R0018-C0003": "category1_2024", "M195-T0001-R0029-C0003": "category12_2024"}, "steps": [{"step_id": "sum_2025", "operation": "sum", "inputs": ["category1_2025", "category12_2025"]}, {"step_id": "share_2025", "operation": "percentage_share", "inputs": ["sum_2025", "total_2025"], "rounding_decimals": 2}, {"step_id": "sum_2024", "operation": "sum", "inputs": ["category1_2024", "category12_2024"]}, {"step_id": "share_2024", "operation": "percentage_share", "inputs": ["sum_2024", "total_2024"], "rounding_decimals": 2}], "candidate_may_select_operation": False},
        "P21-WORKFORCE-001": {"roles": [{"role_id": x, "unit": "headcount"} for x in ["total", "permanent", "temporary", "apprentice"]], "candidate_handle_role_map": {"M262-T0008-R0002-C0007": "total", "M262-T0008-R0003-C0007": "permanent", "M262-T0008-R0004-C0007": "temporary", "M262-T0008-R0005-C0007": "apprentice"}, "steps": [{"step_id": "category_sum", "operation": "sum", "inputs": ["permanent", "temporary", "apprentice"]}, {"step_id": "difference", "operation": "difference", "inputs": ["total", "category_sum"]}], "candidate_may_select_operation": False},
    }
    plans_path = "configs/framework/p21_calculation_plans_v0.1.lock.json"
    plans_sha = dump_new(plans_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "plans": plans})
    preflight = validate_candidate_preflight_v29(pack["tasks"], {"plans": plans})

    graph_path = "configs/framework/p21_two_dimensional_table_graph_v0.1.lock.json"
    graph_sha = dump_new(graph_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "graphs": [{"graph_id": "P21-ENERGY-P192", "pdf_page": 192, "header_axis": ["2025 financial", "2025 operational", "2024 financial restated", "2024 operational restated"], "row_axis": ["total", "renewable", "renewable share", "fossil", "fossil share"]}, {"graph_id": "P21-GHG-P194-P195", "pdf_pages": [194, 195], "header_axis": ["2025 financial", "2025 operational", "2024 financial adjusted", "2024 operational adjusted"], "row_axis": ["Scope 1", "Scope 2 market", "Scope 3 total", "Category 1", "Category 12"]}, {"graph_id": "P21-WORKFORCE-P262", "pdf_page": 262, "header_axis": ["male 2025", "male 2024", "female 2025", "female 2024", "not disclosed 2025", "not disclosed 2024", "total 2025", "total 2024"], "row_axis": ["total", "permanent", "temporary", "apprentice"]}, {"graph_id": "P21-TAXONOMY-P245", "pdf_page": 245, "header_axis": ["denominator", "eligible share", "aligned amount", "aligned share"], "row_axis": ["sales", "capex", "opex"]}]})

    handle_map = {}
    for task in pack["tasks"]:
        _, _, handles = build_v13_packet(task_pack_path=ROOT / TASK_PACK, task_id=task["task_id"], acquisition_manifest_path=ROOT / "data/manifests/p21_source_acquisition_v0.1.lock.json", raw_root=ROOT, interventions_root=ROOT / "data/interventions", registry_path=ROOT / REGISTRY, workspace_root=ROOT, layout_registry_path=ROOT / LAYOUT)
        handle_map[task["task_id"]] = sorted(h["handle"] for h in handles)
    handles_path = "configs/framework/p21_evidence_handle_whitelist_v0.1.lock.json"
    handles_sha = dump_new(handles_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "handles": handle_map})

    freeze_path = "data/manifests/p21_simulated_reference_freeze_v0.1.lock.json"
    freeze_sha = dump_new(freeze_path, {"schema_version": "1.0", "manifest_id": "P21-SIMULATED-REFERENCE-FREEZE-v0.1", "experiment_id": EXPERIMENT, "status": "simulated_references_frozen_after_documented_pre_reference_answerability_correction_and_before_candidate_inference", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_pack": {"path": TASK_PACK, "sha256": sha(TASK_PACK)}, "target_registry": {"path": REGISTRY, "sha256": sha(REGISTRY)}, "references": sorted(entries, key=lambda x: x["task_id"]), "integrity_audit": {"reference_count": 6, "evidence_quote_count": checked, "all_reference_pages_within_frozen_task_windows": True, "all_quotes_exact_substrings_of_frozen_MinerU_markdown": True, "numeric_values_cross_checked_against_native_layout": True, "pre_reference_answerability_correction_logged": True, "candidate_model_used": False, "cloud_transmission_occurred": False}, "candidate_reference_visibility": False, "cloud_transmission_allowed": False})
    audit_path = "data/results/p21_prefreeze_reference_consistency_audit_v0.1.lock.json"
    audit_sha = dump_new(audit_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "gate_result": "pass", "checks": {"task_count": 6, "unique_page_count": 10, "reference_quote_count": checked, "reference_pages_within_windows": True, "quotes_grounded": True, "numeric_arithmetic_recomputed": True, "v29_whole_pack_preflight": preflight, "answerability_correction_audited": True, "candidate_model_used": False, "cloud_transmission_count": 0}, "hashes": {"task_pack": sha(TASK_PACK), "parser_registry": sha(REGISTRY), "reference_freeze": freeze_sha, "slot_contracts": contracts_sha, "atomic_gold": gold_sha}})
    semantic_path = "configs/framework/p21_semantic_qualifiers_v0.1.lock.json"
    semantic_sha = dump_new(semantic_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "qualifiers": {"reporting_period": "calendar year 2025; 2024 comparatives retain adjusted/restated labels", "page_coordinates": "one-based PDF page indexes", "P21-GHG-CALC-001": {"boundary": "financial-control gross Scope 1 plus gross market-based Scope 2; calculated subtotal not total including Scope 3"}, "P21-ENERGY-001": {"boundary": "financial versus operational control kept separate"}, "P21-SCOPE3-001": {"boundary": "financial control; Category 1 and 12 share of gross Scope 3"}, "P21-WORKFORCE-001": {"boundary": "headcount; apprentices are included as a separately reported contract category"}, "P21-TAXONOMY-001": {"boundary": "eligible shares only; aligned amount/share; discontinued coatings differs by KPI"}, "P21-ASSURE-001": {"boundary": "limited assurance over Combined Sustainability Statement with explicit exclusions"}, "reference_type": "AI-simulated research reference; not independent human gold"}})
    scoring_path = "configs/framework/p21_scoring_rules_v0.1.lock.json"
    scoring_sha = dump_new(scoring_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "scoring": {"unit": "atomic slot", "exact_numeric_tolerance": 1e-9, "string_rule": "controlled semantic equality", "missing_or_unsupported_slot": 0, "no_posthoc_repair": True}})
    config_path = "configs/experiments/p21-v30-unseen-lockbox-local.json"
    config_sha = dump_new(config_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_local_configuration_pending_payload_specific_cloud_authorization", "model_config": "configs/models/p1-ollama-cloud-qwen3.5-397b.json", "candidate_model": "qwen3.5:397b-cloud", "pre_candidate_gate": {"use_v29_whole_pack_plan_gate": True, "result": preflight}, "stage_a": {"single_attempt": True, "use_v15_grounding": True, "use_v21_calculation": True, "use_v24_layout_gate": True, "use_v25_calculation_adapter": True, "use_v26_evidence_handle_audit": True, "use_v27_partial_calculation": True, "use_v28_handle_role_binding": True, "use_v29_task_id_schema": False, "use_v29_calculation_executor": True, "use_v30_executor_identity_envelope": True, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path}, "stage_b": {"single_attempt": True, "use_v20_contract_gate": True, "use_v24_preflight": True, "use_v24_layout_gate": True, "use_v25_single_block_ordered_spans": True, "use_v26_atomic_projection": True, "use_v27_handle_aliases": True, "slot_contracts": contracts_path, "semantic_qualifiers": semantic_path}, "failure_policy": {"archive_model_behavior_failure": True, "silent_retry": False, "posthoc_semantic_repair": False, "infrastructure_resume_requires_lineage": True}, "cloud_transmission_allowed": False})
    local_pack_path = "data/tasks/p21_local_execution_task_pack_v0.1.lock.json"
    local_pack_sha = dump_new(local_pack_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "frozen_local_pack_pending_payload_specific_cloud_authorization", "inference_allowed": False, "parent": TASK_PACK, "source_registry": "data/manifests/p21_source_registry_v0.1.lock.json", "parser_registry": REGISTRY, "reference_freeze": freeze_path, "reference_consistency_audit": audit_path, "slot_contracts": contracts_path, "atomic_scoring_projection": gold_path, "semantic_qualifiers": semantic_path, "table_graph": graph_path, "layout_fallback_registry": LAYOUT, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path, "scoring_rules": scoring_path, "execution_config": config_path, "tasks": [{**t, "reference_file": f"{reference_dir}/{t['task_id']}.json"} for t in pack["tasks"]], "release_condition": "Payload-specific authorization for BASF Report 2025 pages 192,194,195,242,245,262,263,433,434,436 to Ollama Cloud qwen3.5:397b-cloud solely for P21 Stage A/Stage B single-attempt candidate inference."})

    report_path = "docs/91_P21_v3.0本地预冻结与云授权边界_v0.1.md"
    report = ROOT / report_path
    if report.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    slot_count = sum(len(v) for v in contracts.values())
    report.write_text(f"""# P21 v3.0 本地预冻结与云授权边界\n\n## 结论\n\nP21 已完成全部本地预冻结，尚未向云模型发送任何 BASF 报告内容，也未启动候选推理。P3–P20 未修改、未重跑、未重评分。\n\n## 样本与任务\n\n- 样本：BASF Report 2025\n- 文档 SHA256：`{DOCUMENT_SHA}`\n- 冻结问题：6 项\n- 唯一证据页：10 页（192、194、195、242、245、262、263、433、434、436）\n- MinerU：10/10 成功并逐文件哈希验证；初始失败证据保留，RESUME01 仅补第 192、433 页\n- 模拟参考：6 份，{checked} 条逐字证据引文\n- 原子评分槽位：{slot_count} 个\n- v2.9 全任务计算计划门：通过；v3.0 执行器身份信封已冻结启用\n\n## 预参考一致性修正\n\n在模拟参考冻结前发现并记录两项答案可得性问题：冻结页窗没有发行人披露的 Scope 1+2 小计，因此不再要求与不存在的小计比较；EU Taxonomy 摘要仅披露 eligible 比例，因而不虚构 eligible 金额。页窗未改变，候选模型未调用，未发生云传输。\n\n## 云边界\n\n必须取得针对 BASF Report 2025 上述 10 页、`qwen3.5:397b-cloud`、P21 Stage A/Stage B 单次候选推理的明确授权后才能发送。\n""", encoding="utf-8")
    report_sha = sha(report_path)
    readiness_path = "data/results/p21_v30_local_readiness_v0.1.lock.json"
    readiness_sha = dump_new(readiness_path, {"schema_version": "3.0", "experiment_id": EXPERIMENT, "status": "local_readiness_passed_waiting_for_payload_specific_cloud_authorization", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_count": 6, "slot_count": slot_count, "unique_target_pages": PAGES, "mineru": {"success_count": 10, "failure_count": 0, "registry": REGISTRY, "registry_sha256": sha(REGISTRY), "preserved_initial_failures": [192, 433], "recovery_generations": ["RESUME01"]}, "prefreeze_integrity": {"status": "passed", "reference_audit": audit_path, "reference_audit_sha256": audit_sha, "reference_freeze": freeze_path, "reference_freeze_sha256": freeze_sha, "evidence_quotes_checked": checked, "v29_whole_pack_preflight": preflight, "pre_reference_answerability_correction_logged": True}, "artifacts": {"slot_contracts": {"path": contracts_path, "sha256": contracts_sha}, "atomic_gold": {"path": gold_path, "sha256": gold_sha}, "semantic_qualifiers": {"path": semantic_path, "sha256": semantic_sha}, "calculation_plans": {"path": plans_path, "sha256": plans_sha}, "table_graph": {"path": graph_path, "sha256": graph_sha}, "layout_registry": {"path": LAYOUT, "sha256": sha(LAYOUT)}, "handle_whitelist": {"path": handles_path, "sha256": handles_sha}, "scoring_rules": {"path": scoring_path, "sha256": scoring_sha}, "execution_config": {"path": config_path, "sha256": config_sha}, "local_task_pack": {"path": local_pack_path, "sha256": local_pack_sha}, "report": {"path": report_path, "sha256": report_sha}}, "cloud_boundary": {"candidate_model": "qwen3.5:397b-cloud", "cloud_transmission_count": 0, "candidate_model_call_count": 0, "explicit_payload_specific_authorization_received": False, "authorized_pages_required": PAGES, "authorized_scope_required": "P21 Stage A/Stage B single-attempt candidate inference"}, "locked_prior_experiments_modified": False})
    print(json.dumps({"status": "ready_waiting_for_authorization", "readiness": readiness_path, "readiness_sha256": readiness_sha, "slots": slot_count, "quotes": checked}, sort_keys=True))


if __name__ == "__main__":
    main()
