from __future__ import annotations

from html.parser import HTMLParser


class _Cells(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def table_cell_records(table_body: str) -> list[dict]:
    parser = _Cells()
    parser.feed(table_body)
    if not parser.rows:
        return []
    headers = parser.rows[0]
    records = []
    for row_index, row in enumerate(parser.rows[1:], start=1):
        column_offset = max(0, len(headers) - len(row))
        row_labels = [cell for cell in row[:2] if cell]
        semantic_terms = []
        if row and row[0]:
            semantic_terms.append(row[0])
        if any("per unit" in cell.casefold() for cell in row):
            semantic_terms.append("per unit")
        for column_index, cell in enumerate(row):
            if not cell:
                continue
            effective_column = column_index + column_offset
            header = headers[effective_column] if effective_column < len(headers) else None
            records.append(
                {
                    "row_index": row_index,
                    "column_index": effective_column,
                    "text": cell,
                    "column_header": header,
                    "row_label_context": " | ".join(row_labels),
                    "semantic_row_context": " | ".join(semantic_terms),
                }
            )
    return records
