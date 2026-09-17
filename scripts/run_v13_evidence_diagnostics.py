from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from esg_reliable_discovery.evidence_diagnostics import diagnose_evidence_state
from esg_reliable_discovery.hashing import sha256_file


def _parsed_text(path: Path) -> str:
    blocks = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(
        str(block.get("text") or block.get("table_body") or "") for block in blocks
    )


def _raw_page_text(pdf_path: Path, page: int) -> str:
    completed = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def run_benchmark(config_path: Path, workspace: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for case in config["cases"]:
        pdf_path = workspace / case["pdf_path"]
        content_path = workspace / case["content_list_path"]
        parsed = _parsed_text(content_path)
        diagnostic = diagnose_evidence_state(
            issuer_answer_status=case["issuer_answer_status"],
            expected_anchors=case["expected_anchors"],
            raw_page_text=_raw_page_text(pdf_path, case["pdf_page"]),
            parsed_page_text=parsed,
            retrieved_evidence_text=parsed,
            structure_required=case.get("structure_required", False),
            raw_structure_supported=case.get("raw_structure_supported", True),
            parsed_structure_supported=case.get("parsed_structure_supported", True),
            retrieved_structure_supported=case.get("retrieved_structure_supported", True),
        )
        results.append(
            {
                "task_id": case["task_id"],
                "expected_state": case["expected_state"],
                "observed_state": diagnostic["state"],
                "exact_state_match": diagnostic["state"] == case["expected_state"],
                "diagnostic": diagnostic,
                "source_artifacts": {
                    "pdf_sha256": sha256_file(pdf_path),
                    "content_list_sha256": sha256_file(content_path),
                },
                "structure_adjudication": case.get("structure_adjudication"),
            }
        )
    return {
        "schema_version": "1.0",
        "experiment_id": "V13-EVIDENCE-DIAGNOSTICS-DEV01",
        "status": "completed" if all(x["exact_state_match"] for x in results) else "failed",
        "development_data_only": True,
        "p3_rerun": False,
        "hidden_anchor_injection_applied": False,
        "case_count": len(results),
        "exact_state_matches": sum(x["exact_state_match"] for x in results),
        "results": results,
        "aggregate_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", default="data/benchmarks/v1.3_evidence_diagnostic_cases.json"
    )
    parser.add_argument(
        "--output", default="data/results/v1.3_evidence_diagnostics_dev01.lock.json"
    )
    args = parser.parse_args()
    workspace = Path.cwd()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite locked result: {output}")
    result = run_benchmark(Path(args.config), workspace)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
