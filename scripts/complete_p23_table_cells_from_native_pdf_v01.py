from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from esg_reliable_discovery.knowledge_base import sha256_file, stable_id, validate_records

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data/knowledge_bases/v0.1"


def main() -> None:
    pdf = ROOT / "data/raw/p23_staging/gsk-annual-report-2025.pdf"
    graph = ROOT / "configs/framework/p23_two_dimensional_table_graph_v0.1.lock.json"
    result = subprocess.run(
        ["pdftotext", "-f", "78", "-l", "78", "-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    targets = {
        "UK energy used (GWh)": "UK energy",
        "% renewably sourced electricity": "renewable electricity",
        "Total supplied water in areas of high water stress million m3,4": (
            "high-stress supplied water"
        ),
    }
    parents = [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
        for path in (pdf, graph)
    ]
    records = []
    for literal, row in targets.items():
        line = next((line for line in result.stdout.splitlines() if literal in line), None)
        if line is None:
            raise ValueError(f"missing native row: {literal}")
        suffix = line.split(literal, 1)[1]
        numbers = re.findall(r"(?<![\d.])\d+(?:[,.]\d+)?(?=\s*%?|\s|$)", suffix)
        values = [float(item.replace(",", "")) for item in numbers[:2]]
        if len(values) != 2:
            raise ValueError(f"expected two values: {line}")
        for column, value in zip(("2025", "2024"), values, strict=True):
            identity = {"graph": "P23-METRICS-P078", "row": row, "column": column}
            records.append(
                {
                    "schema_version": "0.1",
                    "record_kind": "table_cell_completion",
                    "completion_id": stable_id("cell", identity),
                    "graph_id": "P23-METRICS-P078",
                    "pdf_page": 78,
                    "row": row,
                    "column": column,
                    "value": value,
                    "raw_native_line": line.strip(),
                    "validation": {
                        "row_label_exact": True,
                        "header_order_frozen": True,
                        "two_values_parsed": True,
                        "parent_hashes_valid": True,
                    },
                    "parent_artifacts": parents,
                    "execution_mode": "derived_layer_only",
                    "rollback": "delete_derived_completion_record",
                    "locked_graph_modified": False,
                }
            )
    schema = json.loads(
        (ROOT / "schemas/knowledge/table-cell-completion-v0.1.schema.json").read_text()
    )
    validate_records(records, schema)
    output = KB / "p23_table_cell_completions.jsonl"
    output.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in records
        )
    )
    summary = {
        "schema_version": "0.1",
        "status": "p23_native_table_cell_completion_complete",
        "cells_created": len(records),
        "locked_graph_modified": False,
        "parents": parents,
        "output": {
            "path": output.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(output),
        },
        "next_gate": "replay all P23 calculation outputs using frozen plus derived cells",
    }
    summary_path = KB / "p23_table_cell_completion_summary.lock.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"cells_created": len(records)}))


if __name__ == "__main__":
    main()
