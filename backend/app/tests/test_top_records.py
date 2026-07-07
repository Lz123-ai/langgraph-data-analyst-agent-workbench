from __future__ import annotations

import pandas as pd

from app.graph.workflow import build_analysis_workflow
from app.settings import settings


def test_workflow_answers_highest_profit_product_name() -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "top_records_test.csv"
    pd.DataFrame(
        {
            "商品名称": ["产品A", "产品B", "产品C"],
            "利润": [120.0, 530.0, 310.0],
            "销售额": [1000.0, 1800.0, 1500.0],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "top-records-test",
            "file_path": str(dataset_path),
            "user_question": "利润最高的商品名称是什么",
            "profile": None,
            "messages": [],
            "analysis_plan": None,
            "execution_path": None,
            "sql_queries": [],
            "generated_code": [],
            "execution_result": None,
            "charts": [],
            "insights": [],
            "review_notes": [],
            "report_markdown": None,
            "errors": [],
            "needs_clarification": False,
            "current_step": "queued",
            "dataset_preview": [],
        }
    )

    assert state["execution_path"] == "duckdb_sql"
    assert state["execution_result"]["kind"] == "top_records"
    rows = state["execution_result"]["tables"][0]["rows"]
    assert rows[0]["商品名称"] == "产品B"
    assert rows[0]["利润"] == 530.0
    assert "产品B" in state["report_markdown"]
