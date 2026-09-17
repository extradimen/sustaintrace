import json

import pytest

from esg_reliable_discovery.p1_sampling import P1SamplingError, sample_p1_sources


def _registry(status="frozen"):
    strata = ["high_environmental_exposure", "medium_physical_operations",
              "financial_or_digital_services"]
    regions = ["Europe", "North America", "Asia Pacific", "Europe"]
    candidates = []
    for s_index, stratum in enumerate(strata):
        for index, region in enumerate(regions):
            candidates.append({
                "candidate_id": f"C{s_index}{index}", "company": f"Co{s_index}{index}",
                "region": region, "exposure_stratum": stratum,
                "eligibility_status": "eligible",
            })
    return {"registry_id": "R1", "status": status,
            "selection_allowed": status == "frozen", "candidates": candidates}


def test_sampling_is_deterministic_and_balanced(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(_registry()), encoding="utf-8")
    first = sample_p1_sources(path, seed=20260903, minimum_per_region=2)
    second = sample_p1_sources(path, seed=20260903, minimum_per_region=2)
    assert [i["candidate_id"] for i in first["selected"]] == [
        i["candidate_id"] for i in second["selected"]
    ]
    assert set(first["selected_strata"].values()) == {4}
    assert first["inference_allowed"] is False


def test_open_registry_cannot_be_sampled(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(_registry("open")), encoding="utf-8")
    with pytest.raises(P1SamplingError, match="must be frozen"):
        sample_p1_sources(path, seed=1)
