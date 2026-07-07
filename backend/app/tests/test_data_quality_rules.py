from __future__ import annotations

import pandas as pd

from app.domain import AnalysisOperation
from app.tools.pandas_tool import run_pandas_operation


def test_data_quality_returns_business_rule_details() -> None:
    df = pd.DataFrame(
        {
            "订单ID": ["SO-001", "SO-001", "SO-003"],
            "数量": [1, 2, 3],
            "单价": [100.0, 50.0, 0.0],
            "折扣率": [0.0, 0.0, 0.0],
            "销售额": [100.0, 100.0, 0.0],
            "成本": [70.0, 120.0, 0.0],
            "利润": [30.0, -20.0, 0.0],
            "利润率": [0.3, -0.2, 0.0],
        }
    )
    operation = AnalysisOperation(
        operation_type="data_quality",
        path_hint="pandas",
        metrics=[],
        dimensions=[],
        filters=[],
        aggregation=None,
        reason="test",
    )

    result, _ = run_pandas_operation(df, operation)

    issue_rows = result.tables[0].rows
    issue_types = {row["issue_type"] for row in issue_rows}
    assert "重复业务键" in issue_types
    assert "零值金额" in issue_types
    assert "负利润" in issue_types
    assert len(result.tables) == 2
    detail_rows = result.tables[1].rows
    assert any(row["issue_type"] == "重复业务键" and row["订单ID"] == "SO-001" for row in detail_rows)
    assert result.metrics["detail_row_count"] >= 3
