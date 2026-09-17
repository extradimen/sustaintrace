from __future__ import annotations

import argparse
import json
from pathlib import Path

from esg_reliable_discovery.hashing import sha256_file
from esg_reliable_discovery.mineru_adapter import parse_with_mineru
from esg_reliable_discovery.p1_mineru_schedule import target_registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-pack", required=True)
    parser.add_argument("--acquisition-manifest", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--registry-output", required=True)
    parser.add_argument("--executable", default=".mineru-venv/bin/mineru")
    parser.add_argument("--tools-config", required=True)
    parser.add_argument(
        "--reuse",
        action="append",
        default=[],
        metavar="TARGET_ID=OUTPUT_DIRECTORY",
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    task_pack = json.loads(Path(args.task_pack).read_text(encoding="utf-8"))
    acquisition = json.loads(Path(args.acquisition_manifest).read_text(encoding="utf-8"))
    targets = target_registry(task_pack, acquisition)
    reuse = {}
    for item in args.reuse:
        target_id, separator, output_directory = item.partition("=")
        if not separator or not target_id or not output_directory:
            raise ValueError(f"Invalid --reuse value: {item}")
        reuse[target_id] = Path(output_directory)
    for target in targets:
        if target["target_id"] in reuse:
            destination = reuse[target["target_id"]]
            record = destination / "esg_rd_mineru_run.json"
            payload = json.loads(record.read_text(encoding="utf-8"))
            if payload.get("returncode") != 0:
                raise RuntimeError(f"Cannot reuse unsuccessful parse: {destination}")
            if payload.get("input_sha256") != target["document_sha256"]:
                raise RuntimeError(f"Cannot reuse source hash mismatch: {destination}")
            expected_page = target["pdf_page"] - 1
            if payload.get("start_page_zero_based") != expected_page:
                raise RuntimeError(f"Cannot reuse page mismatch: {destination}")
            target["output_directory"] = str(destination)
            target["status"] = "reused_verified_success"
            target["run_record_sha256"] = sha256_file(record)
            continue
        destination = Path(args.output_root) / target["target_id"]
        target["output_directory"] = str(destination)
        if args.execute:
            if destination.exists() and any(destination.iterdir()):
                record = destination / "esg_rd_mineru_run.json"
                if record.is_file() and json.loads(record.read_text()).get("returncode") == 0:
                    target["status"] = "reused_verified_success"
                    target["run_record_sha256"] = sha256_file(record)
                    continue
                raise RuntimeError(f"Refusing non-successful non-empty target: {destination}")
            record = parse_with_mineru(
                Path(args.raw_root) / target["local_path"],
                destination,
                executable=args.executable,
                backend="pipeline",
                method="auto",
                start_page=target["pdf_page"] - 1,
                end_page=target["pdf_page"] - 1,
                tools_config=args.tools_config,
            )
            target["status"] = "parsed"
            target["run_record_sha256"] = sha256_file(
                destination / "esg_rd_mineru_run.json"
            )
            target["output_file_count"] = len(record["output_files"])
        else:
            target["status"] = "planned"
    payload = {
        "schema_version": "1.0",
        "parser": "MinerU 3.4.0 pipeline",
        "unique_target_count": len(targets),
        "targets": targets,
    }
    Path(args.registry_output).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
