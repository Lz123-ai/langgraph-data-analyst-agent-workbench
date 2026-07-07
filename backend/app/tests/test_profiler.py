from __future__ import annotations

import pandas as pd

from app.datasets.profiler import profile_dataframe


def test_profile_dataframe_detects_types_and_missingness() -> None:
    df = pd.DataFrame(
        {
            "category": ["A", "A", "B", None],
            "sales": [10.0, 20.0, 30.0, None],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", None],
        }
    )

    profile = profile_dataframe(df, dataset_id="test")

    assert profile.row_count == 4
    assert "sales" in profile.numeric_columns
    assert "category" in profile.categorical_columns
    assert "created_at" in profile.datetime_columns
    sales = next(column for column in profile.columns if column.name == "sales")
    assert sales.missing_count == 1
    assert sales.mean == 20.0


def test_profile_dataframe_infers_order_grain() -> None:
    df = pd.DataFrame(
        {
            "订单ID": ["SO-001", "SO-002", "SO-003"],
            "订单日期": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "销售额": [10, 20, 30],
        }
    )

    profile = profile_dataframe(df, dataset_id="orders")

    assert profile.grain is not None
    assert profile.grain.grain_type == "订单流水"
    assert profile.grain.grain_columns == ["订单ID"]
    assert profile.grain.time_field == "订单日期"
