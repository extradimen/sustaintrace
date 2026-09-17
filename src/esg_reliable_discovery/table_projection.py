from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Any


class _TableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def parse_html_tables(text: str) -> list[list[list[str]]]:
    parser = _TableHTMLParser()
    parser.feed(text)
    return parser.tables


def _is_period_header(value: str) -> bool:
    return bool(
        re.search(r"(?<!\d)20\d{2}(?:/\d{2})?(?!\d)", value)
        or re.search(r"(?i)(?<![A-Z0-9])FY\s?\d{2,4}(?!\d)", value)
    )


def _normalized_period(value: str) -> int | str:
    match = re.search(r"(?<!\d)(20\d{2})(?:/\d{2})?(?!\d)", value)
    if match:
        return int(match.group(1))
    fiscal = re.search(r"(?i)(?<![A-Z0-9])FY\s?(\d{2,4})(?!\d)", value)
    if fiscal:
        literal = fiscal.group(1)
        return int(literal) if len(literal) == 4 else 2000 + int(literal)
    return value


def _header_index(headers: list[str], *names: str) -> int | None:
    normalized_names = {name.casefold() for name in names}
    return next(
        (
            index
            for index, header in enumerate(headers)
            if " ".join(header.split()).casefold() in normalized_names
        ),
        None,
    )


def _numeric_token_count(value: str) -> int:
    return len(re.findall(r"(?<!\w)\(?\d[\d,.]*\)?%?", value))


def _indicator_column_index(
    headers: list[str],
    body_rows: list[list[str]],
    period_columns: list[int],
    unit_column: int | None,
) -> int:
    explicit = _header_index(headers, "indicator", "metric")
    if explicit is not None:
        return explicit
    first_period = min(period_columns)
    candidates = [
        column_index for column_index in range(first_period) if column_index != unit_column
    ]
    scores: list[tuple[int, int]] = []
    for column_index in candidates:
        values = [
            row[column_index] for row in body_rows if len(row) == len(headers) and row[column_index]
        ]
        narrative = [
            value
            for value in values
            if re.search(r"[A-Za-z]", value)
            and not re.fullmatch(r"[A-Z]\d?[-_][A-Za-z0-9_-]+", value)
        ]
        scores.append((sum(len(value) for value in narrative), column_index))
    best_score, best_column = max(scores, default=(0, 0))
    return best_column if best_score else 0


def normalize_numeric_literal(value: str) -> dict[str, Any] | None:
    compact = " ".join(value.split())
    note_match = re.search(r"([⁰¹²³⁴⁵⁶⁷⁸⁹]+)$", compact)
    literal_annotation = note_match.group(1) if note_match else None
    if literal_annotation:
        compact = compact[: -len(literal_annotation)]
    match = re.fullmatch(r"\(?([0-9][0-9,]*(?:\.[0-9]+)?)\)?(%)?", compact)
    if not match:
        return None
    number = match.group(1).replace(",", "")
    negative = compact.startswith("(") and compact.endswith(")") and not match.group(2)
    if negative:
        number = "-" + number
    normalized = {
        "normalized_value": number,
        "normalized_unit": "percent" if match.group(2) else None,
    }
    if literal_annotation:
        normalized["literal_annotation"] = literal_annotation
    return normalized


def build_two_axis_table_graph(text: str) -> list[dict[str, Any]]:
    graphs = []
    for table_index, rows in enumerate(parse_html_tables(text)):
        header_index = next(
            (
                index
                for index, row in enumerate(rows)
                if len(row) >= 3 and sum(_is_period_header(cell) for cell in row[1:]) >= 2
            ),
            None,
        )
        if header_index is None:
            graphs.append(
                {
                    "table_index": table_index,
                    "status": "ambiguous_no_two_axis_period_header",
                    "rows": rows,
                    "cells": [],
                }
            )
            continue
        headers = rows[header_index]
        period_columns = [
            index for index, header in enumerate(headers) if _is_period_header(header)
        ]
        unit_column = _header_index(headers, "unit")
        indicator_column = _indicator_column_index(
            headers, rows[header_index + 1 :], period_columns, unit_column
        )
        cells = []
        rejected_rows = []
        for row_index, row in enumerate(rows[header_index + 1 :], start=header_index + 1):
            if len(row) != len(headers) or not row[indicator_column]:
                rejected_rows.append({"row_index": row_index, "reason": "shape_mismatch"})
                continue
            if any(_numeric_token_count(row[index]) > 1 for index in period_columns):
                rejected_rows.append(
                    {"row_index": row_index, "reason": "multiple_numeric_tokens_in_one_cell"}
                )
                continue
            for column_index in period_columns:
                raw_value = row[column_index]
                normalized = normalize_numeric_literal(raw_value)
                if normalized is None:
                    continue
                row_header = row[indicator_column]
                column_header = headers[column_index]
                unit = row[unit_column] if unit_column is not None else None
                identity = [
                    table_index,
                    row_index,
                    column_index,
                    row_header,
                    column_header,
                    unit,
                ]
                cells.append(
                    {
                        "cell_handle": "cell-"
                        + hashlib.sha256(repr(identity).encode()).hexdigest()[:20],
                        "table_index": table_index,
                        "row_index": row_index,
                        "column_index": column_index,
                        "row_header": row_header,
                        "row_header_column_index": indicator_column,
                        "column_header": column_header,
                        "normalized_period": _normalized_period(column_header),
                        "unit": unit,
                        "unit_column_index": unit_column,
                        "raw_value": raw_value,
                        **normalized,
                    }
                )
        graphs.append(
            {
                "table_index": table_index,
                "status": "two_axis_graph_built",
                "header_row_index": header_index,
                "column_headers": headers,
                "period_columns": period_columns,
                "indicator_column": indicator_column,
                "unit_column": unit_column,
                "rejected_rows": rejected_rows,
                "rows": rows,
                "cells": cells,
            }
        )
    return graphs
