from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

from app.graph.workflow import build_analysis_workflow
from app.settings import settings


@dataclass(frozen=True)
class RegressionCase:
    question: str
    expected_kind: str
    expected_path: str
    first_row_contains: dict[str, Any]
    report_keywords: tuple[str, ...]


CASES = [
    RegressionCase(
        question="这个数据集有多少条订单、多少个原始字段？日期范围是什么？",
        expected_kind="dataset_overview",
        expected_path="duckdb_sql",
        first_row_contains={"row_count": 5, "column_count": 8},
        report_keywords=("5 行记录", "8 个原始字段", "日期范围"),
    ),
    RegressionCase(
        question="利润最高的商品名称是什么",
        expected_kind="top_records",
        expected_path="duckdb_sql",
        first_row_contains={"商品名称": "文件夹", "利润": 8000.0},
        report_keywords=("文件夹", "8000"),
    ),
    RegressionCase(
        question="上海哪类商品建议扩大市场",
        expected_kind="market_recommendation",
        expected_path="duckdb_sql",
        first_row_contains={"dimension": "家具"},
        report_keywords=("家具", "扩张机会", "上海"),
    ),
    RegressionCase(
        question="数据质量有哪些明显问题？",
        expected_kind="data_quality",
        expected_path="pandas",
        first_row_contains={"issue_type": "缺失值", "column": "客户评分"},
        report_keywords=("数据质量扫描", "缺失值", "客户评分"),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[case.expected_kind for case in CASES])
def test_natural_language_regression_cases(case: RegressionCase) -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "intent_regression.csv"
    pd.DataFrame(
        {
            "订单ID": ["SO-001", "SO-002", "SO-003", "SO-004", "SO-005"],
            "订单日期": ["2026-01-01", "2026-01-03", "2026-02-01", "2026-03-15", "2026-04-20"],
            "城市": ["上海", "上海", "上海", "北京", "上海"],
            "商品类别": ["家具", "家具", "办公", "办公", "家电"],
            "商品名称": ["桌子", "椅子", "纸张", "文件夹", "台灯"],
            "销售额": [8000.0, 9000.0, 1200.0, 20000.0, 3500.0],
            "利润": [2100.0, 2400.0, 300.0, 8000.0, 700.0],
            "客户评分": [5.0, None, 4.0, None, 3.0],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "intent-regression",
            "file_path": str(dataset_path),
            "user_question": case.question,
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

    assert state["execution_path"] == case.expected_path
    assert state["execution_result"]["kind"] == case.expected_kind
    first_row = state["execution_result"]["tables"][0]["rows"][0]
    for key, value in case.first_row_contains.items():
        assert first_row[key] == value
    for keyword in case.report_keywords:
        assert keyword in state["report_markdown"]


def test_compound_question_runs_multiple_operations() -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "compound_question_regression.csv"
    pd.DataFrame(
        {
            "订单ID": ["SO-001", "SO-002", "SO-003", "SO-004", "SO-005"],
            "订单日期": ["2026-01-01", "2026-01-03", "2026-02-01", "2026-03-15", "2026-04-20"],
            "城市": ["上海", "上海", "上海", "北京", "上海"],
            "商品类别": ["家具", "家具", "办公", "办公", "家电"],
            "商品名称": ["桌子", "椅子", "纸张", "文件夹", "台灯"],
            "销售额": [8000.0, 9000.0, 1200.0, 20000.0, 3500.0],
            "利润": [2100.0, 2400.0, 300.0, 8000.0, 700.0],
            "客户评分": [5.0, None, 4.0, None, 3.0],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "compound-question-regression",
            "file_path": str(dataset_path),
            "user_question": "这个数据集有多少条订单、多少个原始字段？日期范围是什么？利润最高的商品名称是什么？数据质量有哪些明显问题？",
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
            "sub_questions": [],
        }
    )

    result = state["execution_result"]
    assert result["kind"] == "multi_analysis"
    assert result["metrics"]["sub_result_count"] == 3
    assert {item["kind"] for item in result["metrics"]["sub_results"]} == {
        "dataset_overview",
        "top_records",
        "data_quality",
    }
    assert len(state["analysis_plan"]["operations"]) == 3
    assert "5 行记录" in state["report_markdown"]
    assert "文件夹" in state["report_markdown"]
    assert "客户评分" in state["report_markdown"]
    assert "子问题执行清单" in state["report_markdown"]


def test_missing_product_name_does_not_fallback_to_region() -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "missing_product_name_regression.csv"
    pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "region": ["East", "West", "North"],
            "category": ["Furniture", "Office", "Tech"],
            "sales": [1000.0, 3000.0, 2000.0],
            "profit": [120.0, 900.0, 300.0],
            "units": [2, 5, 3],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "missing-product-name-regression",
            "file_path": str(dataset_path),
            "user_question": "利润最高的商品名称是什么？",
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

    result = state["execution_result"]
    assert state["execution_path"] == "pandas"
    assert result["kind"] == "unanswerable_with_current_schema"
    assert result["metrics"]["metrics"] == ["profit"]
    assert "没有商品名称" in state["report_markdown"]
    assert "不能把地区" in state["report_markdown"]


def test_city_market_question_is_unanswerable_without_city_value() -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "missing_city_market_regression.csv"
    pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "region": ["East", "West", "North"],
            "category": ["Furniture", "Office", "Tech"],
            "sales": [1000.0, 3000.0, 2000.0],
            "profit": [120.0, 900.0, 300.0],
            "units": [2, 5, 3],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "missing-city-market-regression",
            "file_path": str(dataset_path),
            "user_question": "上海哪类商品建议扩大市场？",
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

    result = state["execution_result"]
    assert state["execution_path"] == "pandas"
    assert result["kind"] == "unanswerable_with_current_schema"
    assert "上海" in state["report_markdown"]
    assert "没有该取值" in state["report_markdown"] or "非城市字段" in state["report_markdown"]


def test_compound_question_keeps_unanswerable_sub_result() -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "compound_unanswerable_regression.csv"
    pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "region": ["East", "West", "North"],
            "category": ["Furniture", "Office", "Tech"],
            "sales": [1000.0, 3000.0, 2000.0],
            "profit": [120.0, 900.0, 300.0],
            "units": [2, 5, 3],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "compound-unanswerable-regression",
            "file_path": str(dataset_path),
            "user_question": "这个数据集有多少条订单、多少个原始字段？日期范围是什么？利润最高的商品名称是什么？数据质量有哪些明显问题？",
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
            "sub_questions": [],
        }
    )

    result = state["execution_result"]
    kinds = {item["kind"] for item in result["metrics"]["sub_results"]}
    assert result["kind"] == "multi_analysis"
    assert "dataset_overview" in kinds
    assert "unanswerable_with_current_schema" in kinds
    assert "data_quality" in kinds
    assert result["metrics"]["sub_result_count"] == len(state["sub_questions"])
    assert "状态：不可回答" in state["report_markdown"]


def test_pipeline_sort_modifier_is_not_split_as_extra_question() -> None:
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "pipeline_modifier_regression.csv"
    pd.DataFrame(
        {
            "销售负责人": ["Alice", "Bob", "Alice"],
            "商机金额": [1000.0, 2000.0, 500.0],
            "赢率": [0.5, 0.25, 1.0],
            "销售阶段": ["洽谈", "赢单", "赢单"],
        }
    ).to_csv(dataset_path, index=False)

    app = build_analysis_workflow()
    state = app.invoke(
        {
            "dataset_id": "pipeline-modifier-regression",
            "file_path": str(dataset_path),
            "user_question": "当前总 Pipeline、加权 Pipeline、赢单金额是多少？按销售负责人排序。",
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
            "sub_questions": [],
        }
    )

    assert state["execution_result"]["kind"] == "business_template_analysis"
    assert state["execution_result"]["metrics"]["template_id"] == "pipeline_summary"
    assert len(state["analysis_plan"]["operations"]) == 1
    assert state["sub_questions"] == []
