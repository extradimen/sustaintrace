# SustainTrace Architecture and Paper-to-Code Map

SustainTrace separates evidence-bearing report facts from method knowledge about failures and
repairs. The repository structure follows that distinction and the SoftwareX manuscript.

## Processing path

1. **Source freeze** — PDF identity and SHA-256 are registered before extraction.
2. **Document parsing** — MinerU is the enhanced parser; native PDF and Poppler paths provide
   controlled fallbacks.
3. **Atomic projection** — output is projected into typed fact slots rather than stored as an
   unrestricted answer.
4. **Evidence binding** — claims retain page, quotation and available table/layout coordinates.
5. **Admission control** — deterministic integrity, period, unit, boundary, calculation and
   conflict gates decide whether a candidate is eligible for promotion.
6. **Failure preservation** — blocked candidates become typed failure records; silent retries and
   post-hoc semantic completion are prohibited.
7. **Controlled repair** — eligible repairs create lineage-linked child candidates, undergo
   deterministic post-validation and remain human-gated before trusted promotion.

## Paper-to-code map

| Manuscript concept | Implementation or evidence |
|---|---|
| Core processing and API | `src/esg_reliable_discovery/` |
| Atomic fact, provenance and evaluation schemas | `schemas/` |
| Parser and model-asset locks | `configs/parsers/`, `model_manifests/` |
| Trusted report-fact seed | `src/esg_reliable_discovery/release_seed/knowledge_bases/v0.1/trusted_fact_records.jsonl` |
| Controlled entities and relations | `src/esg_reliable_discovery/release_seed/knowledge_bases/v0.1/entity_registry.jsonl`, `relation_edges.jsonl` |
| Failure and repair method knowledge | `src/esg_reliable_discovery/release_seed/knowledge_bases/v0.1/failure_records.jsonl`, repair catalogs in the same directory |
| Web workbench | `workbench-ui/` |
| RQ1 fidelity evidence | `evaluation/rq1_human_fidelity/` |
| RQ2 paired admission evidence | `evaluation/rq2_admission_control/` |
| RQ3 controlled-repair evidence | `evaluation/rq3_controlled_repair/` |
| Manuscript and figures | `paper/softwarex/` |

Issuer PDFs are intentionally absent from the public archive. The evaluation manifests retain the
document identities, frozen task definitions and checksums needed to audit the published derived
evidence under the source-distribution policy.
