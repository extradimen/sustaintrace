# SustainTrace independent human validation results v1.0

## Scope

Two independent annotators reviewed 60 frozen tasks from 20 official ESG or annual reports. An independent adjudicator resolved 49 task-level disagreements and 134 slot-level disagreements. All 60 tasks were retained as valid.

## Inter-annotator agreement

| Decision | Raw agreement | Cohen's kappa | N |
|---|---:|---:|---:|
| Support label | 0.567 | 0.327 | 60 |
| Knowledge-base action | 0.583 | 0.431 | 60 |
| Candidate-task slots | 0.757 | 0.526 | 280 |

## RQ1 Knowledge fidelity

- Fully supported exact claims: **50.0% (20/40)**.
- At least partially supported claims: **100.0% (40/40)**.
- Applicable slot exactness: **80.5% (177/220)**.
- Evidence-coordinate exactness: **100.0% (40/40)**.

## RQ2 Reliability control

- Knowledge-admission precision for the three frozen Tier B promotions: **66.7% (2/3)**.
- Unsafe-admission rate: **0.0% (0/3)**.
- Promoted claims requiring bounded correction: **33.3% (1/3)**.
- False-abstention rate: **65.0% (13/20)**.
- Human-admissible share among held Tier C candidates: **37.8% (14/37)**. Tier C is a review queue, so this measures conservatism rather than final rejection error.

## RQ3 Controlled repair

The frozen execution-control set contains four cases: 1 promotion, 2 post-validation rollbacks and 1 preflight block. All four reached a controlled safe terminal state, and locked experiments were not modified or rescored. Because all four cases concern one parent record, this is an engineering control test and not broad evidence of repair effectiveness.

## Reporting constraint

RQ1 and RQ2 are complete for the frozen 20-report human benchmark. RQ3 requires a larger heterogeneous execution set before the manuscript can claim general repair effectiveness.
