import pytest

from esg_reliable_discovery.v17_causal_epistemics import (
    classify_attribution_and_causal_identification,
)
from esg_reliable_discovery.v17_multifragment import (
    project_grounded_string_fragments,
)
from esg_reliable_discovery.v17_threshold import (
    compare_recalculated_to_issuer_threshold,
)


def test_p7_sixty_percent_satisfies_more_than_fifty_claim_without_equality():
    result = compare_recalculated_to_issuer_threshold(
        deterministic_calculation={
            "executed_by":"deterministic_framework",
            "operation":"percentage_change",
            "result":-60.0,
        },
        issuer_claim={"operator":"more_than","threshold_percent":50},
    )
    assert result["comparison_state"] == (
        "recalculated_value_satisfies_issuer_threshold"
    )
    assert result["issuer_claim_converted_to_exact_value"] is False


def test_p7_issuer_attribution_does_not_become_independent_causality():
    result = classify_attribution_and_causal_identification(
        issuer_attribution="contributing to a group carbon intensity",
        evidence=[{
            "handle":"P24",
            "verbatim_text":(
                "assets divested and decommissioned have typically been of a higher "
                "average carbon intensity, contributing to a group carbon intensity"
            ),
        }],
    )
    assert result["issuer_attribution_state"] == (
        "issuer_attribution_verbatim_supported"
    )
    assert result["independent_causal_identification_state"] == (
        "not_independently_identified"
    )


def test_multifragment_projection_preserves_each_evidence_source():
    result = project_grounded_string_fragments(
        fragments=[
            {"evidence_handle":"E1","verbatim_value":"selected E&S KPIs"},
            {"evidence_handle":"E2","verbatim_value":"EU Taxonomy report"},
        ],
        evidence=[
            {"handle":"E1","verbatim_text":"Annex 1: selected E&S KPIs"},
            {"handle":"E2","verbatim_text":"Annex 3: EU Taxonomy report"},
        ],
    )
    assert result["value"] == "selected E&S KPIs | EU Taxonomy report"
    assert [item["evidence_handle"] for item in result["fragments"]] == ["E1", "E2"]


def test_multifragment_projection_fails_closed_on_ungrounded_fragment():
    with pytest.raises(ValueError, match="v17_fragment_not_grounded:2"):
        project_grounded_string_fragments(
            fragments=[
                {"evidence_handle":"E1","verbatim_value":"selected KPIs"},
                {"evidence_handle":"E2","verbatim_value":"invented scope"},
            ],
            evidence=[
                {"handle":"E1","verbatim_text":"selected KPIs"},
                {"handle":"E2","verbatim_text":"EU Taxonomy report"},
            ],
        )
