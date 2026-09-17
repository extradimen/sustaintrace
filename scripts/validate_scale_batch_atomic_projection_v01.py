from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from esg_reliable_discovery.native_table_corroboration import (
    corroborate_wrapped_table_cell,
)

ROOT = Path(__file__).resolve().parents[1]
FACTS = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_001_atomic_fact_records.jsonl"
)
GRAPHS = ROOT / "data/manifests/scale_batch_001_table_graphs.lock.json"
DIAGNOSTICS = ROOT / "data/results/scale_batch_001_diagnostics.lock.json"
OUTPUT = (
    ROOT
    / "data/knowledge_bases/v0.1/increments/scale_batch_001_atomic_validations.jsonl"
)
SUMMARY = ROOT / "data/results/scale_batch_001_atomic_validation.lock.json"
BATCH_ID = "KB-SCALE-BATCH-001-RESUME01"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def normalize(text: str) -> str:
    text = re.sub(r"[|*_#<>]", " ", text)
    return " ".join(text.split()).casefold()


def native_row_header_present(row_header: str, native: str) -> bool:
    """Corroborate a row label even when native PDF columns interrupt a wrapped label.

    Layout-preserving PDF extraction can interleave the right-hand page column between
    two visual lines of a left-hand table row.  Requiring each sufficiently specific
    row fragment, in document order, preserves fail-closed matching without pretending
    that the interrupted native text is contiguous.
    """
    normalized = normalize(row_header)
    if normalized in native:
        return True
    fragments = [normalize(item) for item in re.split(r"(?<=\))\s+(?=per\s)", row_header)]
    fragments = [item for item in fragments if len(item) >= 12]
    if len(fragments) < 2:
        return False
    positions = [native.find(item) for item in fragments]
    return all(position >= 0 for position in positions) and positions == sorted(positions)


def main() -> None:
    facts = load_jsonl(FACTS)
    graph_payload = json.loads(GRAPHS.read_text())
    diagnostics = json.loads(DIAGNOSTICS.read_text())
    native_pages = {
        item["document_id"]: (ROOT / item["layout_text_path"])
        .read_text(errors="replace")
        .split("\f")
        for item in diagnostics["documents"]
    }
    graph_cells = {
        cell["cell_handle"]: {
            **cell,
            "source_fact_record_id": source["source_fact_record_id"],
            "document_id": source["document_id"],
            "pdf_page": source["pdf_page"],
        }
        for source in graph_payload["graphs"]
        for graph in source["graphs"]
        for cell in graph["cells"]
    }
    records = []
    for fact in facts:
        evidence = fact["evidence"][0]
        handle = evidence["cell_handle"]
        graph = graph_cells.get(handle)
        graph_exact = graph is not None and graph["raw_value"] == evidence["quote"] and all(
            graph[key] == evidence[key]
            for key in (
                "table_index",
                "row_index",
                "column_index",
                "row_header",
                "column_header",
            )
        )
        document_id = fact["subject"]["document_ids"][0]
        page = evidence["pdf_page"]
        native_raw = native_pages[document_id][page - 1]
        native = normalize(native_raw)
        quote_present = normalize(evidence["quote"]) in native
        row_present = native_row_header_present(evidence["row_header"], native)
        wrapped_trace = None
        if not row_present and graph is not None:
            source_graph = next(
                source
                for source in graph_payload["graphs"]
                if source["document_id"] == document_id and source["pdf_page"] == page
            )
            table_graph = next(
                item
                for item in source_graph["graphs"]
                if item["table_index"] == evidence["table_index"]
            )
            wrapped_trace = corroborate_wrapped_table_cell(
                native_page=native_raw,
                row_header=evidence["row_header"],
                raw_value=evidence["quote"],
                column_headers=table_graph["column_headers"],
                row_header_column_index=evidence["row_header_column_index"],
                value_column_index=evidence["column_index"],
            )
            row_present = wrapped_trace["matched"]
        column_present = (
            normalize(evidence["column_header"]) in native
            or normalize(str(evidence["normalized_period"])) in native
        )
        coordinate_corroborated = graph_exact and quote_present and row_present and column_present
        records.append(
            {
                "schema_version": "0.1",
                "validation_id": "atomic-validation-"
                + hashlib.sha256(fact["record_id"].encode()).hexdigest()[:24],
                "fact_record_id": fact["record_id"],
                "document_id": document_id,
                "pdf_page": page,
                "cell_handle": handle,
                "checks": {
                    "table_graph_coordinate_exact": graph_exact,
                    "native_quote_present": quote_present,
                    "native_row_header_present": row_present,
                    "native_column_header_present": column_present,
                },
                "native_row_header_trace": wrapped_trace,
                "coordinate_corroborated": coordinate_corroborated,
                "independent_assurance_cell_scope_verified": False,
                "promotion_decision": "hold_tier_c",
                "promotion_reason": (
                    "coordinates corroborated across MinerU and native PDF text, but no "
                    "independent assurance conclusion is mapped to the individual cell"
                    if coordinate_corroborated
                    else "atomic cell failed one or more deterministic coordinate checks"
                ),
            }
        )
    OUTPUT.write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in records)
    )
    summary = {
        "schema_version": "0.1",
        "batch_id": BATCH_ID,
        "status": "atomic_validation_complete_fail_closed",
        "candidate_count": len(records),
        "table_graph_coordinate_exact_count": sum(
            item["checks"]["table_graph_coordinate_exact"] for item in records
        ),
        "native_quote_present_count": sum(
            item["checks"]["native_quote_present"] for item in records
        ),
        "native_row_header_present_count": sum(
            item["checks"]["native_row_header_present"] for item in records
        ),
        "native_column_header_present_count": sum(
            item["checks"]["native_column_header_present"] for item in records
        ),
        "coordinate_corroborated_count": sum(
            item["coordinate_corroborated"] for item in records
        ),
        "held_tier_c_count": len(records),
        "promoted_tier_b_count": 0,
        "output": {
            "path": OUTPUT.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        },
        "policy": {
            "native_parser_corroboration_is_not_external_assurance": True,
            "no_automatic_promotion": True,
            "locked_experiments_modified": False,
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
