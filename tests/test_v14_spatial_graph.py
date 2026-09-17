import pytest

from esg_reliable_discovery.v14_spatial_graph import (
    SpatialNode,
    build_spatial_relation_graph,
    collect_rightward_text,
    project_colored_chart_values,
    project_table_cell,
)


def _nodes():
    return [
        SpatialNode("h2024", "column_header", "2024", (90, 10, 110, 20), 50),
        SpatialNode("row_water", "row_header", "Water consumed", (10, 40, 70, 50), 50),
        SpatialNode("c_water_2024", "value", "45.0", (90, 40, 110, 50), 50, "#0085ca"),
        SpatialNode("legend_consumed", "legend", "Consumed", (150, 70, 200, 80), 50, "#0085ca"),
        SpatialNode("bar_consumed", "shape", "", (85, 35, 115, 55), 50, "#0085ca"),
        SpatialNode("dot_consumed", "shape", "", (135, 71, 141, 77), 50, "#0085ca"),
        SpatialNode("legend_water", "text", "water", (202, 70, 225, 80), 50),
    ]


def test_v14_graph_records_row_column_and_fill_relations():
    graph = build_spatial_relation_graph(_nodes())
    relations = {(edge["source"], edge["target"], edge["relation"]) for edge in graph["edges"]}
    assert ("row_water", "c_water_2024", "same_row_left_of") in relations
    assert ("h2024", "c_water_2024", "same_column_above") in relations
    assert ("c_water_2024", "legend_consumed", "same_fill") in relations
    assert ("bar_consumed", "c_water_2024", "contains_center") in relations
    assert ("dot_consumed", "legend_consumed", "nearest_right_text") in relations


def test_v14_marker_label_collects_contiguous_tokens():
    graph = build_spatial_relation_graph(_nodes())
    result = collect_rightward_text(graph, shape_id="dot_consumed")
    assert result["label"] == "Consumed water"


def test_v14_chart_projection_joins_fill_label_and_contained_value():
    graph = build_spatial_relation_graph(_nodes())
    rows = project_colored_chart_values(graph)
    assert rows[0]["series_label"] == "Consumed water"
    assert rows[0]["value_text"] == "45.0"
    assert rows[0]["value_relation"] == "contains_center"


def test_v14_cell_projection_preserves_coordinates_and_labels():
    graph = build_spatial_relation_graph(_nodes())
    result = project_table_cell(graph, row_label_id="row_water", column_header_id="h2024")
    assert result["cell"]["text"] == "45.0"
    assert result["cell"]["bbox"] == [90, 40, 110, 50]
    assert result["row_label"]["text"] == "Water consumed"
    assert result["column_header"]["text"] == "2024"


def test_v14_projection_fails_closed_without_a_cell():
    graph = build_spatial_relation_graph(_nodes()[:2])
    with pytest.raises(ValueError, match="spatial_cell_not_found"):
        project_table_cell(graph, row_label_id="row_water", column_header_id="h2024")


def test_v14_duplicate_node_ids_are_rejected():
    node = SpatialNode("same", "cell", "1", (0, 0, 1, 1), 1)
    with pytest.raises(ValueError, match="spatial_node_ids_must_be_unique"):
        build_spatial_relation_graph([node, node])
