#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from esg_reliable_discovery.diagnostic_preflight import (
    run_preflighted_read_only_diagnostic,
)
from esg_reliable_discovery.knowledge_base import sha256_file

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/v43_parent_binding_preflight_unseen_v0.1.lock.json"
OUTPUT = ROOT / "artifacts/v43_parent_binding_preflight_unseen_v0.1/result.lock.json"
CLOSURE = ROOT / "data/results/v43_parent_binding_preflight_unseen_closure.lock.json"


def main() -> None:
    for output in (OUTPUT, CLOSURE):
        if output.exists():
            raise FileExistsError(f"refusing_to_overwrite:{output}")
    manifest = json.loads(MANIFEST.read_text())
    stores = manifest["immutable_stores"]
    facts = ROOT / stores["facts"]["path"]
    gaps = ROOT / stores["gaps"]["path"]
    if sha256_file(facts) != stores["facts"]["sha256"]:
        raise ValueError("frozen_fact_store_hash_mismatch")
    if sha256_file(gaps) != stores["gaps"]["sha256"]:
        raise ValueError("frozen_gap_store_hash_mismatch")
    before = {"facts": sha256_file(facts), "gaps": sha256_file(gaps)}
    calls = []

    def sentinel_runner(fixture, fact, root):
        calls.append((fixture["fixture_id"], fact["record_id"], root == ROOT))
        return {
            "status": "passed",
            "fixture_id": fixture["fixture_id"],
            "fact_record_id": fact["record_id"],
            "adapter": "unseen_read_only_sentinel_no_historical_diagnostic_rerun",
        }

    execution = run_preflighted_read_only_diagnostic(
        fixture=manifest["fixture"],
        satisfied_dimensions=manifest["satisfied_dimensions"],
        root=ROOT,
        fact_store_path=facts,
        gap_store_path=gaps,
        diagnostic_runner=sentinel_runner,
    )
    after = {"facts": sha256_file(facts), "gaps": sha256_file(gaps)}
    passed = (
        execution["status"] == "completed"
        and execution["preflight"]["status"] == "passed"
        and execution["adapter_invocation_count"] == 1
        and len(calls) == 1
        and before == after
    )
    result = {
        "schema_version": "0.1",
        "validation_id": manifest["validation_id"],
        "status": "passed" if passed else "failed",
        "single_attempt": True,
        "execution": execution,
        "adapter_calls": calls,
        "immutable_store_sha256_before": before,
        "immutable_store_sha256_after": after,
        "frozen_manifest": {"path": str(MANIFEST), "sha256": sha256_file(MANIFEST)},
        "historical_result_modified": False,
        "fact_write_performed": False,
        "gap_write_performed": False,
        "trust_promotion_performed": False,
        "cloud_transmission_performed": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    closure = {
        "schema_version": "0.1",
        "closure_id": "V4.3-PARENT-BINDING-PREFLIGHT-UNSEEN-CLOSURE-V01",
        "status": "passed" if passed else "failed",
        "manifest": {"path": str(MANIFEST), "sha256": sha256_file(MANIFEST)},
        "result": {"path": str(OUTPUT), "sha256": sha256_file(OUTPUT)},
        "attempt_count": 1,
        "parent_records_modified": False,
    }
    CLOSURE.write_text(json.dumps(closure, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "adapter_calls": len(calls)}))


if __name__ == "__main__":
    main()
