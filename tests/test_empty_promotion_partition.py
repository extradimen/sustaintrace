from scripts.promote_scale_batch_019_six_dimension_facts_v01 import (
    promotion_already_applied,
)


def test_empty_promotion_partition_is_not_treated_as_already_applied() -> None:
    assert not promotion_already_applied({}, set(), set())


def test_nonempty_partition_requires_both_outputs() -> None:
    promotable = {"fact-1": ("DOC", "unit")}
    assert promotion_already_applied(promotable, {"fact-1"}, {"fact-1"})
    assert not promotion_already_applied(promotable, {"fact-1"}, set())
