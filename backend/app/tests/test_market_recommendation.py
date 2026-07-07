from __future__ import annotations

import pandas as pd

from app.graph.workflow import build_analysis_workflow
from app.settings import settings


def test_workflow_answers_market_expansion_recommendation_for_city() -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "market_recommendation_test.csv"
    pd.DataFrame(
        {
            "城市": ["上海", "上海", "上海", "上海", "北京"],
            "商品类别": ["家具", "家具", "办公", "办公", "办公"],
            "商品名称": ["桌子", "椅子", "纸张", "笔", "文件夹"],
            "销售额": [8000.0, 7000.0, 1200.0, 900.0, 20000.0],
            "利润": [2400.0, 2100.0, 300.0, 200.0, 8000.0],
            "数量": [8, 7, 12, 10, 30],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "market-recommendation-test",
            "file_path": str(dataset_path),
            "user_question": "上海哪类商品建议扩大市场",
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
    assert state["execution_result"]["kind"] == "market_recommendation"
    rows = state["execution_result"]["tables"][0]["rows"]
    assert rows[0]["dimension"] == "家具"
    assert rows[0]["total_profit"] == 4500.0
    assert "上海" in state["sql_queries"][0]
    assert "家具" in state["report_markdown"]
