from esg_reliable_discovery.native_table_corroboration import corroborate_wrapped_table_cell

PAGE = """                                          Baseline year
Target, m3/tonne       Scope                 and value    2025      2024
Decrease in process
water discharges per   Selected board,
saleable tonne of      pulp, and paper      2019: 36 m3     32        34
board, pulp, and paper production sites
by 17% by 2030
Continuous target on
decreasing the trend   All board, pulp,
for total water        and paper            2016: 60 m3
                                                           56        60
withdrawal per         production sites
saleable tonne
"""

HEADERS = ["Target, m³/tonne", "Scope", "Baseline year and value", "2025", "2024"]


def test_wrapped_row_is_bound_to_same_table_value_column() -> None:
    result = corroborate_wrapped_table_cell(
        native_page=PAGE,
        row_header=(
            "Decrease in process water discharges per saleable tonne of board, pulp, "
            "and paper by 17% by 2030"
        ),
        raw_value="32",
        column_headers=HEADERS,
        row_header_column_index=0,
        value_column_index=3,
    )
    assert result["matched"] is True
    assert result["candidate_matches"] == 1


def test_row_cannot_be_rebound_to_other_rows_value() -> None:
    result = corroborate_wrapped_table_cell(
        native_page=PAGE,
        row_header=(
            "Decrease in process water discharges per saleable tonne of board, pulp, "
            "and paper by 17% by 2030"
        ),
        raw_value="56",
        column_headers=HEADERS,
        row_header_column_index=0,
        value_column_index=3,
    )
    assert result["matched"] is False


def test_duplicate_row_value_binding_fails_closed() -> None:
    duplicated = PAGE + "\n" + PAGE
    result = corroborate_wrapped_table_cell(
        native_page=duplicated,
        row_header=(
            "Decrease in process water discharges per saleable tonne of board, pulp, "
            "and paper by 17% by 2030"
        ),
        raw_value="32",
        column_headers=HEADERS,
        row_header_column_index=0,
        value_column_index=3,
    )
    assert result["matched"] is False
