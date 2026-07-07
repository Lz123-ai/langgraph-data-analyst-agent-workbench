from __future__ import annotations

import pandas as pd

from app.domain import AnalysisOperation
from app.tools.business_template_tool import run_business_template


def _operation(template_id: str, filters: list[str] | None = None) -> AnalysisOperation:
    return AnalysisOperation(
        operation_type="business_template_analysis",
        path_hint="pandas",
        metrics=[],
        dimensions=[],
        filters=[f"__template__={template_id}", *(filters or [])],
        aggregation=None,
        template_id=template_id,
        reason="test",
    )


def test_payment_renewal_risk_template() -> None:
    df = pd.DataFrame(
        {
            "客户ID": ["C1", "C2", "C3"],
            "公司名称": ["甲", "乙", "丙"],
            "统计月份": ["2025-12-01", "2025-12-01", "2025-12-01"],
            "月经常性收入MRR": [1000.0, 2000.0, 3000.0],
            "付款状态": ["已支付", "失败", "逾期"],
            "发票金额": [1000.0, 2000.0, 3000.0],
            "逾期天数": [0, 15, 60],
            "续约风险": ["低", "高", "中"],
            "客户经理": ["A", "B", "C"],
        }
    )

    result, _ = run_business_template(df, _operation("payment_renewal_risk", ["__month__=12"]))

    assert result.kind == "business_template_analysis"
    assert result.metrics["template_id"] == "payment_renewal_risk"
    summary = result.tables[0].rows
    assert summary[1]["发票金额"] == 5000.0
    priority = result.tables[1].rows
    assert priority[0]["客户ID"] == "C3"


def test_sales_templates_cover_overview_and_pareto() -> None:
    df = pd.DataFrame(
        {
            "订单ID": ["O1", "O2", "O3"],
            "商品名称": ["显示器", "显示器", "书桌"],
            "订单状态": ["已完成", "已取消", "已完成"],
            "销售额": [100.0, 200.0, 50.0],
            "利润": [30.0, 40.0, 20.0],
            "支付方式": ["微信支付", "银行转账", "微信支付"],
            "销售渠道": ["线上商城", "直播", "线上商城"],
            "折扣率": [0.0, 0.3, 0.1],
            "利润率": [0.3, 0.2, 0.4],
        }
    )

    overview, _ = run_business_template(df, _operation("sales_overview_status"))
    assert overview.tables[0].rows[0]["销售额"] == 350.0
    assert overview.tables[0].rows[1]["口径"] == "已完成订单"

    pareto, _ = run_business_template(df, _operation("product_pareto"))
    assert pareto.tables[0].rows[0]["商品名称"] == "显示器"
    assert pareto.tables[0].rows[0]["累计销售额占比"] > 0.8
