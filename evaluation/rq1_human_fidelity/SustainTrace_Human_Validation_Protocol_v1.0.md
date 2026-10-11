# SustainTrace independent human validation protocol v1.0

## Purpose

This prospective protocol creates an independent human reference for the reliability of evidence-grounded ESG knowledge extraction. It does not reuse AI-simulated references as human gold.

## Research questions

- **RQ1 — Knowledge fidelity:** How accurately does SustainTrace preserve subject, predicate, value, period, unit, boundary and evidence coordinates?
- **RQ2 — Reliability control:** How often does the system admit unsupported claims or abstain when a promotable fact is present?
- **RQ3 — Controlled repair:** Do archived repair decisions improve deterministic post-validation without silent retry or evidence loss? RQ3 is evaluated from immutable repair executions; human adjudication is used only where the final knowledge outcome is disputed.

## Frozen human benchmark

- 20 official English-language 2025 annual or sustainability reports from late expansion batches B023–B030.
- 60 bounded tasks: 20 direct claims, 20 complex claims, and 20 abstention audits.
- Each task exposes only a small frozen page window; annotators are not asked to read an entire report.
- Annotators A and B independently label the same tasks in different deterministic orders.
- The adjudicator sees only disagreements after both workbooks are locked.

## Blinding and independence

Annotators may inspect the named PDF and cited page window, but must not inspect simulated references, model prompts, candidate scores, repair logs, the other annotator's workbook, or the final system acceptance decision. Generative AI assistance is prohibited. Search within the source PDF is permitted and must be recorded when it changes the evidence window.

## Labels

Primary support label: `fully_supported`, `partially_supported`, `unsupported`, `cannot_assess`, or `source_defect`.

Knowledge-base action: `admit`, `correct_then_review`, `reject`, or `abstain_or_conflict`.

For candidate claims, each populated slot is checked independently: subject, predicate, value, period, unit, boundary/method, and evidence coordinates. For abstention audits, the annotator records whether an eligible atomic fact is present and, if so, supplies the missing fact.

## Outcomes and statistics

- Exact-claim support and slot-level exactness.
- Evidence-page and table-coordinate accuracy.
- Knowledge admission precision.
- Unsafe admission rate: unsupported or unassessable claims marked for admission.
- False-abstention rate: abstention windows containing an eligible atomic fact.
- Inter-annotator agreement: raw agreement and Cohen's kappa for support and action labels; slot agreement is reported separately.
- Final performance uses adjudicated labels with report-clustered bootstrap 95% confidence intervals.
- Results are stratified by direct claim, complex claim and abstention audit; no invalid task is silently removed.

## Pilot and freeze

The first six tasks are a calibration pilot. Wording may be clarified only before the main annotation begins. After protocol freeze, task text, source hashes and decision rules remain immutable. Pilot labels may enter the final set only if no substantive rule changes are made.

## Stopping and exclusions

A task is invalid only when the source hash does not match, the cited page is absent, or the prompt is irreparably ambiguous. Invalidity is adjudicated and reported. Evidence scarcity is a substantive outcome, not an exclusion.

## Ethics and data handling

The study evaluates public corporate reports and software outputs; it does not collect sensitive personal data. Annotator identity is stored separately from task labels. Institutional requirements must be confirmed by the responsible author before recruitment.

## Frozen inventory

| Item | Count |
|---|---:|
| Reports | 20 |
| Direct-claim tasks | 20 |
| Complex-claim tasks | 20 |
| Abstention audits | 20 |
| Total tasks per annotator | 60 |
| Independent annotators | 2 |
| Adjudicator | 1 |

## Report set

| # | Document ID | Company | Report | SHA256 |
|---:|---|---|---|---|
| 1 | `KB-B023-CRH-SPR2025` | CRH plc | CRH Sustainability Performance Report 2025 | `838c40c5c4a2bf8ebfb225d5f6579e38de4565efad44d91ce6fd456dea3ef9ba` |
| 2 | `KB-B023-ARKEMA-URD2025` | Arkema S.A. | Arkema Universal Registration Document 2025 | `de11061374f70634028b7ffc561e33f93d2f69bf26043888f09be18a8f4f1632` |
| 3 | `KB-B024-FORTUM-FIN2025` | Fortum Oyj | Fortum Financials 2025 | `0f348698addddf27181efe6c999fe17f4ca4390c510e97ce192d254c029764ce` |
| 4 | `KB-B024-YARA-AR2025` | Yara International ASA | Yara Annual Report 2025 | `95ecc7a0b18ca97ee9d579bc3799ed58052a31584ef6b21ac55d466aa77ce5d2` |
| 5 | `KB-B025-EQUINOR-AR2025` | Equinor ASA | Equinor Annual Report 2025 | `4266bb0b2f31bb9a8cc2ed11248cd579e0f98bb3c81fcffaf5c93a89e62e5d98` |
| 6 | `KB-B025-AKERBP-AR2025` | Aker BP ASA | Aker BP Annual Report 2025 | `c5afca29558be6e5daf6cf8e31b378fdd2542bd29b847f3ec96fce10172a1a15` |
| 7 | `KB-B025-DNB-AR2025` | DNB Bank ASA | DNB Group Annual Report 2025 | `e793bbb20582975be0ee87825cafe7d05ad8e80f986f446d8cbfad7e2c84c125` |
| 8 | `KB-B026-STOREBRAND-AR2025` | Storebrand ASA | Storebrand ASA Annual Report 2025 | `56ae30f6f6d5ee245602de45a2f7292e42e13f748a996da0c3f15c4cd2e160b3` |
| 9 | `KB-B026-ORKLA-AR2025` | Orkla ASA | Orkla Annual Report 2025 | `1ac3c951a126ac27733bdae3114237abcbeca4f568f881266ac8ae673239e271` |
| 10 | `KB-B026-SEB-AR2025` | Skandinaviska Enskilda Banken AB (publ) | SEB Annual Report 2025 | `1bf07071afbab0269914a1a78d16e4e840e73e5efbe901af97b148d288b28083` |
| 11 | `KB-B027-NORDEA-AR2025` | Nordea Bank Abp | Nordea Annual Report 2025 | `cce7c2004fbeca8b652ea9977be08500c1297c0cd307349bd016c1dc4de11e1e` |
| 12 | `KB-B027-HANDELSBANKEN-AR2025` | Svenska Handelsbanken AB (publ) | Handelsbanken Annual Report 2025 | `8679cdb160d9603f970eb6251546c8e6a1d98813a493bc4605f26cb933d88717` |
| 13 | `KB-B027-SECURITAS-AR2025` | Securitas AB (publ) | Securitas Annual Report 2025 | `e5d82427641d2dae5ed6f0bbe5c075827382c9bb5a2064a0aa3b4ec8a3991f95` |
| 14 | `KB-B028-TELIA-AR2025` | Telia Company AB (publ) | Telia Annual Report 2025 | `572c00695eca26b8bea90e2c9d0cdaaeaddf845f2851969c4f9c9d2cba85ecf7` |
| 15 | `KB-B028-ASSA-ABLOY-AR2025` | ASSA ABLOY AB (publ) | ASSA ABLOY Annual Report 2025 | `cfbb6cbd864e00b71c55bf5c7803da470f7230129308012ebef6f80dda273b90` |
| 16 | `KB-B028-LOOMIS-ASR2025` | Loomis AB | Loomis Annual and Sustainability Report 2025 | `c601ba6cac8ac150b79e8061312120ba2c3136f22a9c24f302602e16fcf6d46a` |
| 17 | `KB-B029-INVESTOR-AR2025` | Investor AB (publ) | Investor Annual Report 2025 | `e7a5af97f82433a1b1346a26ff2bcca9f342e2399dcbd190f7077ecae3150100` |
| 18 | `KB-B029-VATTENFALL-ASR2025` | Vattenfall AB | Vattenfall Annual and Sustainability Report 2025 | `be8ba08ffe79f95fea1e82c4484c7b68d1c2abe4c3f46015ffcf9dfebc12533f` |
| 19 | `KB-B029-SWEDAVIA-ASR2025` | Swedavia AB (publ) | Swedavia Annual and Sustainability Report 2025 | `95c7ad31487d729c99c3d42f3a5344ae1eb506ad1cf3524f6a3d16f1dbfce0d3` |
| 20 | `KB-B030-NCC-ASR2025` | NCC AB (publ) | NCC Annual and Sustainability Report 2025 | `253f5b9bf6a12ec5ce7e1965711dcda91af42da1bd58cb37972b5d87af853de2` |
