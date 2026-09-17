from __future__ import annotations

import argparse
import json
from pathlib import Path

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.layout_fallback import build_layout_fallback_handles
from esg_reliable_discovery.parser_anomaly import assess_page_parser_anomaly


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-registry", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, default=Path("."))
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--layout-registry-output", type=Path, required=True)
    parser.add_argument(
        "--experiment-id", default="P4-V13-PARSER-ANOMALY-AUDIT-V01"
    )
    args = parser.parse_args()
    for output in (args.audit_output, args.layout_registry_output):
        if output.exists():
            raise FileExistsError(f"refusing_to_overwrite:{output}")
        output.parent.mkdir(parents=True, exist_ok=True)

    registry = json.loads(args.target_registry.read_text(encoding="utf-8"))
    audits = []
    layout_targets = []
    for target in registry["targets"]:
        output_dir = Path(target["output_directory"])
        run_path = output_dir / "esg_rd_mineru_run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        content_rel = next(
            item["path"]
            for item in run["output_files"]
            if item["path"].endswith("_content_list.json")
        )
        content_path = output_dir / content_rel
        mineru_blocks = json.loads(content_path.read_text(encoding="utf-8"))
        pdf_path = args.raw_root / target["local_path"]
        native_handles, native_provenance = build_layout_fallback_handles(
            pdf_path=pdf_path,
            pdf_page=target["pdf_page"],
            document_id=target["document_id"],
            document_sha256=target["document_sha256"],
        )
        assessment = assess_page_parser_anomaly(
            mineru_blocks=mineru_blocks,
            native_layout_text="\n".join(x["verbatim_text"] for x in native_handles),
        )
        audits.append(
            {
                "target_id": target["target_id"],
                "document_id": target["document_id"],
                "pdf_page": target["pdf_page"],
                "task_ids": target["task_ids"],
                "mineru_run_sha256": sha256_file(run_path),
                "mineru_content_sha256": sha256_file(content_path),
                "native_layout_line_count": len(native_handles),
                "native_layout_provenance": native_provenance,
                "assessment": assessment,
            }
        )
        if assessment["fallback_required"]:
            for task_id in target["task_ids"]:
                layout_targets.append(
                    {
                        "task_id": task_id,
                        "document_id": target["document_id"],
                        "document_sha256": target["document_sha256"],
                        "pdf_path": target["local_path"],
                        "pdf_page": target["pdf_page"],
                        "trigger_reasons": assessment["reasons"],
                    }
                )

    audit = {
        "schema_version": "1.0",
        "experiment_id": args.experiment_id,
        "status": "locked_before_candidate_inference",
        "task_text_used": False,
        "expected_value_used": False,
        "target_registry_sha256": sha256_file(args.target_registry),
        "targets": audits,
    }
    args.audit_output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    layout_registry = {
        "schema_version": "1.0",
        "status": "frozen_before_candidate_inference",
        "trigger_audit": str(args.audit_output),
        "trigger_audit_sha256": sha256_file(args.audit_output),
        "selection_rule": "task-independent frozen parser anomaly trigger",
        "targets": layout_targets,
    }
    args.layout_registry_output.write_text(
        json.dumps(layout_registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
