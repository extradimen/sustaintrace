import json
from pathlib import Path

from esg_reliable_discovery.p1_synthetic_freeze import audit_synthetic_benchmark


def test_repository_synthetic_benchmark_passes_prefreeze_audit():
    result = audit_synthetic_benchmark(
        "data/tasks/p1_synthetic_task_pack_v0.1.draft.json",
        "templates/p1_synthetic_reference.schema.json",
        "data/manifests/p1_acquisition_manifest_v0.1.json",
        "data/manifests/p1_eligibility_exposure_exclusions.lock.json",
    )
    assert result["passed"] is True, result["errors"]
    assert result["task_count"] == result["verified_reference_count"] == 24
    assert result["human_gold_standard"] is False
    assert result["inference_allowed"] is False


def test_freeze_rejects_nonverified_reference(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    pack_path = root / "data/tasks/p1_synthetic_task_pack_v0.1.draft.json"
    pack = json.loads(pack_path.read_text())
    copied_root = tmp_path / "repository"
    for task in pack["tasks"]:
        source = root / task["reference_file"]
        target = copied_root / task["reference_file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text())
    first = copied_root / pack["tasks"][0]["reference_file"]
    reference = json.loads(first.read_text())
    reference["reference_status"] = "draft"
    first.write_text(json.dumps(reference))

    result = audit_synthetic_benchmark(
        pack_path,
        root / "templates/p1_synthetic_reference.schema.json",
        root / "data/manifests/p1_acquisition_manifest_v0.1.json",
        root / "data/manifests/p1_eligibility_exposure_exclusions.lock.json",
        copied_root,
    )

    assert result["passed"] is False
    assert any(error.endswith(":reference_not_verified") for error in result["errors"])
