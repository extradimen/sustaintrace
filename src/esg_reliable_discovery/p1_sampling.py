from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any


class P1SamplingError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sample_p1_sources(
    registry_path: str | Path,
    *,
    seed: int,
    per_stratum: int = 4,
    minimum_per_region: int = 3,
) -> dict[str, Any]:
    path = Path(registry_path)
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("status") != "frozen" or registry.get("selection_allowed") is not True:
        raise P1SamplingError("Source registry must be frozen before sampling")
    eligible = [
        item for item in registry.get("candidates", [])
        if item.get("eligibility_status") == "eligible"
    ]
    strata = (
        "high_environmental_exposure",
        "medium_physical_operations",
        "financial_or_digital_services",
    )
    groups = {
        name: sorted(
            (item for item in eligible if item.get("exposure_stratum") == name),
            key=lambda item: item["candidate_id"],
        )
        for name in strata
    }
    if any(len(group) < per_stratum for group in groups.values()):
        raise P1SamplingError("Insufficient eligible candidates for a stratum")

    rng = random.Random(seed)
    for _attempt in range(1, 10001):
        selected = []
        for name in strata:
            selected.extend(rng.sample(groups[name], per_stratum))
        regions = Counter(item["region"] for item in selected)
        if all(regions.get(name, 0) >= minimum_per_region for name in (
            "Europe", "North America", "Asia Pacific"
        )):
            break
    else:
        raise P1SamplingError("No sample satisfied the registered regional constraints")

    selected_ids = {item["candidate_id"] for item in selected}
    selected = sorted(selected, key=lambda item: item["candidate_id"])
    reserves = sorted(
        (item for item in eligible if item["candidate_id"] not in selected_ids),
        key=lambda item: item["candidate_id"],
    )
    return {
        "schema_version": "1.0",
        "sample_id": "P1-SAMPLE-v0.1",
        "status": "frozen",
        "algorithm": "python_random.Random.sample_over_candidate_id_sorted_strata_v1",
        "seed": seed,
        "attempt": _attempt,
        "registry_id": registry["registry_id"],
        "registry_sha256": _sha256(path),
        "constraints": {
            "per_stratum": per_stratum,
            "minimum_per_region": minimum_per_region,
        },
        "selected": selected,
        "reserves": reserves,
        "selected_strata": dict(sorted(Counter(i["exposure_stratum"] for i in selected).items())),
        "selected_regions": dict(sorted(regions.items())),
        "inference_allowed": False,
    }
