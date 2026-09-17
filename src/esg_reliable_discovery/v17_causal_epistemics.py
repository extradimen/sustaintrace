from __future__ import annotations

from typing import Any

from .v15_grounding import unicode_equivalent_substring


def classify_attribution_and_causal_identification(
    *, issuer_attribution: str | None, evidence: list[dict[str, Any]],
    identification_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Keep issuer attribution distinct from independently identified causality."""
    support = []
    if issuer_attribution:
        support = [
            item["handle"] for item in evidence
            if unicode_equivalent_substring(
                issuer_attribution, item.get("verbatim_text", "")
            )
        ]
    identification = identification_evidence or []
    return {
        "issuer_attribution_state":(
            "issuer_attribution_verbatim_supported" if support
            else "issuer_attribution_unsupported" if issuer_attribution
            else "issuer_attribution_not_proposed"
        ),
        "issuer_attribution_supporting_handles":support,
        "independent_causal_identification_state":(
            "independently_identified" if identification
            else "not_independently_identified"
        ),
        "identification_evidence_handles":[
            item["handle"] for item in identification
        ],
        "textual_attribution_does_not_equal_causal_identification":True,
        "framework_owned_classification":True,
    }
