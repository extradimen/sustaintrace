# SoftwareX Evaluation Evidence

This directory mirrors the three research questions reported in the SoftwareX manuscript. Each
subdirectory contains the frozen protocol, machine-readable outcomes, human-readable results and
checksums for one question. Original corporate PDFs are not redistributed.

| Research question | Evidence directory | Primary outcome |
|---|---|---|
| RQ1 — Are projected claims and evidence faithful to the frozen reports? | [`rq1_human_fidelity/`](rq1_human_fidelity/) | Human-adjudicated claim, slot and evidence-coordinate fidelity |
| RQ2 — Do admission controls reduce unsupported knowledge admission? | [`rq2_admission_control/`](rq2_admission_control/) | Paired ungated-versus-full decisions on identical frozen model candidates |
| RQ3 — Do repairs preserve fail-closed and auditable behavior? | [`rq3_controlled_repair/`](rq3_controlled_repair/) | Immutable component trials and repair-state-machine outcomes |

The denominators are intentionally not pooled. RQ1 is a human-adjudicated fidelity benchmark,
RQ2 is a paired admission-control experiment, and RQ3 is bounded software evidence rather than an
accuracy benchmark. See the manuscript for limitations and interpretation.

