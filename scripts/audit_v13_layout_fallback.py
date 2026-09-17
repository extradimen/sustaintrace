from __future__ import annotations

import argparse
import json
from pathlib import Path

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.layout_fallback import build_layout_fallback_handles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        default="configs/framework/v1.3_layout_fallback_development_registry.json",
    )
    parser.add_argument("--artifact-root", default="artifacts/v13/layout_fallback_dev01")
    parser.add_argument(
        "--output", default="data/results/v1.3_layout_fallback_dev01.lock.json"
    )
    args = parser.parse_args()
    registry_path = Path(args.registry)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    artifact_root = Path(args.artifact_root)
    output_path = Path(args.output)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite locked result: {output_path}")
    artifact_root.mkdir(parents=True, exist_ok=True)
    results = []
    for target in registry["targets"]:
        artifact_path = artifact_root / f"{target['task_id']}.layout.json"
        if artifact_path.exists():
            raise FileExistsError(f"Refusing to overwrite artifact: {artifact_path}")
        handles, provenance = build_layout_fallback_handles(
            pdf_path=target["pdf_path"],
            pdf_page=target["pdf_page"],
            document_id=target["document_id"],
            document_sha256=target["document_sha256"],
        )
        artifact_path.write_text(
            json.dumps(
                {"provenance": provenance, "handles": handles},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        extracted = "\n".join(item["verbatim_text"] for item in handles).replace(",", "")
        anchors_found = {
            anchor: anchor.replace(",", "") in extracted
            for anchor in target["scoring_only_anchors"]
        }
        results.append(
            {
                "task_id": target["task_id"],
                "artifact_path": str(artifact_path),
                "artifact_sha256": sha256_file(artifact_path),
                "line_count": len(handles),
                "scoring_only_anchor_recall": anchors_found,
                "all_scoring_anchors_recovered": all(anchors_found.values()),
                "hidden_reference_value_used_for_selection": False,
            }
        )
    result = {
        "schema_version": "1.0",
        "experiment_id": "V13-LAYOUT-FALLBACK-DEV01",
        "status": (
            "completed" if all(x["all_scoring_anchors_recovered"] for x in results) else "failed"
        ),
        "development_data_only": True,
        "p3_rerun": False,
        "registry_sha256": sha256_file(registry_path),
        "results": results,
        "aggregate_score": None,
    }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
