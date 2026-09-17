import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from esg_reliable_discovery.open_review import compare_independent_reviews

ROOT = Path(__file__).parents[1]
CANDIDATE_HASH = "a" * 64


def _review(round_name: str, reviewer_id: str) -> dict:
    return {
        "review_id": f"review-{round_name}",
        "task_id": "P0-OPEN-001",
        "candidate_finding_id": "finding-001",
        "candidate_sha256": CANDIDATE_HASH,
        "reviewer_id": reviewer_id,
        "review_round": round_name,
        "blindness_attestation": {
            "model_identity_hidden": True,
            "other_review_hidden": True,
            "candidate_order_randomized": True,
        },
        "fatal_checks": {
            "claim_correctness": {"rating": "pass", "rationale": "Directly stated."},
            "evidence_entailment": {"rating": "pass", "rationale": "Evidence entails claim."},
            "evidence_locator_valid": {"rating": "pass", "rationale": "Page can be verified."},
        },
        "dimensions": {
            "boundary_fidelity": {"rating": 2, "rationale": "All boundaries retained."},
            "novelty": {"rating": 1, "rationale": "Useful synthesis."},
            "decision_relevance": {"rating": 2, "rationale": "Decision relevant."},
            "falsifiability": {"rating": 2, "rationale": "Clear falsifier."},
            "non_redundancy": {"rating": 2, "rationale": "Distinct claim."},
        },
        "duplicate_cluster_id": None,
        "disposition": "accept",
        "review_notes": "",
        "reviewed_at": "2026-09-01T12:00:00Z",
    }


def test_open_review_and_adjudication_schemas_are_valid():
    review_schema = json.loads(
        (ROOT / "templates/open_discovery_review.schema.json").read_text(encoding="utf-8")
    )
    adjudication_schema = json.loads(
        (ROOT / "templates/open_discovery_adjudication.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(review_schema)
    Draft202012Validator.check_schema(adjudication_schema)
    Draft202012Validator(review_schema).validate(_review("independent_A", "reviewer-A"))


def test_identical_reviews_have_full_dimension_agreement():
    schema = json.loads(
        (ROOT / "templates/open_discovery_review.schema.json").read_text(encoding="utf-8")
    )
    review_a = _review("independent_A", "reviewer-A")
    review_b = _review("independent_B", "reviewer-B")
    result = compare_independent_reviews([review_a], [review_b], schema)
    assert result["paired_candidate_count"] == 1
    assert result["adjudication_queue"] == []
    assert result["aggregate_score"] is None
    for metric in result["dimension_agreement"].values():
        assert metric["exact_agreement"] == 1
        assert metric["cohen_kappa"] == 1


def test_disagreement_enters_queue_without_overwriting_reviews():
    schema = json.loads(
        (ROOT / "templates/open_discovery_review.schema.json").read_text(encoding="utf-8")
    )
    review_a = _review("independent_A", "reviewer-A")
    review_b = _review("independent_B", "reviewer-B")
    original_a = deepcopy(review_a)
    review_b["fatal_checks"]["claim_correctness"] = {
        "rating": "fail",
        "rationale": "The scope is overstated.",
    }
    review_b["disposition"] = "revise_boundary"

    result = compare_independent_reviews([review_a], [review_b], schema)

    assert result["adjudication_queue"] == [
        {
            "candidate_sha256": CANDIDATE_HASH,
            "disputed_fields": ["claim_correctness", "disposition"],
        }
    ]
    assert review_a == original_a
    assert review_b["disposition"] == "revise_boundary"


def test_unpaired_candidates_are_reported():
    schema = json.loads(
        (ROOT / "templates/open_discovery_review.schema.json").read_text(encoding="utf-8")
    )
    review_a = _review("independent_A", "reviewer-A")
    result = compare_independent_reviews([review_a], [], schema)
    assert result["paired_candidate_count"] == 0
    assert result["unpaired_candidate_hashes"]["A_only"] == [CANDIDATE_HASH]
