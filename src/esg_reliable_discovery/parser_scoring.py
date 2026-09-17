from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ParserScoringError(ValueError):
    pass


def score_parser_case(case: dict[str, Any], repository_root: Path) -> dict[str, Any]:
    source = repository_root / case["parsed_text_path"]
    if not source.is_file():
        raise ParserScoringError(f"Parsed text does not exist: {source}")
    text = source.read_text(encoding="utf-8")
    checks = []
    for assertion in case["assertions"]:
        kind = assertion["kind"]
        pattern = assertion["pattern"]
        flags = re.IGNORECASE | re.DOTALL if assertion.get("ignore_case", True) else re.DOTALL
        matched = re.search(pattern, text, flags) is not None
        passed = not matched if kind == "regex_absent" else matched
        if kind not in {"regex_present", "regex_absent"}:
            raise ParserScoringError(f"Unsupported assertion kind: {kind}")
        checks.append(
            {
                "assertion_id": assertion["assertion_id"],
                "dimension": assertion["dimension"],
                "critical": assertion.get("critical", True),
                "passed": passed,
            }
        )
    passed_count = sum(check["passed"] for check in checks)
    critical_passed = all(check["passed"] for check in checks if check["critical"])
    return {
        "task_id": case["task_id"],
        "parsed_text_path": case["parsed_text_path"],
        "checks": checks,
        "passed": passed_count,
        "total": len(checks),
        "score": passed_count / len(checks) if checks else 0.0,
        "critical_passed": critical_passed,
        "visual_review": case.get("visual_review"),
    }


def score_parser_benchmark(spec_path: str | Path, repository_root: str | Path) -> dict[str, Any]:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    root = Path(repository_root).resolve()
    cases = [score_parser_case(case, root) for case in spec["cases"]]
    passed = sum(case["passed"] for case in cases)
    total = sum(case["total"] for case in cases)
    return {
        "schema_version": "1.0",
        "benchmark_id": spec["benchmark_id"],
        "parser": spec["parser"],
        "case_count": len(cases),
        "assertions_passed": passed,
        "assertions_total": total,
        "micro_score": passed / total if total else 0.0,
        "all_critical_passed": all(case["critical_passed"] for case in cases),
        "cases": cases,
        "limitations": spec.get("limitations", []),
    }
