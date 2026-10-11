# SustainTrace E3 Paired Evaluation Protocol v0.1

## Purpose

E3 estimates the causal effect of SustainTrace's deterministic admission controls without confounding that effect with independent model sampling. Each task permits exactly one model response. The unchanged response is the ungated outcome; SustainTrace full applies frozen deterministic controls to that same response.

E3 is a new experiment. E1 and E2 tasks or responses must not be relabelled, rerun, or reused as unseen E3 evidence.

## Research questions

1. **RQ1 — Executability:** What proportion of single model responses satisfy the frozen machine contract without retry or semantic repair?
2. **RQ2 — Safety effect:** On pre-registered non-admissible candidates, how much does full reduce unsafe knowledge admission relative to the paired ungated outcome?
3. **RQ3 — Utility retention:** On pre-registered admissible candidates, what proportion of correct admissions does full preserve?

## Comparison design

- Unit of generation: one task and one model response.
- Derived paths: `ungated_pipeline_verifier` and `sustaintrace_full`.
- Both paths share the same `raw_response_sha256`.
- Full may change only `knowledge_base_action`; it must not rewrite support or slot judgements.
- Every changed action requires a machine-readable gate audit with individual check results and reason codes.
- Model-behaviour failure is final for that task. Infrastructure interruption may resume only from the preserved checkpoint and parent run lineage.

There is no separate plain condition unless it has a genuinely different, pre-registered implementation. A duplicate of the ungated path is not treated as an experimental condition.

## Frozen task contract

Every task must freeze the source document SHA-256, permitted PDF pages, candidate claim, candidate evidence, task stratum, and an `admission_contract` containing:

- `allow_admission`: whether this structurally defined task class can yield a trusted fact;
- `required_slots`: the semantic slots that must be supported for admission.

The admission contract must be determined from task structure before model execution. It must not be inferred from the model response or altered after outcome inspection.

## Evaluation strata

E3 should include both clean and fault-bearing tasks, sampled across at least 20 previously unused reports:

1. Clean admissible atomic facts.
2. Wrong or out-of-window evidence pages.
3. Ungrounded or substituted evidence quotations.
4. Missing or mismatched period, unit, boundary, or method.
5. Non-atomic compound claims.
6. Abstention-audit tasks for which admission is structurally prohibited.

Deterministic mutations provide known fault status for RQ2. Clean-task semantic admissibility requires a separately sealed reference. If that reference is AI-derived rather than independently human adjudicated, results must be labelled pseudo-gold agreement and must not be reported as human-validated accuracy.

## Primary endpoints

- Machine-contract completion rate.
- Unsafe admission rate among pre-registered non-admissible tasks, separately for ungated and full.
- Paired unsafe admissions prevented by full.
- Safe admission retention among pre-registered admissible tasks.
- Over-blocking rate: ungated correct admissions changed to a non-admit action by full.
- Gate activation rate and reason-code distribution.

All proportions use report-clustered bootstrap 95% confidence intervals. Paired discordant counts are reported directly. The unit of clustering is the source report, not the task.

## Integrity rules

- Freeze the task pack and its self-hash before any cloud transmission.
- Freeze the sealed reference independently of model outputs.
- One candidate attempt per task; no silent retry.
- No post-hoc semantic repair.
- Preserve raw provider responses, request hashes, response hashes, checkpoints, failures, and controller receipts.
- Do not substitute a retired or unavailable model without a new frozen identity and explicit authorization.
- Run evidence-producing work only through the global experiment controller.

## Interpretation boundary

E3 can establish whether deterministic SustainTrace controls improve admission safety for the same candidate response. It does not, by itself, establish that an AI-derived semantic reference is equivalent to independent human annotation, nor that extracted claims are true outside the source report.
