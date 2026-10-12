# SustainTrace E3 paired admission-control results

E3 isolates the deterministic SustainTrace admission gate: each model produced one frozen candidate per task, after which the ungated and full-system decisions were derived locally from that identical candidate. No silent retries or post-hoc semantic repairs were allowed.

| Model | Completion | Unsafe admission: ungated | Unsafe admission: full | Absolute reduction | Prevented / introduced | Exact paired *p* | Safe admission: ungated | Safe admission: full | Retention |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mistral Large 3 (675B) | 120/120 | 27.0% (17.0%–37.0%) | 1.0% (0.0%–3.0%) | 26.0% (17.0%–36.0%) | 26/0 | 2.980e-08 | 60.0% (40.0%–80.0%) | 50.0% (30.0%–70.0%) | 83.3% (58.3%–100.0%) |
| GPT-OSS (120B) | 119/120 | 24.2% (16.0%–33.3%) | 1.0% (0.0%–3.1%) | 23.2% (15.2%–32.0%) | 23/0 | 2.384e-07 | 65.0% (45.0%–85.0%) | 35.0% (15.0%–55.0%) | 53.8% (30.8%–76.9%) |

## Interpretation

The full admission gate reduced unsafe admissions by 26.0 percentage points for Mistral Large 3 and 23.2 points for GPT-OSS. No unsafe admission was introduced in either paired comparison, and both exact paired tests were significant. The safeguard was not cost-free: safe-admission rates fell by 10.0 points for Mistral and 30.0 points for GPT-OSS. The latter indicates materially stronger over-blocking and motivates calibration rather than a universal superiority claim.

## Claim boundary

These results establish a paired deterministic gate effect on frozen candidates. They do not establish external factual truth, fully unseen semantic generalization, or human-adjudicated semantic accuracy for E3. Report-clustered bootstrap intervals use 10,000 resamples with the report as the cluster.
