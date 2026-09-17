from esg_reliable_discovery.v11_table_cells import table_cell_records


def test_splits_progress_from_target_years() -> None:
    html = """<table>
    <tr><td>Topic</td><td>2030 Goal</td><td>Progress</td></tr>
    <tr><td>Supply Chain Emissions</td>
    <td>Reduce by 40% per unit (2020 baseline)</td><td>9% reduction</td></tr>
    </table>"""
    cells = table_cell_records(html)
    progress = next(cell for cell in cells if cell["column_header"] == "Progress")
    assert progress["text"] == "9% reduction"
    assert "2030" not in progress["text"]
    assert "2020" not in progress["text"]
    assert (
        progress["row_label_context"]
        == "Supply Chain Emissions | Reduce by 40% per unit (2020 baseline)"
    )
    assert progress["semantic_row_context"] == "Supply Chain Emissions | per unit"
