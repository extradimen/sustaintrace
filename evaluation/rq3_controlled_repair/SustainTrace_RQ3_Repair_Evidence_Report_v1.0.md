# SustainTrace RQ3 heterogeneous controlled-repair evidence v1.0

## Scope

This addendum synthesizes immutable evidence; it does not rerun or rescore a historical experiment. The component set contains **13 single-attempt unseen trials**, covering **6 repair-component classes** and **7 reports**. A separate frozen state-machine set contains **4 execution-control cases** on one parent record.

## Heterogeneous component evidence

| Component | Trials | Contract passes | Exposed failures | New unseen positive passes | Unseen fail-closed passes | Reports |
|---|---:|---:|---:|---:|---:|---:|
| CALCULATION_LINEAGE_INCOMPLETE | 4 | 1 | 3 | 1 | 0 | 1 |
| FIELD_EVIDENCE_BINDING_INCOMPLETE | 1 | 1 | 0 | 0 | 1 | 1 |
| NATIVE_PDF_CORROBORATION_INCOMPLETE | 2 | 1 | 1 | 1 | 0 | 2 |
| PERIOD_ATTACHMENT_INCOMPLETE | 1 | 1 | 0 | 0 | 1 | 1 |
| TABLE_CELL_BINDING_INCOMPLETE | 4 | 1 | 3 | 1 | 0 | 3 |
| UNIT_ATTACHMENT_INCOMPLETE | 1 | 1 | 0 | 0 | 1 | 1 |

Across the 13 trials, 6 met their frozen contracts and 7 exposed a failure. The failures remain in the record. **3 component families**—table-cell binding, native-PDF corroboration and calculation lineage—show a failure followed by development and a pass on a newly frozen unseen case. No component trial wrote a fact or promoted trusted knowledge.

## Execution-control evidence

The four frozen lifecycle cases ended in 1 promotion, 2 rollbacks and 1 preflight block. All 4/4 reached a safe terminal state. All 3 injected hash, invariant or preflight faults were detected; no source artifact or locked experiment was modified.

## Interpretation for RQ3

The evidence supports a bounded claim: SustainTrace preserves auditable fail-closed control across six repair-component classes, and its recorded development process produced three genuine failure-to-new-unseen-pass sequences without rewriting earlier failures. It does **not** establish general autonomous repair effectiveness. No component has repeated unseen success across sufficiently heterogeneous reports to meet the project's L4 evidence threshold, and component success alone never authorizes trusted-knowledge promotion.

## Reporting rule

The manuscript should report the heterogeneous component evidence and the execution-control evidence separately. Their denominators must not be pooled into a single repair-accuracy percentage because they measure different units: component contract behavior versus lifecycle safety.
