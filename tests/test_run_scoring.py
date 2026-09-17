import json
from pathlib import Path

import pytest

from esg_reliable_discovery.archive import RunArchive, verify_run_checksums
from esg_reliable_discovery.ollama_client import OllamaResult
from esg_reliable_discovery.run_scoring import score_archived_closed_run

ROOT = Path(__file__).parents[1]


def _closed_run(tmp_path: Path) -> Path:
    gold = json.loads(
        (ROOT / "data/annotations/p0_gold/P0-TEXT-001.json").read_text(encoding="utf-8")
    )
    archive = RunArchive.create(tmp_path, "experiment", "run-001")
    result = OllamaResult(
        request={"model": "candidate"},
        response={"message": {"content": json.dumps(gold)}},
        elapsed_seconds=1.0,
        request_sha256="a" * 64,
    )
    archive.record_result(
        result,
        model_manifest={"digest": "d"},
        normalized_output=gold,
        additional_json={
            "task_context_manifest.json": {"task_id": "P0-TEXT-001"},
            "validation.json": {"status": "passed", "errors": []},
        },
    )
    return archive.run_dir


def test_archived_run_is_verified_scored_and_resealed(tmp_path):
    run_directory = _closed_run(tmp_path)
    result = score_archived_closed_run(
        run_directory,
        ROOT / "data/annotations/p0_gold",
        ROOT / "templates/finding_card.schema.json",
    )
    assert result["dimensions"]["answer_correctness"] == 1
    assert result["aggregate_score"] is None
    assert (run_directory / "score.json").is_file()
    verify_run_checksums(run_directory)
    with pytest.raises(FileExistsError):
        score_archived_closed_run(
            run_directory,
            ROOT / "data/annotations/p0_gold",
            ROOT / "templates/finding_card.schema.json",
        )


def test_archive_tampering_is_detected_before_scoring(tmp_path):
    run_directory = _closed_run(tmp_path)
    (run_directory / "validation.json").write_text(
        json.dumps({"status": "passed", "errors": ["tampered"]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        score_archived_closed_run(
            run_directory,
            ROOT / "data/annotations/p0_gold",
            ROOT / "templates/finding_card.schema.json",
        )
