from __future__ import annotations

from typing import Any


def bind_table_column_periods(
    *,
    inputs: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    required_years: list[int],
) -> dict[str, Any]:
    """Bind values to explicit two-dimensional table headers, failing closed."""
    index = {cell["handle"]: cell for cell in cells}
    if len(index) != len(cells):
        raise ValueError("v19_table_cell_handles_must_be_unique")
    if len(inputs) != len(required_years):
        raise ValueError("v19_input_year_arity_mismatch")
    bindings = []
    observed_years = []
    for item in inputs:
        handle = item["evidence_handle"]
        if handle not in index:
            raise ValueError(f"v19_unknown_table_cell:{handle}")
        cell = index[handle]
        year = int(item["period_year"])
        if str(year) != str(cell.get("column_header", "")).strip():
            raise ValueError(f"v19_column_year_not_grounded:{handle}:{year}")
        if not str(cell.get("row_header", "")).strip():
            raise ValueError(f"v19_row_header_missing:{handle}")
        if str(item["value"]).strip() != str(cell.get("verbatim_value", "")).strip():
            raise ValueError(f"v19_table_value_not_verbatim:{handle}")
        observed_years.append(year)
        bindings.append(
            {
                **item,
                "row_header": cell["row_header"],
                "column_header": str(year),
                "binding_rule": "same_cell_explicit_column_header",
            }
        )
    if observed_years != required_years:
        raise ValueError("v19_required_year_order_mismatch")
    return {
        "bindings": bindings,
        "two_dimensional_grounding": True,
        "candidate_output_modified": False,
    }
