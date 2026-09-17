from pathlib import Path

from esg_reliable_discovery.v14_pdf_vector import (
    _direct_fill_path_bbox,
    _parse_poppler_xml,
    _rectangle_bbox,
)


def test_v14_rectangle_path_parser_preserves_pdf_coordinates():
    path = "M 150.7 307.9 L 122.4 307.9 L 122.4 371.6 L 150.7 371.6 Z"
    assert _rectangle_bbox(path) == (122.4, 307.9, 150.7, 371.6)


def test_v14_rectangle_parser_rejects_non_rectangular_path():
    assert _rectangle_bbox("M 0 0 C 1 2 3 4 5 6 Z") is None


def test_v14_direct_fill_curve_bbox_supports_legend_markers():
    path = "M 10 20 C 12 20 14 22 14 24 C 14 26 12 28 10 28 C 8 28 6 26 6 24 Z"
    assert _direct_fill_path_bbox(path) == (6.0, 20.0, 14.0, 28.0)


def test_v14_poppler_xml_parser_removes_invalid_control_glyphs(tmp_path: Path):
    source = tmp_path / "page.xml"
    source.write_bytes(b"<doc><word xMin='1' yMin='2' xMax='3' yMax='4'>a\x0cb</word></doc>")
    root = _parse_poppler_xml(source)
    assert root.find("word").text == "ab"
