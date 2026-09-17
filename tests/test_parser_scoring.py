import json
from pathlib import Path

import pytest

from esg_reliable_discovery.parser_scoring import ParserScoringError, score_parser_benchmark


def test_parser_benchmark_scores_present_and_absent_patterns(tmp_path: Path) -> None:
    (tmp_path / "parsed.md").write_text("FY2024 16; FY2023 21", encoding="utf-8")
    spec = {
        "benchmark_id": "test",
        "parser": {},
        "cases": [
            {
                "task_id": "T1",
                "parsed_text_path": "parsed.md",
                "assertions": [
                    {
                        "assertion_id": "a",
                        "dimension": "value",
                        "kind": "regex_present",
                        "pattern": "FY2024\\s+16",
                    },
                    {
                        "assertion_id": "b",
                        "dimension": "false_discovery",
                        "kind": "regex_absent",
                        "pattern": "FY2024\\s+55",
                    },
                ],
            }
        ],
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    result = score_parser_benchmark(path, tmp_path)
    assert result["micro_score"] == 1.0
    assert result["all_critical_passed"] is True


def test_parser_benchmark_rejects_missing_parse(tmp_path: Path) -> None:
    spec = {
        "benchmark_id": "test",
        "parser": {},
        "cases": [{"task_id": "T1", "parsed_text_path": "missing.md", "assertions": []}],
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(ParserScoringError, match="does not exist"):
        score_parser_benchmark(path, tmp_path)
