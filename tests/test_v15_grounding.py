from esg_reliable_discovery.p1_v07 import finalize_v07_output
from esg_reliable_discovery.v13_atomic_projection import validate_and_project_slots
from esg_reliable_discovery.v14_spatial_graph import SpatialNode, build_spatial_relation_graph
from esg_reliable_discovery.v15_grounding import bind_period_headers_from_spatial_graph


def test_spatial_period_binding_makes_year_grounded_without_changing_cell_text():
    handles = [
        {"handle": "H1", "source_id": "D", "page": 1,
         "block_type": "table_cell", "normalized_text": "1,569",
         "verbatim_text": "1,569"},
        {"handle": "H2", "source_id": "D", "page": 1,
         "block_type": "table_cell", "normalized_text": "1,695",
         "verbatim_text": "1,695"},
    ]
    graph = build_spatial_relation_graph([
        SpatialNode("year25", "value", "2025", (100, 10, 120, 20), 1),
        SpatialNode("year24", "value", "2024", (200, 10, 220, 20), 1),
        SpatialNode("value25", "value", "1,569", (100, 50, 120, 60), 1),
        SpatialNode("value24", "value", "1,695", (200, 50, 220, 60), 1),
    ])
    augmented, bindings = bind_period_headers_from_spatial_graph(handles, graph)
    assert [item["period_header_context"] for item in augmented] == ["2025", "2024"]
    assert augmented[0]["normalized_text"] == "1,569"
    assert len(bindings) == 2
    result = finalize_v07_output(
        {"calculation_request": {"operation": "percentage_change", "inputs": [
            {"value": 1569, "period_year": 2025, "evidence_handle": "H1"},
            {"value": 1695, "period_year": 2024, "evidence_handle": "H2"},
        ]}},
        "deterministic_calculation",
        augmented,
    )
    assert result["deterministic_calculation"]["result"] < 0


def test_spatial_period_binding_fails_closed_on_duplicate_value_nodes():
    handles = [{"handle": "H1", "page": 1, "block_type": "table_cell", "normalized_text": "10"}]
    graph = build_spatial_relation_graph([
        SpatialNode("year", "value", "2025", (10, 0, 20, 10), 1),
        SpatialNode("value1", "value", "10", (10, 20, 20, 30), 1),
        SpatialNode("value2", "value", "10", (10, 40, 20, 50), 1),
    ])
    augmented, bindings = bind_period_headers_from_spatial_graph(handles, graph)
    assert "period_header_context" not in augmented[0]
    assert bindings == []


def test_unicode_apostrophe_equivalence_preserves_model_and_source_literals():
    output = validate_and_project_slots(
        model_output={"slots": [{
            "slot_id": "boundary",
            "value": "brands' company-operated stores",
            "verbatim_value": "brands' company-operated stores",
            "evidence_handle": "E1",
        }]},
        evidence=[{"handle": "E1", "verbatim_text": "brands’ company-operated stores"}],
        required_slots=[{
            "slot_id": "boundary", "value_type": "string", "predicate_id": "includes"
        }],
        framework_subject={"entity_id": "ORG", "entity_label": "Issuer"},
    )
    claim = output["validated_claims"][0]
    assert claim["verbatim_value"] == "brands' company-operated stores"
    assert claim["source_verbatim_preserved"] is True


def test_unicode_comparison_does_not_accept_semantic_paraphrase():
    try:
        validate_and_project_slots(
            model_output={"slots": [{
                "slot_id": "boundary", "value": "retail sites",
                "verbatim_value": "retail sites", "evidence_handle": "E1",
            }]},
            evidence=[{"handle": "E1", "verbatim_text": "company-operated stores"}],
            required_slots=[{
                "slot_id": "boundary", "value_type": "string", "predicate_id": "includes"
            }],
            framework_subject={"entity_id": "ORG", "entity_label": "Issuer"},
        )
    except ValueError as error:
        assert "v13_verbatim_not_grounded" in str(error)
    else:
        raise AssertionError("semantic paraphrase must not be accepted")
