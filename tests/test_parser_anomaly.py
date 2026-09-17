from esg_reliable_discovery.parser_anomaly import assess_page_parser_anomaly


def test_table_triggers_layout_without_task_or_expected_value() -> None:
    result = assess_page_parser_anomaly(
        mineru_blocks=[{"type": "table", "table_body": "<table><td>13,891</td></table>"}],
        native_layout_text="Scope 3 13,891",
    )
    assert result["fallback_required"] is True
    assert result["reasons"] == ["mineru_table_detected"]
    assert result["task_text_used"] is False
    assert result["expected_value_used"] is False


def test_numeric_loss_triggers_when_no_table_was_detected() -> None:
    result = assess_page_parser_anomaly(
        mineru_blocks=[{"type": "text", "text": "2020 and 2024"}],
        native_layout_text="2020 61,754 2030 30,877 2024 44,190",
    )
    assert result["fallback_required"] is True
    assert "native_to_mineru_numeric_recall_below_threshold" in result["reasons"]


def test_clean_narrative_page_does_not_trigger() -> None:
    result = assess_page_parser_anomaly(
        mineru_blocks=[{"type": "text", "text": "In 2024 emissions fell 10.7%."}],
        native_layout_text="In 2024 emissions fell 10.7%.",
    )
    assert result["fallback_required"] is False
