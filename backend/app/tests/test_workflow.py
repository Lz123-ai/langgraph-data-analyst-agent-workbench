from __future__ import annotations

import pandas as pd

from app.graph.workflow import build_analysis_workflow
from app.settings import settings


def test_workflow_runs_duckdb_group_analysis() -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "workflow_test.csv"
    pd.DataFrame(
        {
            "category": ["A", "A", "B", "B", "C"],
            "sales": [10, 15, 25, 30, 8],
            "cost": [5, 7, 10, 12, 4],
            "date": ["2026-01-01", "2026-01-02", "2026-02-01", "2026-02-02", "2026-03-01"],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "workflow-test",
            "file_path": str(dataset_path),
            "user_question": "按 category 统计 sales 最高的类别",
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
    assert state["execution_result"]["source"] == "duckdb"
    assert state["charts"]
    assert "数据分析报告" in state["report_markdown"]
    assert "业务粒度" in state["report_markdown"]
    assert state["insights"]
