from esg_reliable_discovery.layout_fallback import (
    add_layout_adjacent_context,
    layout_line_records,
)

XML = """<doc><page><flow><block>
<line><word xMin="10" yMin="20" xMax="45" yMax="30">Scope</word>
<word xMin="48" yMin="20" xMax="54" yMax="30">3</word>
<word xMin="200" yMin="20" xMax="240" yMax="30">13,891</word></line>
<line><word xMin="10" yMin="40" xMax="50" yMax="50">Gross</word>
<word xMin="55" yMin="40" xMax="85" yMax="50">2025</word></line>
</block></flow></page></doc>"""


def test_layout_lines_preserve_text_coordinates_and_words() -> None:
    records = layout_line_records(XML)
    assert records[0]["text"] == "Scope 3 13,891"
    assert records[0]["bbox"] == [10.0, 20.0, 240.0, 30.0]
    assert records[0]["words"][2]["x_min"] == 200.0
    assert records[1]["line_index"] == 2


def test_layout_lines_tolerate_visible_pdf_control_glyphs_and_bare_ampersands() -> None:
    xml = (
        '<doc><line><word xMin="1" yMin="2" xMax="3" yMax="4">'
        "8\x07Upstream & Downstream"
        "</word></line></doc>"
    )
    assert layout_line_records(xml)[0]["text"] == "8Upstream & Downstream"


def test_continued_numeric_line_inherits_only_adjacent_explicit_year_context() -> None:
    handles = [
        {"handle": "P106-L0016", "verbatim_text": "calendar year 2024, AMD reported"},
        {"handle": "P106-L0017", "verbatim_text": "44,190 metric tCO2e"},
    ]
    augmented, links = add_layout_adjacent_context(handles)
    assert "2024" in augmented[1]["table_header_context"]
    assert links[0]["context_handle"] == "P106-L0016"
