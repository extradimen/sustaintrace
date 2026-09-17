# SustainTrace Release Engineering Milestone

## Outcome

The locally executable P0/P1 engineering scope is complete and forms the SustainTrace 0.1.0
release candidate. On macOS, the complete path from `bootstrap.py` through a real MinerU PDF smoke
parse and the single-port `run.py` frontend/API launch has been verified. Windows and Linux
installation branches and the GitHub Actions matrix are implemented, but cannot be described as
runner-verified until the workflows have executed in a remote repository.

## Acceptance against the release plan

| Priority | Work item | Current outcome | Evidence |
|---|---|---|---|
| P0 | Unified three-platform installer | Implemented; macOS passed, Windows/Linux await CI | `bootstrap.py` |
| P0 | Unified launcher | Passed | `run.py`; same-origin UI/API smoke test |
| P0 | Automatic MinerU installation | Passed locally | MinerU 3.4.0; 40/40 SHA256 checks; real PDF smoke test |
| P0 | Cross-platform Poppler installation | Implemented; macOS passed, Windows/Linux await CI | Homebrew, apt, dnf, pacman, winget, and Chocolatey branches |
| P0 | Frontend included in distribution | Passed | Wheel contains the static frontend; users do not need Node.js |
| P0 | Knowledge bases included in distribution | Passed | Non-destructive initialization on first launch |
| P1 | Entity registry | Passed | 34 persistent identifiers with controlled aliases, merges, and disambiguation |
| P1 | Explicit relation layer | Passed | 149 queryable entity-predicate-value edges |
| P1 | Baseline knowledge filtering | Passed | Default layer contains only 149 Tier B facts; candidates and simulations are isolated |
| P1 | Source-report distribution policy | Passed | No corporate PDFs bundled; 8 official URLs and 26 metadata-only records |
| P1 | Frontend internationalization | Passed | English default; complete English and Simplified Chinese catalogs; extensible selector |
| P1 | Three-platform automated tests | Workflow complete; remote execution pending | Two-level macOS, Windows, and Linux matrix |
| P1 | GitHub release structure | Local materials complete; remote release pending | README, license, citation, changelog, security policy, and CI |
| P1 | SoftwareX reproducibility materials | Local materials complete; DOI pending publication | Example, architecture, evaluations, and reproducibility checklist |

## Local validation results

- Python: 592 tests passed.
- Ruff: the repository passed static checks.
- Frontend: ESLint and the static production build passed.
- Installation: all 40 MinerU model assets were present and matched their hashes; Poppler was
  available.
- Parsing: a generated one-page PDF produced five Markdown/JSON artifacts.
- Wheel: installation and release-seed initialization passed in an isolated temporary environment.
- Release boundary: 149 Tier B facts, 34 issuers, 149 relations, and 1,032 failure observations;
  candidate facts, simulated records, and original corporate PDFs were excluded.

## External steps that local validation cannot replace

1. Configure the GitHub remote and create the first commit.
2. Run the complete three-platform MinerU workflows and preserve evidence from all three runners.
3. Create an immutable GitHub Release and archive it with Zenodo to obtain the permanent DOI.

Until those steps are complete, publication materials may state that cross-platform installation
has been implemented, but not that every platform has been verified on independent runners.
