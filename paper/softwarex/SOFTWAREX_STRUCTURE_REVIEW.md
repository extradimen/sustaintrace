# SoftwareX structure review for SustainTrace

## Official submission constraints checked on 11 October 2026

SoftwareX provides a journal-specific Word template and points LaTeX authors to Elsevier's
official article classes. The local submission source therefore uses the official Elsevier CAS
single-column class (`cas-sc.cls`), downloaded from CTAN, while following the section order in the
SoftwareX template.

The journal-specific requirements that affect this manuscript are:

- a public source-code repository, README and software license;
- a code-metadata table near the front of the article;
- approximately 100 words in the abstract and no more than six keywords;
- a maximum manuscript length of 4,000 words;
- no more than six figures; and
- five principal sections: **Motivation and significance**, **Software description**,
  **Illustrative examples**, **Impact**, and **Conclusions**.

Official sources:

- [SoftwareX / Research Elements journal guidance](https://www.elsevier.com/en-gb/researcher/author/tools-and-resources/research-elements-journals)
- [Elsevier LaTeX instructions](https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions)
- [Official Elsevier CAS package](https://ctan.org/pkg/els-cas-templates)
- [SoftwareX reviewer form](https://legacyfileshare.elsevier.com/promis_misc/softwarex-reviewer-form.pdf)

## Structural patterns in comparable SoftwareX papers

| Example | Reusable structural pattern | Implication for SustainTrace |
|---|---|---|
| *Kunai: A static analysis framework for Android apps*, SoftwareX 22 (2023), 101370 | Code metadata is followed immediately by motivation and a concrete software architecture. | Open with the practical ESG-document problem and identify the executable software gap, not a broad AI survey. |
| *A WebExtension framework for experimentation and evaluation of webpage segmentation methods*, SoftwareX 23 (2023), 101501 | Evaluation is tied to supported software operations and reproducible metrics. | Present the human benchmark, paired gate experiment and repair-state tests as evidence for software capabilities. |
| *Gecko: A Python library for the generation and mutation of realistic personal identification data at scale*, SoftwareX 27 (2024), 101846 | Benchmarks cover effectiveness and operational behaviour rather than implementation tests alone. | Separate knowledge fidelity, unsafe admission, safe-admission retention and execution safety. |
| *CohortPlat*, SoftwareX 32 (2025), 102381 | Multiple illustrative workflows precede the broader impact discussion. | Demonstrate evidence inspection, cross-report analysis and controlled repair as three user workflows. |
| *BLOCKS*, SoftwareX 36 (2026), 102999 | The abstract and impact section emphasize open code, archived releases and reproducibility. | Keep the GitHub repository, immutable artifacts and pending Zenodo DOI visible in both metadata and declarations. |

## Chosen SustainTrace organization

1. **Motivation and significance**
   - ESG document-to-knowledge problem
   - distinction from PDF conversion, general document pipelines, ESG triple extraction and ESG
     compliance knowledge graphs
2. **Software description**
   - architecture and two knowledge layers
   - atomic fact and evidence model
   - fail-closed admission and controlled repair
   - interface, installation and portability
3. **Illustrative examples**
   - source-linked fact inspection
   - qualified cross-report comparison
   - failure-to-repair audit
4. **Impact**
   - RQ1--RQ3 evaluation design
   - human-adjudicated knowledge fidelity
   - paired deterministic admission-control effect
   - bounded repair evidence and lifecycle safety
   - limitations and intended scientific reuse
5. **Conclusions**

This arrangement intentionally avoids separate top-level `Methods` and `Results` sections. Their
content is retained under **Impact**, where it establishes the reliability and scientific utility
of the software while preserving the five-section SoftwareX format.

Article links checked during the review:

- [Kunai, DOI 10.1016/j.softx.2023.101370](https://doi.org/10.1016/j.softx.2023.101370)
- [WebExtension framework, DOI 10.1016/j.softx.2023.101501](https://doi.org/10.1016/j.softx.2023.101501)
- [Gecko, DOI 10.1016/j.softx.2024.101846](https://doi.org/10.1016/j.softx.2024.101846)
- [CohortPlat, DOI 10.1016/j.softx.2025.102381](https://doi.org/10.1016/j.softx.2025.102381)

