from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from .v14_spatial_graph import SpatialNode, build_spatial_relation_graph

_RECTANGLE_PATH = re.compile(
    r"M\s+([\d.]+)\s+([\d.]+)\s+L\s+([\d.]+)\s+([\d.]+)\s+"
    r"L\s+([\d.]+)\s+([\d.]+)\s+L\s+([\d.]+)\s+([\d.]+)\s+Z"
)


def _parse_poppler_xml(path: Path) -> ElementTree.Element:
    """Parse Poppler XML after removing PDF control glyphs invalid in XML 1.0."""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = "".join(
        character
        for character in text
        if character in "\t\n\r" or ord(character) >= 0x20
    )
    return ElementTree.fromstring(text)


def _rectangle_bbox(path_data: str) -> tuple[float, float, float, float] | None:
    match = _RECTANGLE_PATH.search(path_data)
    if not match:
        return None
    values = [float(value) for value in match.groups()]
    xs, ys = values[0::2], values[1::2]
    if len(set(xs)) != 2 or len(set(ys)) != 2:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _direct_fill_path_bbox(path_data: str) -> tuple[float, float, float, float] | None:
    rectangle = _rectangle_bbox(path_data)
    if rectangle is not None:
        return rectangle
    numbers = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", path_data)]
    if len(numbers) < 4 or len(numbers) % 2:
        return None
    xs, ys = numbers[0::2], numbers[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def graph_pdf_page_vectors(pdf_path: Path, page: int) -> dict:
    """Extract Poppler text boxes and colored vector rectangles into one graph."""
    if page < 1:
        raise ValueError("page_must_be_one_based")
    with tempfile.TemporaryDirectory(prefix="esg-v14-vector-") as directory:
        root = Path(directory)
        svg_path = root / "page.svg"
        bbox_path = root / "page.xml"
        subprocess.run(
            ["pdftocairo", "-f", str(page), "-l", str(page), "-svg",
             str(pdf_path), str(svg_path)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["pdftotext", "-f", str(page), "-l", str(page), "-bbox-layout",
             str(pdf_path), str(bbox_path)],
            check=True,
            capture_output=True,
        )
        nodes: list[SpatialNode] = []
        bbox_root = _parse_poppler_xml(bbox_path)
        for index, word in enumerate(bbox_root.findall(".//{*}word")):
            nodes.append(SpatialNode(
                node_id=f"p{page:04d}-word-{index:04d}",
                kind="value" if re.fullmatch(r"[-+]?\d[\d,.]*", word.text or "") else "text",
                text=word.text or "",
                bbox=tuple(float(word.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax")),
                page=page,
            ))
        svg_root = ElementTree.parse(svg_path).getroot()
        shape_index = 0
        for path in svg_root.findall(".//{*}path"):
            fill = path.attrib.get("fill")
            bbox = _direct_fill_path_bbox(path.attrib.get("d", ""))
            if bbox is None or fill in {None, "rgb(0%, 0%, 0%)", "rgb(100%, 100%, 100%)"}:
                continue
            nodes.append(SpatialNode(
                node_id=f"p{page:04d}-shape-{shape_index:04d}",
                kind="shape",
                text="",
                bbox=bbox,
                page=page,
                fill=fill,
            ))
            shape_index += 1
    graph = build_spatial_relation_graph(nodes)
    graph["source_pdf"] = str(pdf_path)
    graph["source_page"] = page
    graph["extractors"] = ["pdftotext -bbox-layout", "pdftocairo -svg"]
    graph["coordinate_axis"] = "x rightward, y downward"
    return graph
