import pytest

from esg_reliable_discovery.v17_postprocess import run_v17_postprocess


def test_v17_unified_postprocess_runs_all_three_operations():
    result = run_v17_postprocess(
        stage_a_output={
            "deterministic_calculation":{
                "executed_by":"deterministic_framework",
                "operation":"percentage_change",
                "result":-60,
            }
        },
        evidence=[
            {"handle":"E1","verbatim_text":"contributing to lower intensity"},
            {"handle":"E2","verbatim_text":"selected E&S KPIs"},
        ],
        threshold_claim={"operator":"more_than","threshold_percent":50},
        issuer_attribution="contributing to lower intensity",
        string_fragments=[
            {"evidence_handle":"E2","verbatim_value":"selected E&S KPIs"}
        ],
    )
    assert len(result["operations"]) == 3
    assert result["candidate_output_modified"] is False


def test_v17_unified_postprocess_requires_an_operation():
    with pytest.raises(ValueError, match="v17_no_postprocess_operation_requested"):
        run_v17_postprocess(stage_a_output={},evidence=[])
