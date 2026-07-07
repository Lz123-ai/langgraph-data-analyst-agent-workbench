from __future__ import annotations

import pandas as pd

from app.graph.workflow import build_analysis_workflow
from app.settings import settings


def _base_state(dataset_path, question: str):
    return {
        "dataset_id": "saas-business-intents",
        "file_path": str(dataset_path),
        "user_question": question,
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


def _write_saas_fixture():
    settings.ensure_directories()
    dataset_path = settings.upload_dir / "saas_business_intents.csv"
    pd.DataFrame(
        {
            "客户ID": ["CUST-001", "CUST-002", "CUST-001", "CUST-002", "CUST-003"],
            "公司名称": ["甲公司", "乙公司", "甲公司", "乙公司", "丙公司"],
            "统计月份": ["2025-11-01", "2025-11-01", "2025-12-01", "2025-12-01", "2025-12-01"],
            "注册后月份": [5, 8, 6, 9, 1],
            "月经常性收入MRR": [100.0, 200.0, 150.0, 250.0, 300.0],
            "续约风险": ["低", "中", "高", "低", "高"],
            "客户经理": ["Aiden", "Chloe", "Aiden", "Chloe", "Grace"],
            "付款状态": ["已支付", "逾期", "失败", "已支付", "逾期"],
            "发票金额": [100.0, 200.0, 150.0, 250.0, 300.0],
            "逾期天数": [0, 10, 5, 0, 30],
        }
    ).to_csv(dataset_path, index=False)
    return dataset_path


def test_mrr_snapshot_vs_cumulative_intent() -> None:
    dataset_path = _write_saas_fixture()

    state = build_analysis_workflow().invoke(_base_state(dataset_path, "当前 MRR 与累计 MRR 的口径区分。"))

    result = state["execution_result"]
    assert state["execution_path"] == "pandas"
    assert result["kind"] == "mrr_snapshot_vs_cumulative"
    rows = result["tables"][0]["rows"]
    assert rows[0]["口径"] == "当前 MRR"
    assert rows[0]["MRR"] == 700.0
    assert rows[1]["口径"] == "累计 MRR"
    assert rows[1]["MRR"] == 1000.0
    assert "不能当作当前 MRR" in state["report_markdown"]


def test_high_risk_customer_ranking_intent() -> None:
    dataset_path = _write_saas_fixture()

    state = build_analysis_workflow().invoke(_base_state(dataset_path, "12 月高风险客户和高风险 MRR 排名。"))

    result = state["execution_result"]
    assert state["execution_path"] == "pandas"
    assert result["kind"] == "risk_customer_ranking"
    ranking = result["tables"][0]["rows"]
    assert ranking[0]["客户ID"] == "CUST-003"
    assert ranking[0]["MRR"] == 300.0
    summary = result["tables"][1]["rows"][0]
    assert summary["客户数"] == 2
    assert summary["MRR"] == 450.0
    assert "高风险客户" in state["report_markdown"]


def test_payment_renewal_risk_business_template_intent() -> None:
    dataset_path = _write_saas_fixture()

    state = build_analysis_workflow().invoke(_base_state(dataset_path, "账款风险与续约风险联动分析。"))

    result = state["execution_result"]
    assert state["execution_path"] == "pandas"
    assert result["kind"] == "business_template_analysis"
    assert result["metrics"]["template_id"] == "payment_renewal_risk"
    assert result["tables"][0]["name"] == "payment_renewal_summary"
    assert result["tables"][0]["rows"][1]["发票金额"] == 450.0
    assert "账款" in state["report_markdown"]
