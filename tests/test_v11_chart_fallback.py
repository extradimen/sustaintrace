from esg_reliable_discovery.v11_chart_fallback import select_exact_scope_row_from_bbox_xml

XML = """<doc><page>
<line><word xMin="371" yMin="370.3" xMax="396" yMax="382.4">Scope</word></line>
<line><word xMin="399" yMin="370.3" xMax="404" yMax="382.4">3</word></line>
<line><word xMin="527" yMin="370.3" xMax="567" yMax="382.4">8,151,769</word></line>
<line><word xMin="391" yMin="395.3" xMax="413" yMax="404.8">Scope</word></line>
<line><word xMin="415" yMin="395.3" xMax="420" yMax="404.8">3</word></line>
<line><word xMin="570" yMin="395.3" xMax="605" yMax="404.8">8,151,825</word></line>
</page></doc>"""


def test_selects_larger_visible_font_duplicate_without_reference_value() -> None:
    selected = select_exact_scope_row_from_bbox_xml(XML, "What Scope 3 emissions were reported?")
    assert selected is not None
    assert selected["value_text"] == "8,151,769"
    assert selected["candidate_count"] == 2


def test_ignores_question_without_scope_metric() -> None:
    assert select_exact_scope_row_from_bbox_xml(XML, "What was water use?") is None
