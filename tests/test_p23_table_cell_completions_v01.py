import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_p23_completions_are_derived_and_cover_six_cells_if_present():
    path = ROOT / "data/knowledge_bases/v0.1/p23_table_cell_completions.jsonl"
    if not path.exists():
        return
    records = [json.loads(line) for line in path.read_text().splitlines() if line]
    assert len(records) == 6
    assert all(item["locked_graph_modified"] is False for item in records)
    assert {(item["row"], item["column"]) for item in records} == {
        (row, year)
        for row in ("UK energy", "renewable electricity", "high-stress supplied water")
        for year in ("2025", "2024")
    }
