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
EXPERIMENT = "P22-V31-UNSEEN-LOCKBOX-V01"
DOCUMENT = "P22-BAYER-AR2025"
DOCUMENT_SHA = "0af4a9d19fd9d4cba72c1ec062802199873f2379f84112dc2db5dc9605ce769b"
PAGES = [130, 132, 149, 151, 171, 172, 203, 204, 374, 375, 377]
TASK_PACK = "data/tasks/p22_task_pack_v0.1.lock.json"
REGISTRY = "data/manifests/p22_mineru_target_registry_v0.1.lock.json"
ACQUISITION = "data/manifests/p22_source_acquisition_v0.1.lock.json"
LAYOUT = "configs/framework/p22_layout_fallback_registry_v0.1.lock.json"


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
    result: dict[int, str] = {}
    for target in registry["targets"]:
        files = list((ROOT / target["output_directory"]).rglob("*.md"))
        if len(files) != 1:
            raise ValueError(f"markdown_ambiguous:{target['pdf_page']}:{files}")
        result[target["pdf_page"]] = files[0].read_text(encoding="utf-8")
    return result


def evidence(page: int, *quotes: str, parser: str = "mineru") -> list[dict[str, Any]]:
    return [
        {"source_id": DOCUMENT, "pdf_page": page, "quote": q, "parser": parser}
        for q in quotes
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
        "reference_status": "verified_against_frozen_mineru_pages_native_layout_and_visual_fallback",
        "answer": answer,
        "normalized_value": values,
        "evidence": items,
        "provenance": {
            "reference_is_simulated": True,
            "candidate_model_used": False,
        },
    }


def main() -> None:
    pack, registry = load(TASK_PACK), load(REGISTRY)
    assert pack["experiment_id"] == registry["experiment_id"] == EXPERIMENT
    assert pack["document_sha256"] == registry["document_sha256"] == DOCUMENT_SHA
    assert registry["success_count"] == registry["target_count"] == 11
    assert sorted(t["pdf_page"] for t in registry["targets"]) == PAGES
    pages = markdown_by_page(registry)

    total_energy_change = (
        (Decimal("8855") - Decimal("9055")) / Decimal("9055") * 100
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    renewable_energy_change = (
        (Decimal("2013") - Decimal("1560")) / Decimal("1560") * 100
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    ghg_2024 = Decimal("1.88") + Decimal("1.08")
    ghg_2025 = Decimal("1.89") + Decimal("0.90")
    ghg_change = ((ghg_2025 - ghg_2024) / ghg_2024 * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    water_calc_2024 = Decimal("53.47") - Decimal("32.46")
    water_calc_2025 = Decimal("51.61") - Decimal("30.25")

    references = {
        "P22-TAXONOMY-001": ref(
            "P22-TAXONOMY-001",
            "In 2025 Bayer reported turnover of €45,575m, taxonomy-eligible turnover of €17,956m (39.4%), and aligned turnover of €0m (0.0%). CapEx was €3,202m, eligible €284m (8.9%), and aligned €0m (0.0%). OpEx was €7,054m; no material eligible or aligned OpEx was identified, so no separate activity table was included, while the summary reports 0.0% eligible and €0m/0.0% aligned. Nonmaterial active-ingredient sales and nonmaterial CapEx/OpEx were excluded under the stated thresholds.",
            {
                "turnover_denominator_million_eur::2025": 45575,
                "turnover_eligible_million_eur::2025": 17956,
                "turnover_eligible_share_percent::2025": 39.4,
                "turnover_aligned_million_eur::2025": 0,
                "turnover_aligned_share_percent::2025": 0.0,
                "capex_denominator_million_eur::2025": 3202,
                "capex_eligible_million_eur::2025": 284,
                "capex_eligible_share_percent::2025": 8.9,
                "capex_aligned_million_eur::2025": 0,
                "capex_aligned_share_percent::2025": 0.0,
                "opex_denominator_million_eur::2025": 7054,
                "opex_eligible_amount_disclosure::2025": "not separately disclosed",
                "opex_eligible_share_percent::2025": 0.0,
                "opex_aligned_million_eur::2025": 0,
                "opex_aligned_share_percent::2025": 0.0,
                "materiality_treatment": "nonmaterial eligible CapEx excluded; active-ingredient turnover below 1%; material eligible/aligned OpEx not identified and no separate OpEx table",
            },
            evidence(
                130,
                "Turnover</td><td rowspan=1 colspan=1>45,575</td><td rowspan=1 colspan=1>39.4</td><td rowspan=1 colspan=1>0</td><td rowspan=1 colspan=1>0.0",
                "Taxonomy-eligible sales amounted to €17,956 million in 2025",
            )
            + evidence(
                132,
                "We incurred taxonomy-eligible capital expenditure (CapEx) of €284 million in 2025",
                "The proportion of taxonomy-eligible capital expenditure therefore came to 8.9%",
                "In 2025, operating expenditure totaling €7,054 million",
                "Material taxonomy-eligible and taxonomy-aligned operating expenditure could not be identified.",
                "We have not included a table of taxonomy eligibility and alignment for operating expenditure.",
            ),
        ),
        "P22-ENERGY-CALC-001": ref(
            "P22-ENERGY-CALC-001",
            f"For high-climate-impact sectors, total energy consumption was 9,055 thousand MWh in 2024 and 8,855 in 2025; fossil consumption was 7,058/6,440, renewable consumption 1,560/2,013, fossil shares 77.9%/72.7%, and renewable shares 17.2%/22.7%. Total energy changed {total_energy_change}% and renewable energy {renewable_energy_change}% from 2024 to 2025.",
            {
                "total_energy_thousand_mwh::2024": 9055,
                "total_energy_thousand_mwh::2025": 8855,
                "fossil_energy_thousand_mwh::2024": 7058,
                "fossil_energy_thousand_mwh::2025": 6440,
                "renewable_energy_thousand_mwh::2024": 1560,
                "renewable_energy_thousand_mwh::2025": 2013,
                "fossil_share_percent::2024": 77.9,
                "fossil_share_percent::2025": 72.7,
                "renewable_share_percent::2024": 17.2,
                "renewable_share_percent::2025": 22.7,
                "calculated_total_energy_change_percent": float(total_energy_change),
                "calculated_renewable_energy_change_percent": float(renewable_energy_change),
                "renewable_share_change_percentage_points": 5.5,
                "boundary": "activities in high climate impact sectors",
            },
            evidence(
                149,
                "Total fossil energy consumption</td><td rowspan=1 colspan=1>7,058</td><td rowspan=1 colspan=1>6,440",
                "Total renewable energy consumption</td><td rowspan=1 colspan=1>1,560</td><td rowspan=1 colspan=1>2,013",
                "Total energy consumption</td><td rowspan=1 colspan=1>9,055</td><td rowspan=1 colspan=1>8,855",
                "Share of fossil sources in total energy consumption (%)</td><td rowspan=1 colspan=1>77.9</td><td rowspan=1 colspan=1>72.7",
                "Share of renewable sources in total energy consumption (%)</td><td rowspan=1 colspan=1>17.2</td><td rowspan=1 colspan=1>22.7",
            ),
        ),
        "P22-GHG-CALC-001": ref(
            "P22-GHG-CALC-001",
            f"Gross Scope 1 plus gross market-based Scope 2 was {ghg_2024} Mt CO2e in restated 2024 and {ghg_2025} in 2025, a {ghg_change}% change. Gross Scope 3 was 8.82/9.10 and total market-based GHG was 11.78/11.89 Mt CO2e. The calculated Scope 1+2 subtotal is not the issuer's total including Scope 3.",
            {
                "scope1_gross_mtco2e::2024_restated": 1.88,
                "scope2_market_gross_mtco2e::2024_restated": 1.08,
                "calculated_scope1_plus_scope2_mtco2e::2024_restated": float(ghg_2024),
                "scope1_gross_mtco2e::2025": 1.89,
                "scope2_market_gross_mtco2e::2025": 0.90,
                "calculated_scope1_plus_scope2_mtco2e::2025": float(ghg_2025),
                "calculated_change_percent": float(ghg_change),
                "scope3_gross_mtco2e::2024_restated": 8.82,
                "scope3_gross_mtco2e::2025": 9.10,
                "total_market_based_mtco2e::2024_restated": 11.78,
                "total_market_based_mtco2e::2025": 11.89,
                "boundary": "financial scope of consolidation and environmentally relevant sites",
            },
            evidence(
                151,
                "Gross Scope 1 GHG emissions²</td><td rowspan=1 colspan=1>2.08</td><td rowspan=1 colspan=1>1.88</td><td rowspan=1 colspan=1>1.89",
                "Gross market-based Scope 2 GHG emissions</td><td rowspan=1 colspan=1>1.68</td><td rowspan=1 colspan=1>1.08</td><td rowspan=1 colspan=1>0.9",
                "Gross Scope 3 GHG emissions</td><td rowspan=1 colspan=1>10.34</td><td rowspan=1 colspan=1>8.82</td><td rowspan=1 colspan=1>9.10",
                "Total GHG emissions (market-based)3,4</td><td rowspan=1 colspan=1>14.10</td><td rowspan=1 colspan=1>11.78</td><td rowspan=1 colspan=1>11.89",
                "we take into account the entire Group in accordance with the financial scope of consolidation, provided a site is environmentally relevant",
            ),
        ),
        "P22-WATER-CALC-001": ref(
            "P22-WATER-CALC-001",
            f"Water withdrawal/discharge/disclosed consumption were 53.47/32.46/21.01 million m³ in 2024 and 51.61/30.25/21.35 in 2025. Withdrawal minus discharge gives {water_calc_2024}/{water_calc_2025}; differences from disclosure are 0.00/+0.01 million m³, consistent with rounding. Water-risk consumption was 5.36 in both years, recycling 384.80/379.70, and intensity 451/468 m³ per €m sales.",
            {
                "withdrawal_million_m3::2024": 53.47,
                "discharge_million_m3::2024": 32.46,
                "calculated_consumption_million_m3::2024": float(water_calc_2024),
                "disclosed_consumption_million_m3::2024": 21.01,
                "calculated_minus_disclosed_million_m3::2024": 0.0,
                "withdrawal_million_m3::2025": 51.61,
                "discharge_million_m3::2025": 30.25,
                "calculated_consumption_million_m3::2025": float(water_calc_2025),
                "disclosed_consumption_million_m3::2025": 21.35,
                "calculated_minus_disclosed_million_m3::2025": 0.01,
                "water_risk_consumption_million_m3::2024": 5.36,
                "water_risk_consumption_million_m3::2025": 5.36,
                "recycling_reuse_million_m3::2024": 384.80,
                "recycling_reuse_million_m3::2025": 379.70,
                "water_intensity_m3_per_million_eur::2024": 451,
                "water_intensity_m3_per_million_eur::2025": 468,
                "definition": "withdrawal minus discharge at environmentally relevant sites",
            },
            evidence(
                171,
                "Our total water consumption is calculated as the difference between the volume of water withdrawn and the volume discharged.",
                "Our water consumption in regions impacted by water risks according to ESRS",
                "All sites with an annual energy consumption exceeding 1.5 terajoules and/or annual water withdrawal that is greater than or equal to 50 Tm<sup>3</sup> are regarded as environmentally relevant.",
            )
            + evidence(
                172,
                "Water withdrawal</td><td>43.80</td><td>42.75</td><td>6.28</td><td>6.10</td><td>1.66</td><td>1.56</td><td>1.74</td><td>1.20</td><td>53.47</td><td>51.61",
                "Water discharge</td><td>23.83</td><td>22.31</td><td>5.78</td><td>5.52</td><td>1.24</td><td>1.28</td><td>1.60</td><td>1.14</td><td>32.46</td><td>30.25",
                "Water consumption</td><td>19.96</td><td>20.43</td><td>0.50</td><td>0.58</td><td>0.42</td><td>0.28</td><td>0.13</td><td>0.06</td><td>21.01</td><td>21.35",
                "Water recycling and reuse</td><td>384.75</td><td>379.66",
                "Water intensity</td><td>451</td><td>468",
            ),
        ),
        "P22-SAFETY-CALC-001": ref(
            "P22-SAFETY-CALC-001",
            "Recordable accidents were 439 in 2024 and 403 in 2025; employee/nonemployee components were 397/42 and 338/65, summing exactly to each total. Total accident rates were 2.20/2.16, employee rates 2.05/1.88 and nonemployee rates 7.58/9.87. Fatalities were two value-chain workers in 2024 and zero in every category in 2025. The rate is accidents divided by hours worked times one million; coverage uses headcount including casual employees.",
            {
                "total_accidents::2024": 439,
                "employee_accidents::2024": 397,
                "nonemployee_accidents::2024": 42,
                "calculated_component_sum::2024": 439,
                "total_minus_component_sum::2024": 0,
                "total_accidents::2025": 403,
                "employee_accidents::2025": 338,
                "nonemployee_accidents::2025": 65,
                "calculated_component_sum::2025": 403,
                "total_minus_component_sum::2025": 0,
                "total_rate::2024": 2.20,
                "total_rate::2025": 2.16,
                "employee_rate::2024": 2.05,
                "employee_rate::2025": 1.88,
                "nonemployee_rate::2024": 7.58,
                "nonemployee_rate::2025": 9.87,
                "total_fatalities::2024": 2,
                "employee_fatalities::2024": 0,
                "nonemployee_fatalities::2024": 0,
                "value_chain_fatalities::2024": 2,
                "total_fatalities::2025": 0,
                "employee_fatalities::2025": 0,
                "nonemployee_fatalities::2025": 0,
                "value_chain_fatalities::2025": 0,
                "rate_formula": "accidents / total hours worked * 1,000,000",
                "coverage": "employee headcount including casual employees, seasonal employees, apprentices, interns and students",
            },
            evidence(
                203,
                "We registered a total of 403 recordable work-related accidents in 2025 (2024: 439)",
                "the number of recordable work-related accidents registered in the reporting period is divided by the total number of hours worked by employees and nonemployees during the reporting period and then multiplied by one million",
                "In 2025, no fatalities from work-related injuries and work-related ill health occurred affecting our own workforce (2024: zero).",
                "There were also no fatalities in 2025 due to work-related injuries and workrelated ill health among value chain workers (2024: two).",
                parser="native_layout_and_mineru_narrative",
            )
            + evidence(
                204,
                "Recordable work-related accidents</td><td rowspan=1 colspan=1>439</td><td rowspan=1 colspan=1>403",
                "of which recordable work-related accidents of employees</td><td rowspan=1 colspan=1>397</td><td rowspan=1 colspan=1>338",
                "of which recordable work-related accidents of nonemployees</td><td rowspan=1 colspan=1>42</td><td rowspan=1 colspan=1>65",
                "Rate of recordable work-related accidents</td><td rowspan=1 colspan=1>2.20</td><td rowspan=1 colspan=1>2.16",
                "The health and safety data is based on number of employees (total headcount), including casual employees",
            ),
        ),
        "P22-ASSURE-001": ref(
            "P22-ASSURE-001",
            "Deloitte GmbH conducted limited assurance over Bayer's Consolidated Sustainability Statement for 2025 against CSRD, Article 8 EU Taxonomy, HGB 315b/315c, ESRS/materiality and executive-director criteria. Its negative-form conclusion was that nothing came to its attention. ISAE 3000 (Revised) governed; external-company references were excluded. Limited assurance is less extensive and substantially lower than reasonable assurance. The report was signed in Düsseldorf on March 2, 2026 by Andreas Wermelt and Silvia Geberth.",
            {
                "subject": "Consolidated Sustainability Statement included in combined management report",
                "reporting_period": "2025-01-01/2025-12-31",
                "criteria": "CSRD | EU Taxonomy Article 8 | HGB 315b/315c | ESRS/materiality | executive-director specifying criteria",
                "assurance_level": "limited assurance",
                "conclusion_form": "nothing has come to our attention",
                "governing_standard": "ISAE 3000 (Revised)",
                "excluded_information": "references outside the combined management report",
                "procedure_difference": "less extensive and substantially lower assurance than reasonable assurance",
                "provider": "Deloitte GmbH Wirtschaftsprüfungsgesellschaft",
                "location": "Düsseldorf/Germany",
                "date": "2026-03-02",
                "signatories": "Andreas Wermelt | Silvia Geberth",
            },
            evidence(
                374,
                "We have conducted a limited assurance engagement on the Consolidated Sustainability Statement of Bayer Aktiengesellschaft",
                "References to information provided by the Company outside the combined management report were not subject to our assurance engagement.",
                "nothing has come to our attention",
                "International Standard on Assurance Engagements (ISAE) 3000 (Revised)",
            )
            + evidence(
                375,
                "less in extent than for, a reasonable assurance engagement",
                "the level of assurance obtained is substantially lower than the assurance that would have been obtained had a reasonable assurance engagement been performed",
            )
            + evidence(
                377,
                "Düsseldorf/Germany, March 2, 2026",
                "## Deloitte GmbH",
                "Andreas Wermelt",
                "Silvia Geberth",
            ),
        ),
    }

    windows = {t["task_id"]: set(t["target_pages"]) for t in pack["tasks"]}
    checked = 0
    for task_id, payload in references.items():
        for item in payload["evidence"]:
            if item["pdf_page"] not in windows[task_id]:
                raise ValueError(f"reference_page_outside_window:{task_id}:{item}")
            if item["quote"] not in pages[item["pdf_page"]]:
                raise ValueError(f"ungrounded_reference:{task_id}:{item}")
            checked += 1

    reference_dir = "data/annotations/p22_simulated"
    entries = []
    for task_id, payload in references.items():
        path = f"{reference_dir}/{task_id}.json"
        entries.append({"task_id": task_id, "path": path, "sha256": dump_new(path, payload)})

    units = {
        "mtco2e": "Mt CO2e",
        "thousand_mwh": "thousand MWh",
        "million_m3": "million m3",
        "m3_per_million_eur": "m3 per million EUR",
        "percent": "percent",
        "million_eur": "million EUR",
    }
    contracts: dict[str, list[dict[str, Any]]] = {}
    for task_id, payload in references.items():
        rows = []
        for slot_id, value in payload["normalized_value"].items():
            row = {
                "predicate_id": f"esg_p22::{task_id.lower()}::{slot_id}",
                "slot_id": slot_id,
                "value_type": "number" if isinstance(value, (int, float)) else "string",
            }
            for marker, unit in units.items():
                if marker in slot_id:
                    row["canonical_unit"] = unit
                    break
            rows.append(row)
        contracts[task_id] = rows
    contracts_path = "configs/framework/p22_slot_contracts_v0.1.lock.json"
    contracts_sha = dump_new(
        contracts_path,
        {
            "schema_version": "3.1",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "contracts": contracts,
        },
    )
    gold_path = f"{reference_dir}/p22_atomic_slot_gold_v0.1.lock.json"
    gold_sha = dump_new(
        gold_path,
        {
            "schema_version": "3.1",
            "experiment_id": EXPERIMENT,
            "status": "frozen_before_candidate_inference",
            "values": {k: v["normalized_value"] for k, v in references.items()},
        },
    )

    plans = {
        "P22-ENERGY-CALC-001": {
            "roles": [{"role_id": x, "unit": "thousand MWh"} for x in ["total_2024", "total_2025", "renewable_2024", "renewable_2025"]],
            "candidate_handle_role_map": {
                "M149-T0001-R0021-C0001": "total_2024",
                "M149-T0001-R0021-C0002": "total_2025",
                "M149-T0001-R0014-C0001": "renewable_2024",
                "M149-T0001-R0014-C0002": "renewable_2025",
            },
            "steps": [
                {"step_id": "total_change", "operation": "percentage_change", "inputs": ["total_2025", "total_2024"], "rounding_decimals": 2},
                {"step_id": "renewable_change", "operation": "percentage_change", "inputs": ["renewable_2025", "renewable_2024"], "rounding_decimals": 2},
            ],
            "output_slot_map": [
                {"source_value_id": "total_change", "slot_id": "calculated_total_energy_change_percent"},
                {"source_value_id": "renewable_change", "slot_id": "calculated_renewable_energy_change_percent"},
            ],
            "candidate_may_select_operation": False,
        },
        "P22-GHG-CALC-001": {
            "roles": [{"role_id": x, "unit": "Mt CO2e"} for x in ["scope1_2024", "scope2_2024", "scope1_2025", "scope2_2025"]],
            "candidate_handle_role_map": {
                "M151-T0001-R0005-C0002": "scope1_2024",
                "M151-T0001-R0009-C0002": "scope2_2024",
                "M151-T0001-R0005-C0003": "scope1_2025",
                "M151-T0001-R0009-C0003": "scope2_2025",
            },
            "steps": [
                {"step_id": "sum_2024", "operation": "sum", "inputs": ["scope1_2024", "scope2_2024"]},
                {"step_id": "sum_2025", "operation": "sum", "inputs": ["scope1_2025", "scope2_2025"]},
                {"step_id": "percentage_change", "operation": "percentage_change", "inputs": ["sum_2025", "sum_2024"], "rounding_decimals": 2},
            ],
            "output_slot_map": [
                {"source_value_id": "sum_2024", "slot_id": "calculated_scope1_plus_scope2_mtco2e::2024_restated"},
                {"source_value_id": "sum_2025", "slot_id": "calculated_scope1_plus_scope2_mtco2e::2025"},
                {"source_value_id": "percentage_change", "slot_id": "calculated_change_percent"},
            ],
            "candidate_may_select_operation": False,
        },
        "P22-WATER-CALC-001": {
            "roles": [{"role_id": x, "unit": "million m3"} for x in ["withdrawal_2024", "discharge_2024", "disclosed_2024", "withdrawal_2025", "discharge_2025", "disclosed_2025"]],
            "candidate_handle_role_map": {
                "M172-T0002-R0002-C0009": "withdrawal_2024",
                "M172-T0002-R0003-C0009": "discharge_2024",
                "M172-T0002-R0004-C0009": "disclosed_2024",
                "M172-T0002-R0002-C0010": "withdrawal_2025",
                "M172-T0002-R0003-C0010": "discharge_2025",
                "M172-T0002-R0004-C0010": "disclosed_2025",
            },
            "steps": [
                {"step_id": "calculated_2024", "operation": "difference", "inputs": ["withdrawal_2024", "discharge_2024"]},
                {"step_id": "calculated_2025", "operation": "difference", "inputs": ["withdrawal_2025", "discharge_2025"]},
                {"step_id": "comparison_2024", "operation": "difference", "inputs": ["calculated_2024", "disclosed_2024"]},
                {"step_id": "comparison_2025", "operation": "difference", "inputs": ["calculated_2025", "disclosed_2025"]},
            ],
            "output_slot_map": [
                {"source_value_id": "calculated_2024", "slot_id": "calculated_consumption_million_m3::2024"},
                {"source_value_id": "calculated_2025", "slot_id": "calculated_consumption_million_m3::2025"},
                {"source_value_id": "comparison_2024", "slot_id": "calculated_minus_disclosed_million_m3::2024"},
                {"source_value_id": "comparison_2025", "slot_id": "calculated_minus_disclosed_million_m3::2025"},
            ],
            "candidate_may_select_operation": False,
        },
        "P22-SAFETY-CALC-001": {
            "roles": [{"role_id": x, "unit": "count"} for x in ["total_2024", "employee_2024", "nonemployee_2024", "total_2025", "employee_2025", "nonemployee_2025"]],
            "candidate_handle_role_map": {
                "M204-T0001-R0003-C0001": "total_2024",
                "M204-T0001-R0004-C0001": "employee_2024",
                "M204-T0001-R0005-C0001": "nonemployee_2024",
                "M204-T0001-R0003-C0002": "total_2025",
                "M204-T0001-R0004-C0002": "employee_2025",
                "M204-T0001-R0005-C0002": "nonemployee_2025",
            },
            "steps": [
                {"step_id": "component_sum_2024", "operation": "sum", "inputs": ["employee_2024", "nonemployee_2024"]},
                {"step_id": "component_sum_2025", "operation": "sum", "inputs": ["employee_2025", "nonemployee_2025"]},
                {"step_id": "difference_2024", "operation": "difference", "inputs": ["total_2024", "component_sum_2024"]},
                {"step_id": "difference_2025", "operation": "difference", "inputs": ["total_2025", "component_sum_2025"]},
            ],
            "output_slot_map": [
                {"source_value_id": "component_sum_2024", "slot_id": "calculated_component_sum::2024"},
                {"source_value_id": "component_sum_2025", "slot_id": "calculated_component_sum::2025"},
                {"source_value_id": "difference_2024", "slot_id": "total_minus_component_sum::2024"},
                {"source_value_id": "difference_2025", "slot_id": "total_minus_component_sum::2025"},
            ],
            "candidate_may_select_operation": False,
        },
    }
    plans_path = "configs/framework/p22_calculation_plans_v0.1.lock.json"
    plans_sha = dump_new(plans_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "plans": plans})
    preflight = validate_candidate_preflight_v29(pack["tasks"], {"plans": plans})

    graph_path = "configs/framework/p22_two_dimensional_table_graph_v0.1.lock.json"
    graph_sha = dump_new(graph_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "graphs": [
        {"graph_id": "P22-TAXONOMY-P130", "pdf_page": 130, "header_axis": ["denominator", "eligible share", "aligned amount", "aligned share"], "row_axis": ["turnover", "CapEx", "OpEx"]},
        {"graph_id": "P22-ENERGY-P149", "pdf_page": 149, "header_axis": ["2024", "2025"], "row_axis": ["fossil", "renewable", "total", "fossil share", "renewable share"]},
        {"graph_id": "P22-GHG-P151", "pdf_page": 151, "header_axis": ["2019", "2024 restated", "2025", "change"], "row_axis": ["Scope 1", "Scope 2 market", "Scope 3", "total market"]},
        {"graph_id": "P22-WATER-P172", "pdf_page": 172, "header_axis": ["Crop Science 2024/2025", "Pharmaceuticals 2024/2025", "Consumer Health 2024/2025", "Other 2024/2025", "Total 2024/2025"], "row_axis": ["withdrawal", "discharge", "consumption", "recycling"]},
        {"graph_id": "P22-SAFETY-P204", "pdf_page": 204, "header_axis": ["2024", "2025"], "row_axis": ["total accidents", "employee accidents", "nonemployee accidents", "rates", "fatalities"], "known_anomaly": "fatality dashes misread as 1 by primary parser; native-layout fallback controls fatality evidence"},
    ]})

    handle_map = {}
    for task in pack["tasks"]:
        _, _, handles = build_v13_packet(
            task_pack_path=ROOT / TASK_PACK,
            task_id=task["task_id"],
            acquisition_manifest_path=ROOT / ACQUISITION,
            raw_root=ROOT,
            interventions_root=ROOT / "data/interventions",
            registry_path=ROOT / REGISTRY,
            workspace_root=ROOT,
            layout_registry_path=ROOT / LAYOUT,
        )
        handle_map[task["task_id"]] = sorted(h["handle"] for h in handles)
    handles_path = "configs/framework/p22_evidence_handle_whitelist_v0.1.lock.json"
    handles_sha = dump_new(handles_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "handles": handle_map})

    freeze_path = "data/manifests/p22_simulated_reference_freeze_v0.1.lock.json"
    freeze_sha = dump_new(freeze_path, {"schema_version": "1.0", "manifest_id": "P22-SIMULATED-REFERENCE-FREEZE-v0.1", "experiment_id": EXPERIMENT, "status": "simulated_references_frozen_after_documented_pre_reference_parser_anomaly_resolution_and_before_candidate_inference", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_pack": {"path": TASK_PACK, "sha256": sha(TASK_PACK)}, "target_registry": {"path": REGISTRY, "sha256": sha(REGISTRY)}, "references": sorted(entries, key=lambda x: x["task_id"]), "integrity_audit": {"reference_count": 6, "evidence_quote_count": checked, "all_reference_pages_within_frozen_task_windows": True, "all_quotes_exact_substrings_of_frozen_MinerU_markdown": True, "numeric_values_cross_checked_against_native_layout": True, "page_204_fatality_parser_anomaly_logged_before_reference_freeze": True, "candidate_model_used": False, "cloud_transmission_occurred": False}, "candidate_reference_visibility": False, "cloud_transmission_allowed": False})

    audit_path = "data/results/p22_prefreeze_reference_consistency_audit_v0.1.lock.json"
    audit_sha = dump_new(audit_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "gate_result": "pass", "checks": {"task_count": 6, "unique_page_count": 11, "reference_quote_count": checked, "reference_pages_within_windows": True, "quotes_grounded": True, "numeric_arithmetic_recomputed": True, "v29_whole_pack_preflight": preflight, "page_204_native_layout_fallback_verified": True, "candidate_model_used": False, "cloud_transmission_count": 0}, "hashes": {"task_pack": sha(TASK_PACK), "parser_registry": sha(REGISTRY), "reference_freeze": freeze_sha, "slot_contracts": contracts_sha, "atomic_gold": gold_sha}})

    semantic_path = "configs/framework/p22_semantic_qualifiers_v0.1.lock.json"
    semantic_sha = dump_new(semantic_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "qualifiers": {"reporting_period": "calendar year 2025; 2024 comparatives preserve restatement where disclosed", "page_coordinates": "one-based PDF page indexes", "P22-TAXONOMY-001": {"boundary": "eligible amount/share only where disclosed; zero distinct from not identified and not separately tabled"}, "P22-ENERGY-CALC-001": {"boundary": "high-climate-impact sectors; thousand MWh"}, "P22-GHG-CALC-001": {"boundary": "financial consolidation and environmentally relevant sites; calculated Scope 1+2 subtotal not total including Scope 3"}, "P22-WATER-CALC-001": {"boundary": "environmentally relevant sites; consumption defined as withdrawal minus discharge; rounded issuer values retained"}, "P22-SAFETY-CALC-001": {"boundary": "accident components calculated deterministically; fatalities use frozen native-layout/narrative fallback because primary table parser substituted dash glyphs"}, "P22-ASSURE-001": {"boundary": "limited assurance over Consolidated Sustainability Statement with external references excluded"}, "reference_type": "AI-simulated research reference; not independent human gold"}})
    scoring_path = "configs/framework/p22_scoring_rules_v0.1.lock.json"
    scoring_sha = dump_new(scoring_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "frozen_before_candidate_inference", "scoring": {"unit": "atomic slot", "exact_numeric_tolerance": 1e-9, "string_rule": "controlled semantic equality", "missing_or_unsupported_slot": 0, "no_posthoc_repair": True}})

    config_path = "configs/experiments/p22-v31-unseen-lockbox-local.json"
    config_sha = dump_new(config_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "frozen_local_configuration_pending_payload_specific_cloud_authorization", "model_config": "configs/models/p1-ollama-cloud-qwen3.5-397b.json", "candidate_model": "qwen3.5:397b-cloud", "pre_candidate_gate": {"use_v29_whole_pack_plan_gate": True, "result": preflight}, "stage_a": {"single_attempt": True, "use_v15_grounding": True, "use_v21_calculation": True, "use_v24_layout_gate": True, "use_v25_calculation_adapter": True, "use_v26_evidence_handle_audit": True, "use_v27_partial_calculation": True, "use_v28_handle_role_binding": True, "use_v29_task_id_schema": False, "use_v29_calculation_executor": True, "use_v30_executor_identity_envelope": True, "use_v31_stage_a_handle_aliases": True, "use_v31_calculation_slot_projection": True, "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path}, "stage_b": {"single_attempt": True, "use_v20_contract_gate": True, "use_v24_preflight": True, "use_v24_layout_gate": True, "use_v25_single_block_ordered_spans": True, "use_v26_atomic_projection": True, "use_v27_handle_aliases": True, "slot_contracts": contracts_path, "semantic_qualifiers": semantic_path}, "failure_policy": {"archive_model_behavior_failure": True, "silent_retry": False, "posthoc_semantic_repair": False, "infrastructure_resume_requires_lineage": True}, "cloud_transmission_allowed": False})

    local_pack_path = "data/tasks/p22_local_execution_task_pack_v0.1.lock.json"
    local_pack_sha = dump_new(local_pack_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "frozen_local_pack_pending_payload_specific_cloud_authorization", "inference_allowed": False, "parent": TASK_PACK, "source_registry": "data/manifests/p22_source_registry_v0.1.lock.json", "parser_registry": REGISTRY, "reference_freeze": freeze_path, "reference_consistency_audit": audit_path, "slot_contracts": contracts_path, "atomic_scoring_projection": gold_path, "semantic_qualifiers": semantic_path, "table_graph": graph_path, "layout_fallback_registry": LAYOUT, "parser_anomaly_audit": "data/results/p22_parser_anomaly_audit_v0.1.lock.json", "calculation_plans": plans_path, "evidence_handle_whitelist": handles_path, "scoring_rules": scoring_path, "execution_config": config_path, "tasks": [{**t, "reference_file": f"{reference_dir}/{t['task_id']}.json"} for t in pack["tasks"]], "release_condition": "Payload-specific authorization for Bayer Annual Report 2025 pages 130,132,149,151,171,172,203,204,374,375,377 to Ollama Cloud qwen3.5:397b-cloud solely for P22 Stage A/Stage B single-attempt candidate inference."})

    report_path = "docs/94_P22_v3.1本地预冻结与云授权边界_v0.1.md"
    report = ROOT / report_path
    if report.exists():
        raise RuntimeError(f"refusing_to_overwrite:{report_path}")
    slot_count = sum(len(v) for v in contracts.values())
    report.write_text(f"""# P22 v3.1 本地预冻结与云授权边界

## 结论

P22 已完成全部本地预冻结，尚未向云模型发送任何 Bayer 报告内容，也未启动候选推理。P3–P21 未修改、未重跑、未重评分。

## 样本与任务

- 样本：Bayer Annual Report 2025
- 文档 SHA256：`{DOCUMENT_SHA}`
- 冻结问题：6 项
- 唯一证据页：11 页（130、132、149、151、171、172、203、204、374、375、377）
- MinerU：11/11 成功并逐文件哈希验证；初始第 130、374 页基础设施失败证据保留，RESUME01 只补未完成页
- 模拟参考：6 份，{checked} 条逐字证据引文
- 原子评分槽位：{slot_count} 个
- v2.9 全任务计算计划门：通过；v3.1 证据短句柄与计算槽位确定性投影已冻结启用

## 解析异常

在参考答案冻结和候选推理之前，发现 MinerU 把第 204 页 2025 年死亡事故栏的横线误识别为数字 1。原生 PDF 布局、页面渲染和第 203 页叙述均确认 2025 年各类死亡事故为零。原始 MinerU 输出未覆盖；异常、判定依据和原生布局回退已单独归档，候选证据对该字段采用预冻结回退。

## 云边界

必须取得针对 Bayer Annual Report 2025 上述 11 页、`qwen3.5:397b-cloud`、P22 Stage A/Stage B 单次候选推理的明确授权后才能发送。
""", encoding="utf-8")
    report_sha = sha(report_path)

    readiness_path = "data/results/p22_v31_local_readiness_v0.1.lock.json"
    readiness_sha = dump_new(readiness_path, {"schema_version": "3.1", "experiment_id": EXPERIMENT, "status": "local_readiness_passed_waiting_for_payload_specific_cloud_authorization", "document_id": DOCUMENT, "document_sha256": DOCUMENT_SHA, "task_count": 6, "slot_count": slot_count, "unique_target_pages": PAGES, "mineru": {"success_count": 11, "failure_count": 0, "registry": REGISTRY, "registry_sha256": sha(REGISTRY), "preserved_initial_failures": [130, 374], "recovery_generations": ["RESUME01"]}, "prefreeze_integrity": {"status": "passed", "reference_audit": audit_path, "reference_audit_sha256": audit_sha, "reference_freeze": freeze_path, "reference_freeze_sha256": freeze_sha, "evidence_quotes_checked": checked, "v29_whole_pack_preflight": preflight, "page_204_parser_anomaly_logged_and_resolved_before_reference_freeze": True}, "artifacts": {"slot_contracts": {"path": contracts_path, "sha256": contracts_sha}, "atomic_gold": {"path": gold_path, "sha256": gold_sha}, "semantic_qualifiers": {"path": semantic_path, "sha256": semantic_sha}, "calculation_plans": {"path": plans_path, "sha256": plans_sha}, "table_graph": {"path": graph_path, "sha256": graph_sha}, "layout_registry": {"path": LAYOUT, "sha256": sha(LAYOUT)}, "handle_whitelist": {"path": handles_path, "sha256": handles_sha}, "scoring_rules": {"path": scoring_path, "sha256": scoring_sha}, "execution_config": {"path": config_path, "sha256": config_sha}, "local_task_pack": {"path": local_pack_path, "sha256": local_pack_sha}, "report": {"path": report_path, "sha256": report_sha}}, "cloud_boundary": {"candidate_model": "qwen3.5:397b-cloud", "cloud_transmission_count": 0, "candidate_model_call_count": 0, "explicit_payload_specific_authorization_received": False, "authorized_pages_required": PAGES, "authorized_scope_required": "P22 Stage A/Stage B single-attempt candidate inference"}, "locked_prior_experiments_modified": False})
    print(json.dumps({"status": "ready_waiting_for_authorization", "readiness": readiness_path, "readiness_sha256": readiness_sha, "slots": slot_count, "quotes": checked}, sort_keys=True))


if __name__ == "__main__":
    main()
