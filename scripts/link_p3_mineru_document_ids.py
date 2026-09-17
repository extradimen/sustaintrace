#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("data/manifests/p3_mineru_target_registry_v0.1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/manifests/p3_mineru_document_aliases_v0.1.json"),
    )
    args = parser.parse_args()
    registry_path = args.registry
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    records = []
    for target in registry["targets"]:
        output = Path(target["output_directory"])
        document_alias = output / target["document_id"]
        candidates = [
            path
            for path in output.iterdir()
            if path.is_dir() and not path.is_symlink() and (path / "auto").is_dir()
        ]
        if len(candidates) != 1:
            raise RuntimeError(f"unexpected_mineru_artifact_layout:{target['target_id']}")
        actual = candidates[0]
        if document_alias.exists() or document_alias.is_symlink():
            if document_alias.resolve() != actual.resolve():
                raise RuntimeError(f"conflicting_document_alias:{target['target_id']}")
            status = "reused_verified_alias"
        else:
            document_alias.symlink_to(actual.name, target_is_directory=True)
            status = "created_relative_alias"
        auto = actual / "auto"
        content_candidates = list(auto.glob("*_content_list.json"))
        if len(content_candidates) != 1:
            raise RuntimeError(f"unexpected_content_list_layout:{target['target_id']}")
        content_alias = auto / f"{target['document_id']}_content_list.json"
        if content_alias.exists() or content_alias.is_symlink():
            if content_alias.resolve() != content_candidates[0].resolve():
                raise RuntimeError(f"conflicting_content_list_alias:{target['target_id']}")
        else:
            content_alias.symlink_to(content_candidates[0].name)
        records.append(
            {
                "target_id": target["target_id"],
                "document_id": target["document_id"],
                "actual_artifact_directory": actual.name,
                "alias": document_alias.as_posix(),
                "content_list_alias": content_alias.as_posix(),
                "status": status,
            }
        )
    manifest = {
        "schema_version": "1.0",
        "status": "mineru_document_id_aliases_ready",
        "reason": (
            "MinerU names its artifact directory after the PDF filename stem, while "
            "the frozen evidence builder resolves the registered document_id."
        ),
        "model_inference_occurred_before_fix": False,
        "records": records,
    }
    output_path = args.output
    if output_path.exists():
        raise FileExistsError(f"refusing_to_overwrite:{output_path}")
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"alias_count": len(records), "manifest": str(output_path)}))


if __name__ == "__main__":
    main()
