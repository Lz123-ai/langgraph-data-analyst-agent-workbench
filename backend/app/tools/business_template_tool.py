from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.domain import AnalysisOperation, ExecutionResult, ExecutionTable
from app.tools.serialization import dataframe_to_records, to_jsonable
from app.tools.time_scope import latest_complete_period, period_filters, start_end_period_filters


def run_business_template(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    template_id = operation.template_id or _template_from_filters(operation.filters)
    if template_id == "payment_renewal_risk":
        return _payment_renewal_risk(df, operation)
    if template_id == "customer_success_priority":
        return _customer_success_priority(df, operation)
    if template_id == "channel_performance_risk":
        return _channel_performance_risk(df, operation)
    if template_id == "industry_market_selection":
        return _industry_market_selection(df, operation)
    if template_id == "segment_plan_strategy":
        return _segment_plan_strategy(df, operation)
    if template_id == "expansion_contraction":
        return _expansion_contraction(df, operation)
    if template_id == "health_signal_analysis":
        return _health_signal_analysis(df, operation)
    if template_id == "sales_overview_status":
        return _sales_overview_status(df, operation)
    if template_id == "order_status_impact":
        return _order_status_impact(df, operation)
    if template_id == "product_pareto":
        return _product_pareto(df, operation)
    if template_id == "discount_profit_sensitivity":
        return _discount_profit_sensitivity(df, operation)
    if template_id == "payment_mix":
        return _payment_mix(df, operation)
    if template_id == "sales_channel_strategy":
        return _sales_channel_strategy(df, operation)
    if template_id == "pipeline_summary":
        return _pipeline_summary(df, operation)
    raise ValueError(f"未支持的业务分析模板：{template_id}")


def _payment_renewal_risk(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    payment_col = _require_column(columns, ["付款状态", "支付状态", "payment"])
    invoice_col = _require_column(columns, ["发票金额", "应收金额", "逾期金额", "账单金额", "开票金额", "invoice_amount", "ar_amount", "invoice", "amount"])
    overdue_col = _find_column(columns, ["逾期天数", "overdue_days", "days overdue"])
    risk_col = _find_column(columns, ["续约风险", "风险等级", "risk"])
    mrr_col = _find_column(columns, ["月经常性收入MRR", "mrr", "月经常性收入"])
    time_col = _find_column(columns, ["统计月份", "月份", "month", "date", "日期"])
    customer_col = _find_column(columns, ["客户ID", "customer_id", "customer id"])
    company_col = _find_column(columns, ["公司名称", "客户名称", "company"])
    manager_col = _find_column(columns, ["客户经理", "manager", "owner"])

    work = _with_period(df, time_col)
    work["_invoice_amount"] = _num(work[invoice_col])
    if mrr_col:
        work["_mrr_value"] = _num(work[mrr_col])
    issue = work[_payment_issue_mask(work[payment_col])].copy()
    scoped_issue, period_label = _scope_by_month_or_latest(issue, operation.filters)
    scoped_all, _ = _scope_by_month_or_latest(work, operation.filters)

    high_risk_issue = scoped_issue[_risk_mask(scoped_issue[risk_col], include_medium=False)] if risk_col else scoped_issue.iloc[0:0]
    medium_high_issue = scoped_issue[_risk_mask(scoped_issue[risk_col], include_medium=True)] if risk_col else scoped_issue.iloc[0:0]
    summary_rows = [
        {
            "范围": "全期间",
            "口径": "逾期/支付失败账款",
            "记录数": int(len(issue)),
            "客户数": _unique_count(issue, customer_col),
            "发票金额": _round_sum(issue["_invoice_amount"]),
            "说明": f"{payment_col} 包含逾期或失败。",
        },
        {
            "范围": period_label,
            "口径": "逾期/支付失败账款",
            "记录数": int(len(scoped_issue)),
            "客户数": _unique_count(scoped_issue, customer_col),
            "发票金额": _round_sum(scoped_issue["_invoice_amount"]),
            "说明": "按问题指定月份筛选；未指定时默认最新月份。",
        },
    ]
    if overdue_col:
        overdue_45 = issue[_num(issue[overdue_col]) >= 45]
        summary_rows.append(
            {
                "范围": "全期间",
                "口径": "逾期45天以上应收风险",
                "记录数": int(len(overdue_45)),
                "客户数": _unique_count(overdue_45, customer_col),
                "发票金额": _round_sum(overdue_45["_invoice_amount"]),
                "说明": f"{payment_col} 逾期或失败，且 {overdue_col} >= 45。",
            }
        )
    if risk_col:
        summary_rows.extend(
            [
                {
                    "范围": period_label,
                    "口径": "高风险且账款异常",
                    "记录数": int(len(high_risk_issue)),
                    "客户数": _unique_count(high_risk_issue, customer_col),
                    "发票金额": _round_sum(high_risk_issue["_invoice_amount"]),
                    "说明": f"{risk_col} 包含高，且 {payment_col} 逾期或失败。",
                },
                {
                    "范围": period_label,
                    "口径": "高+中风险且账款异常",
                    "记录数": int(len(medium_high_issue)),
                    "客户数": _unique_count(medium_high_issue, customer_col),
                    "发票金额": _round_sum(medium_high_issue["_invoice_amount"]),
                    "说明": f"{risk_col} 包含高或中，且 {payment_col} 逾期或失败。",
                },
            ]
        )
    if mrr_col and risk_col:
        high_risk_all = scoped_all[_risk_mask(scoped_all[risk_col], include_medium=False)]
        summary_rows.append(
            {
                "范围": period_label,
                "口径": "高风险客户 MRR",
                "记录数": int(len(high_risk_all)),
                "客户数": _unique_count(high_risk_all, customer_col),
                "发票金额": _round_sum(high_risk_all["_mrr_value"]),
                "说明": f"用于衡量 {risk_col}=高 对应的 MRR 暴露。",
            }
        )

    top = scoped_issue.copy()
    sort_columns = ["_invoice_amount"]
    if overdue_col:
        top["_overdue_days"] = _num(top[overdue_col])
        sort_columns.append("_overdue_days")
    top = top.sort_values(sort_columns, ascending=[False] * len(sort_columns)).head(20)
    top_columns = _existing_columns([customer_col, company_col, manager_col, payment_col, risk_col, invoice_col, overdue_col, mrr_col, time_col])
    top_table = top[top_columns].copy() if top_columns else top.head(20)
    if invoice_col in top_table.columns:
        top_table[invoice_col] = _num(top_table[invoice_col]).round(2)
    if mrr_col and mrr_col in top_table.columns:
        top_table[mrr_col] = _num(top_table[mrr_col]).round(2)

    return _template_result(
        template_id="payment_renewal_risk",
        tables=[
            _table("payment_renewal_summary", summary_rows),
            _frame_table("payment_collection_priority", top_table),
        ],
        metrics={
            "dimensions": [customer_col or "客户"],
            "metrics": [invoice_col],
            "period": period_label,
            "issue_invoice_total": summary_rows[1]["发票金额"],
        },
        method="使用 pandas 筛选逾期/支付失败账款，按月份、续约风险、发票金额和逾期天数生成催收与续约联动分析。",
        code="issue = df[df[payment_col].str.contains('逾期|失败|overdue|failed')]\npriority = issue.sort_values(['发票金额', '逾期天数'], ascending=False)",
    )


def _customer_success_priority(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    manager_col = _require_column(columns, ["客户经理", "manager", "owner", "cs"])
    mrr_col = _require_column(columns, ["月经常性收入MRR", "mrr", "月经常性收入"])
    risk_col = _find_column(columns, ["续约风险", "风险等级", "risk"])
    customer_col = _find_column(columns, ["客户ID", "customer_id", "customer id"])
    time_col = _find_column(columns, ["统计月份", "月份", "month", "date", "日期"])
    payment_col = _find_column(columns, ["付款状态", "支付状态", "payment"])
    invoice_col = _find_column(columns, ["发票金额", "应收金额", "逾期金额", "账单金额", "开票金额", "invoice_amount", "ar_amount", "invoice", "amount"])

    work, period_label = _scope_by_month_or_latest(_with_period(df, time_col), operation.filters)
    work["_mrr_value"] = _num(work[mrr_col])
    work["_high_risk"] = _risk_mask(work[risk_col], include_medium=False) if risk_col else False
    work["_medium_high_risk"] = _risk_mask(work[risk_col], include_medium=True) if risk_col else False
    if payment_col and invoice_col:
        work["_payment_issue_invoice"] = np.where(_payment_issue_mask(work[payment_col]), _num(work[invoice_col]), 0)
    else:
        work["_payment_issue_invoice"] = 0.0

    grouped = (
        work.groupby(manager_col, dropna=False)
        .apply(
            lambda group: pd.Series(
                {
                    "客户数": _unique_count(group, customer_col),
                    "总MRR": _round_sum(group["_mrr_value"]),
                    "高风险客户数": _unique_count(group[group["_high_risk"]], customer_col),
                    "高风险MRR": _round_sum(group.loc[group["_high_risk"], "_mrr_value"]),
                    "高+中风险MRR": _round_sum(group.loc[group["_medium_high_risk"], "_mrr_value"]),
                    "问题账款金额": _round_sum(group["_payment_issue_invoice"]),
                }
            ),
            include_groups=False,
        )
        .reset_index()
        .sort_values(["高风险MRR", "问题账款金额", "总MRR"], ascending=False)
    )
    grouped.insert(0, "优先级", range(1, len(grouped) + 1))
    return _template_result(
        template_id="customer_success_priority",
        tables=[_frame_table("customer_success_priority", grouped)],
        metrics={"dimensions": [manager_col], "metrics": ["高风险MRR"], "period": period_label},
        method="使用 pandas 按客户经理汇总客户数、MRR、高风险客户数、高风险 MRR 和问题账款金额，并按风险金额排序。",
        code="groupby(客户经理).agg(客户数, 总MRR, 高风险客户数, 高风险MRR, 问题账款金额)",
    )


def _channel_performance_risk(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    channel_col = _require_column(list(df.columns), ["获客渠道", "销售渠道", "channel"])
    table, metric_col, period_label = _dimension_risk_table(df, operation, channel_col)
    return _template_result(
        template_id="channel_performance_risk",
        tables=[_frame_table("channel_performance_risk", table)],
        metrics={"dimensions": [channel_col], "metrics": [metric_col], "period": period_label},
        method="使用 pandas 按渠道汇总规模、流失/风险、NPS 和样本量，用于投放或渠道复盘。",
        code="groupby(渠道).agg(total_metric, churn_rate, high_risk_count, avg_nps)",
    )


def _industry_market_selection(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    industry_col = _require_column(list(df.columns), ["行业", "industry"])
    table, metric_col, period_label = _dimension_risk_table(df, operation, industry_col)
    return _template_result(
        template_id="industry_market_selection",
        tables=[_frame_table("industry_market_selection", table)],
        metrics={"dimensions": [industry_col], "metrics": [metric_col], "period": period_label},
        method="使用 pandas 按行业汇总规模、平均收入、流失/风险和样本量，用于识别重点市场与谨慎市场。",
        code="groupby(行业).agg(total_mrr, avg_mrr, customer_count, churn_rate, high_risk_count)",
    )


def _segment_plan_strategy(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    dims = _existing_columns([
        _find_column(columns, ["客户分层", "segment"]),
        _find_column(columns, ["套餐类型", "plan", "package"]),
    ])
    if not dims:
        raise ValueError("分层/套餐策略分析需要客户分层或套餐类型字段。")
    frames = []
    for dimension in dims:
        table, metric_col, period_label = _dimension_risk_table(df, operation, dimension)
        table.insert(0, "维度类型", dimension)
        frames.append(table.rename(columns={dimension: "维度值"}))
    combined = pd.concat(frames, ignore_index=True)
    return _template_result(
        template_id="segment_plan_strategy",
        tables=[_frame_table("segment_plan_strategy", combined)],
        metrics={"dimensions": dims, "metrics": [metric_col], "period": period_label},
        method="使用 pandas 分别按客户分层和套餐类型汇总收入规模、客户数、流失/风险，用于客群与套餐策略判断。",
        code="for dim in [客户分层, 套餐类型]: groupby(dim).agg(total_mrr, churn_rate, high_risk_count)",
    )


def _expansion_contraction(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    customer_col = _require_column(columns, ["客户ID", "customer_id", "customer id"])
    mrr_col = _require_column(columns, ["月经常性收入MRR", "mrr", "月经常性收入"])
    time_col = _require_column(columns, ["统计月份", "月份", "month", "date", "日期"])
    company_col = _find_column(columns, ["公司名称", "客户名称", "company"])
    work = _with_period(df, time_col).dropna(subset=["_period"]).copy()
    work["_mrr_value"] = _num(work[mrr_col])
    explicit_start, explicit_end = start_end_period_filters(operation.filters)
    first_period = explicit_start or work["_period"].min()
    latest_period = explicit_end or latest_complete_period(work["_period"]) or work["_period"].max()
    first_key = str(first_period)
    latest_key = str(latest_period)
    first_columns = [customer_col, "_mrr_value", *([company_col] if company_col else [])]
    last_columns = [customer_col, "_mrr_value"]
    first = (
        work[work["_period"] == first_period][first_columns]
        .drop_duplicates(customer_col)
        .rename(columns={"_mrr_value": first_key})
        .set_index(customer_col)
    )
    last = (
        work[work["_period"] == latest_period][last_columns]
        .drop_duplicates(customer_col)
        .rename(columns={"_mrr_value": latest_key})
        .set_index(customer_col)
    )
    panel = first.join(last, how="inner").reset_index()
    panel["MRR变化"] = panel[latest_key] - panel[first_key]
    panel["变化类型"] = np.where(panel["MRR变化"] > 0, "扩张", np.where(panel["MRR变化"] < 0, "收缩", "持平"))
    top_expansion = panel[panel["MRR变化"] > 0].sort_values("MRR变化", ascending=False).head(20)
    top_contraction = panel[panel["MRR变化"] < 0].sort_values("MRR变化", ascending=True).head(20)
    ranking = pd.concat([top_expansion, top_contraction], ignore_index=True)
    summary_rows = [
        {"类型": "扩张客户", "客户数": int((panel["MRR变化"] > 0).sum()), "MRR变化": round(float(panel.loc[panel["MRR变化"] > 0, "MRR变化"].sum()), 2)},
        {"类型": "收缩客户", "客户数": int((panel["MRR变化"] < 0).sum()), "MRR变化": round(float(panel.loc[panel["MRR变化"] < 0, "MRR变化"].sum()), 2)},
        {"类型": "净变化", "客户数": int(len(panel)), "MRR变化": round(float(panel["MRR变化"].sum()), 2)},
    ]
    return _template_result(
        template_id="expansion_contraction",
        tables=[
            _table("expansion_contraction_summary", summary_rows),
            _frame_table("expansion_contraction_top_expansion", top_expansion),
            _frame_table("expansion_contraction_top_contraction", top_contraction),
            _frame_table("expansion_contraction_customers", ranking),
        ],
        metrics={"dimensions": [customer_col], "metrics": ["MRR变化"], "period": f"{first_period} 至 {latest_period}"},
        method="使用 pandas 将同一客户首期和最新期 MRR 对齐，计算扩张、收缩和净变化。",
        code="pivot = df.pivot_table(index=客户ID, columns=统计月份, values=MRR); delta = latest - first",
    )


def _health_signal_analysis(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    target_cols = _existing_columns([
        _find_column(columns, ["产品使用时长", "使用时长", "usage"]),
        _find_column(columns, ["活跃用户数", "活跃用户", "active users", "active"]),
        _find_column(columns, ["工单数量", "工单", "ticket"]),
        _find_column(columns, ["SLA超时数", "SLA超时", "sla"]),
        _find_column(columns, ["NPS评分", "nps"]),
        _find_column(columns, ["CSAT评分", "csat", "满意度"]),
        _find_column(columns, ["月经常性收入MRR", "mrr"]),
    ])
    risk_col = _find_column(columns, ["续约风险", "风险等级", "risk"])
    work = pd.DataFrame()
    for column in target_cols:
        work[column] = pd.to_numeric(df[column], errors="coerce")
    if risk_col:
        work["风险等级编码"] = df[risk_col].astype(str).map(lambda value: 3 if "高" in value else (2 if "中" in value else (1 if "低" in value else np.nan)))
    pairs = _health_signal_pairs(work, target_cols, risk_col is not None)
    pairs_frame = pd.DataFrame(pairs).sort_values("相关系数", key=lambda s: s.abs(), ascending=False)
    return _template_result(
        template_id="health_signal_analysis",
        tables=[_frame_table("health_signal_correlations", pairs_frame)],
        metrics={"metrics": target_cols, "dimensions": []},
        method="使用 pandas 对使用、工单、NPS、CSAT、MRR 和风险编码计算相关系数；仅说明相关，不推断因果。",
        code="corr = numeric_health_features.corr()",
    )


def _sales_overview_status(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    sales_col = _require_column(columns, ["销售额", "sales", "revenue"])
    profit_col = _require_column(columns, ["利润", "profit"])
    status_col = _find_column(columns, ["订单状态", "status"])
    rows = [_sales_scope_row(df, "全部订单", sales_col, profit_col)]
    if status_col:
        completed = df[df[status_col].astype(str).str.contains("已完成|完成|completed", case=False, regex=True, na=False)]
        rows.append(_sales_scope_row(completed, "已完成订单", sales_col, profit_col, denominator_sales=rows[0]["销售额"]))
    return _template_result(
        template_id="sales_overview_status",
        tables=[_table("sales_overview_status", rows)],
        metrics={"metrics": [sales_col, profit_col], "dimensions": [status_col] if status_col else []},
        method="使用 pandas 同时计算全部订单和已完成订单的销售额、利润、整体利润率和占比，避免订单状态口径不清。",
        code="all_orders = sum(sales/profit); completed = df[df[订单状态]=='已完成']",
    )


def _order_status_impact(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    status_col = _require_column(columns, ["订单状态", "status"])
    sales_col = _require_column(columns, ["销售额", "sales", "revenue"])
    profit_col = _find_column(columns, ["利润", "profit"])
    table = _sales_group_table(df, status_col, sales_col, profit_col)
    return _template_result(
        template_id="order_status_impact",
        tables=[_frame_table("order_status_impact", table)],
        metrics={"dimensions": [status_col], "metrics": [sales_col]},
        method="使用 pandas 按订单状态统计订单数、销售额、利润和利润率，并提示取消/退货是否纳入口径。",
        code="groupby(订单状态).agg(order_count, sales, profit, profit_rate)",
    )


def _product_pareto(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    product_col = _require_column(columns, ["商品名称", "产品名称", "product", "item"])
    sales_col = _require_column(columns, ["销售额", "sales", "revenue"])
    profit_col = _find_column(columns, ["利润", "profit"])
    table = _sales_group_table(df, product_col, sales_col, profit_col)
    total_sales = max(float(_num(df[sales_col]).sum()), 1.0)
    table["销售额占比"] = (table["销售额"] / total_sales).round(4)
    table["累计销售额占比"] = table["销售额占比"].cumsum().round(4)
    return _template_result(
        template_id="product_pareto",
        tables=[_frame_table("product_pareto", table.head(20))],
        metrics={"dimensions": [product_col], "metrics": [sales_col]},
        method="使用 pandas 按商品汇总销售额和利润，计算销售额占比与累计贡献率，用于集中度/Pareto 分析。",
        code="groupby(商品名称).sum(); share = sales / total_sales; cumulative_share = share.cumsum()",
    )


def _discount_profit_sensitivity(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    discount_col = _require_column(columns, ["折扣率", "discount"])
    profit_rate_col = _require_column(columns, ["利润率", "margin", "profit_rate"])
    profit_col = _find_column(columns, ["利润", "profit"])
    order_col = _find_column(columns, ["订单ID", "订单编号", "order_id"])
    sales_col = _find_column(columns, ["销售额", "sales"])
    work = df.copy()
    work["_discount"] = _num(work[discount_col])
    work["_profit_rate"] = _num(work[profit_rate_col])
    corr = float(work[["_discount", "_profit_rate"]].corr().iloc[0, 1])
    by_discount = (
        work.groupby(discount_col, dropna=False)
        .agg(订单数=(discount_col, "size"), 平均利润率=("_profit_rate", "mean"))
        .reset_index()
        .sort_values(discount_col)
    )
    by_discount["平均利润率"] = by_discount["平均利润率"].round(4)
    anomaly = work.copy()
    if profit_col:
        anomaly = anomaly[_num(anomaly[profit_col]) < 0]
    anomaly_columns = _existing_columns([order_col, discount_col, sales_col, profit_col, profit_rate_col])
    return _template_result(
        template_id="discount_profit_sensitivity",
        tables=[_frame_table("discount_profit_by_rate", by_discount), _frame_table("discount_profit_anomalies", anomaly[anomaly_columns].head(20) if anomaly_columns else anomaly.head(20))],
        metrics={"metrics": [discount_col, profit_rate_col], "dimensions": [], "correlation": round(corr, 4)},
        method="使用 pandas 计算折扣率与利润率相关系数，按折扣率汇总平均利润率，并列出负利润折扣订单。",
        code="corr = df[[折扣率, 利润率]].corr(); anomalies = df[df[利润] < 0]",
    )


def _payment_mix(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    payment_col = _require_column(columns, ["支付方式", "付款方式", "payment"])
    sales_col = _require_column(columns, ["销售额", "sales", "revenue"])
    table = _sales_group_table(df, payment_col, sales_col, _find_column(columns, ["利润", "profit"]))
    total_sales = max(float(_num(df[sales_col]).sum()), 1.0)
    table["销售额占比"] = (table["销售额"] / total_sales).round(4)
    return _template_result(
        template_id="payment_mix",
        tables=[_frame_table("payment_mix", table)],
        metrics={"dimensions": [payment_col], "metrics": [sales_col]},
        method="使用 pandas 按支付方式汇总销售额、利润和销售额占比。",
        code="groupby(支付方式).agg(sales, profit); share = sales / total_sales",
    )


def _sales_channel_strategy(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    channel_col = _require_column(columns, ["销售渠道", "渠道", "channel"])
    sales_col = _require_column(columns, ["销售额", "sales", "revenue"])
    profit_col = _find_column(columns, ["利润", "profit"])
    status_col = _find_column(columns, ["订单状态", "status"])
    table = _sales_group_table(df, channel_col, sales_col, profit_col)
    if status_col:
        status = df[status_col].astype(str)
        cancel = status.str.contains("取消|cancel", case=False, regex=True, na=False)
        returned = status.str.contains("退货|return", case=False, regex=True, na=False)
        risk = df.assign(_cancel=cancel, _return=returned).groupby(channel_col).agg(取消率=("_cancel", "mean"), 退货率=("_return", "mean")).reset_index()
        table = table.merge(risk, on=channel_col, how="left")
        table["取消率"] = table["取消率"].round(4)
        table["退货率"] = table["退货率"].round(4)
    return _template_result(
        template_id="sales_channel_strategy",
        tables=[_frame_table("sales_channel_strategy", table)],
        metrics={"dimensions": [channel_col], "metrics": [sales_col]},
        method="使用 pandas 按销售渠道汇总销售额、利润率、取消率和退货率，综合比较规模、质量和履约风险。",
        code="groupby(销售渠道).agg(sales, profit_rate, cancel_rate, return_rate)",
    )


def _pipeline_summary(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    amount_col = _require_column(columns, ["商机金额", "pipeline", "opportunity amount", "amount"])
    probability_col = _require_column(columns, ["赢率", "win_rate", "probability", "prob"])
    stage_col = _require_column(columns, ["销售阶段", "stage"])
    owner_col = _find_column(columns, ["销售负责人", "销售", "owner", "sales"])
    type_col = _find_column(columns, ["商机类型", "opportunity type", "type"])

    work = df.copy()
    work["_amount"] = _num(work[amount_col])
    work["_probability"] = _num(work[probability_col])
    work["_probability"] = work["_probability"].where(work["_probability"] <= 1, work["_probability"] / 100)
    work["_weighted_pipeline"] = work["_amount"] * work["_probability"]
    won_mask = work[stage_col].astype(str).str.contains("赢单|已赢|closed won|won", case=False, regex=True, na=False)
    summary_rows = [
        {
            "口径": "当前总 Pipeline",
            "Pipeline金额": round(float(work["_amount"].sum()), 2),
            "说明": f"对 {amount_col} 全量求和。",
        },
        {
            "口径": "加权 Pipeline",
            "Pipeline金额": round(float(work["_weighted_pipeline"].sum()), 2),
            "说明": f"{amount_col} x {probability_col} 后求和。",
        },
        {
            "口径": "赢单金额",
            "Pipeline金额": round(float(work.loc[won_mask, "_amount"].sum()), 2),
            "说明": f"{stage_col} 包含赢单/closed won 的商机金额。",
        },
    ]

    tables = [_table("pipeline_summary", summary_rows)]
    if owner_col:
        owner = (
            work.assign(_won_amount=np.where(won_mask, work["_amount"], 0.0))
            .groupby(owner_col, dropna=False)
            .agg(
                商机数=(amount_col, "size"),
                总Pipeline=("_amount", "sum"),
                加权Pipeline=("_weighted_pipeline", "sum"),
                赢单金额=("_won_amount", "sum"),
            )
            .reset_index()
            .sort_values("总Pipeline", ascending=False)
        )
        for column in ["总Pipeline", "加权Pipeline", "赢单金额"]:
            owner[column] = owner[column].round(2)
        tables.append(_frame_table("pipeline_by_owner", owner))

    stage = (
        work.groupby(stage_col, dropna=False)
        .agg(商机数=(amount_col, "size"), 总Pipeline=("_amount", "sum"), 加权Pipeline=("_weighted_pipeline", "sum"))
        .reset_index()
        .sort_values("总Pipeline", ascending=False)
    )
    stage["总Pipeline"] = stage["总Pipeline"].round(2)
    stage["加权Pipeline"] = stage["加权Pipeline"].round(2)
    tables.append(_frame_table("pipeline_by_stage", stage))

    if type_col:
        by_type = (
            work.groupby(type_col, dropna=False)
            .agg(商机数=(amount_col, "size"), 总Pipeline=("_amount", "sum"), 加权Pipeline=("_weighted_pipeline", "sum"))
            .reset_index()
            .sort_values("总Pipeline", ascending=False)
        )
        by_type["总Pipeline"] = by_type["总Pipeline"].round(2)
        by_type["加权Pipeline"] = by_type["加权Pipeline"].round(2)
        tables.append(_frame_table("pipeline_by_type", by_type))

    return _template_result(
        template_id="pipeline_summary",
        tables=tables,
        metrics={
            "metrics": [amount_col, probability_col],
            "dimensions": _existing_columns([owner_col, stage_col, type_col]),
            "total_pipeline_amount": summary_rows[0]["Pipeline金额"],
            "weighted_pipeline": summary_rows[1]["Pipeline金额"],
            "win_amount": summary_rows[2]["Pipeline金额"],
        },
        method="使用 pandas 计算总 Pipeline、赢率加权 Pipeline、赢单金额，并按销售负责人和销售阶段拆分。",
        code="total = 商机金额.sum(); weighted = (商机金额 * 赢率).sum(); win = 商机金额[销售阶段 == 赢单].sum()",
    )


def _dimension_risk_table(df: pd.DataFrame, operation: AnalysisOperation, dimension: str) -> tuple[pd.DataFrame, str, str]:
    columns = list(df.columns)
    metric_col = _find_column(columns, ["月经常性收入MRR", "mrr", "销售额", "sales", "revenue", "发票金额", "应收金额"]) or _first_numeric_column(df)
    customer_col = _find_column(columns, ["客户ID", "customer_id", "customer id"])
    time_col = _find_column(columns, ["统计月份", "月份", "month", "date", "日期"])
    risk_col = _find_column(columns, ["续约风险", "风险等级", "risk"])
    churn_col = _find_column(columns, ["当月流失", "流失", "churn"])
    nps_col = _find_column(columns, ["NPS评分", "nps"])
    work, period_label = _scope_by_month_or_all(_with_period(df, time_col), operation.filters)
    work["_metric_value"] = _num(work[metric_col])
    work["_high_risk"] = _risk_mask(work[risk_col], include_medium=False) if risk_col else False
    work["_churn"] = _yes_mask(work[churn_col]) if churn_col else False
    aggregations: dict[str, Any] = {
        "记录数": (dimension, "size"),
        "客户数": (customer_col, pd.Series.nunique) if customer_col else (dimension, "size"),
        "指标合计": ("_metric_value", "sum"),
        "指标均值": ("_metric_value", "mean"),
        "高风险记录数": ("_high_risk", "sum"),
        "流失记录数": ("_churn", "sum"),
    }
    if nps_col:
        work["_nps"] = _num(work[nps_col])
        aggregations["平均NPS"] = ("_nps", "mean")
    table = work.groupby(dimension, dropna=False).agg(**aggregations).reset_index()
    table["指标合计"] = table["指标合计"].round(2)
    table["指标均值"] = table["指标均值"].round(2)
    table["高风险率"] = (table["高风险记录数"] / table["记录数"].replace(0, np.nan)).fillna(0).round(4)
    table["流失率"] = (table["流失记录数"] / table["记录数"].replace(0, np.nan)).fillna(0).round(4)
    if "平均NPS" in table.columns:
        table["平均NPS"] = table["平均NPS"].round(2)
    return table.sort_values(["指标合计", "高风险率"], ascending=[False, False]), metric_col, period_label


def _sales_group_table(df: pd.DataFrame, dimension: str, sales_col: str, profit_col: str | None = None) -> pd.DataFrame:
    work = df.copy()
    work["_sales_value"] = _num(work[sales_col])
    if profit_col:
        work["_profit_value"] = _num(work[profit_col])
    aggregations: dict[str, Any] = {"订单数": (dimension, "size"), "销售额": ("_sales_value", "sum")}
    if profit_col:
        aggregations["利润"] = ("_profit_value", "sum")
    table = work.groupby(dimension, dropna=False).agg(**aggregations).reset_index()
    table["销售额"] = table["销售额"].round(2)
    if profit_col:
        table["利润"] = table["利润"].round(2)
        table["利润率"] = (table["利润"] / table["销售额"].replace(0, np.nan)).fillna(0).round(4)
    return table.sort_values("销售额", ascending=False)


def _sales_scope_row(df: pd.DataFrame, label: str, sales_col: str, profit_col: str, denominator_sales: float | None = None) -> dict[str, Any]:
    sales = float(_num(df[sales_col]).sum())
    profit = float(_num(df[profit_col]).sum())
    row = {
        "口径": label,
        "订单数": int(len(df)),
        "销售额": round(sales, 2),
        "利润": round(profit, 2),
        "整体利润率": round(profit / sales, 4) if sales else 0,
    }
    if denominator_sales:
        row["销售额占比"] = round(sales / denominator_sales, 4) if denominator_sales else 0
    return row


def _template_result(
    template_id: str,
    tables: list[ExecutionTable],
    metrics: dict[str, Any],
    method: str,
    code: str,
) -> tuple[ExecutionResult, str]:
    result = ExecutionResult(
        kind="business_template_analysis",
        source="pandas",
        tables=tables,
        metrics={**metrics, "template_id": template_id},
        method=method,
    )
    return result, code


def _table(name: str, rows: list[dict[str, Any]]) -> ExecutionTable:
    columns = list(rows[0].keys()) if rows else []
    return ExecutionTable(name=name, columns=columns, rows=rows)


def _frame_table(name: str, frame: pd.DataFrame) -> ExecutionTable:
    return ExecutionTable(name=name, columns=list(frame.columns), rows=dataframe_to_records(frame))


def _template_from_filters(filters: list[str]) -> str | None:
    for item in filters:
        if item.startswith("__template__="):
            return item.split("=", 1)[1]
    return None


def _scope_by_month_or_latest(df: pd.DataFrame, filters: list[str]) -> tuple[pd.DataFrame, str]:
    if "_period" not in df.columns or df["_period"].isna().all():
        return df, "全期间"
    explicit_periods = period_filters(filters)
    if explicit_periods:
        period = explicit_periods[-1]
        return df[df["_period"] == period], str(period)
    month = _month_filter(filters)
    if month:
        return df[df["_period"].dt.month == month], f"{month} 月"
    latest = latest_complete_period(df["_period"]) or df["_period"].max()
    return df[df["_period"] == latest], str(latest)


def _scope_by_month_or_all(df: pd.DataFrame, filters: list[str]) -> tuple[pd.DataFrame, str]:
    if "_period" not in df.columns or df["_period"].isna().all():
        return df, "全期间"
    explicit_periods = period_filters(filters)
    if explicit_periods:
        period = explicit_periods[-1]
        return df[df["_period"] == period], str(period)
    month = _month_filter(filters)
    if month:
        return df[df["_period"].dt.month == month], f"{month} 月"
    return df, "全期间"


def _health_signal_pairs(work: pd.DataFrame, target_cols: list[str], has_risk: bool) -> list[dict[str, Any]]:
    usage_col = _find_column(target_cols, ["产品使用时长", "使用时长", "usage"])
    active_col = _find_column(target_cols, ["活跃用户", "active"])
    ticket_col = _find_column(target_cols, ["工单数量", "工单", "ticket"])
    sla_col = _find_column(target_cols, ["SLA超时", "sla"])
    nps_col = _find_column(target_cols, ["NPS评分", "nps"])
    csat_col = _find_column(target_cols, ["CSAT评分", "csat", "满意度"])
    mrr_col = _find_column(target_cols, ["月经常性收入MRR", "mrr"])
    risk_col = "风险等级编码" if has_risk and "风险等级编码" in work.columns else None
    candidates = [
        ("使用时长 vs MRR", usage_col, mrr_col),
        ("活跃用户 vs MRR", active_col, mrr_col),
        ("工单数量 vs 续约风险", ticket_col, risk_col),
        ("SLA超时 vs 续约风险", sla_col, risk_col),
        ("NPS vs 续约风险", nps_col, risk_col),
        ("CSAT vs 续约风险", csat_col, risk_col),
        ("CSAT vs NPS", csat_col, nps_col),
    ]
    rows: list[dict[str, Any]] = []
    for label, left, right in candidates:
        if not left or not right or left not in work.columns or right not in work.columns:
            continue
        pair = work[[left, right]].dropna()
        if len(pair) < 3:
            continue
        corr = pair[left].corr(pair[right])
        if pd.isna(corr):
            continue
        rows.append(
            {
                "关系": label,
                "字段A": left,
                "字段B": "续约风险" if right == "风险等级编码" else right,
                "相关系数": round(float(corr), 4),
                "样本数": int(len(pair)),
                "说明": "正值表示同向变化，负值表示反向变化；相关不代表因果。",
            }
        )
    if rows:
        return rows

    corr = work.corr(numeric_only=True).reset_index().rename(columns={"index": "字段"})
    for left in corr["字段"]:
        for right in corr.columns[1:]:
            if left < right and pd.notna(corr.loc[corr["字段"] == left, right].iloc[0]):
                rows.append({"关系": f"{left} vs {right}", "字段A": left, "字段B": right, "相关系数": round(float(corr.loc[corr["字段"] == left, right].iloc[0]), 4), "样本数": int(len(work[[left, right]].dropna())), "说明": "相关不代表因果。"})
    return rows


def _with_period(df: pd.DataFrame, time_col: str | None) -> pd.DataFrame:
    work = df.copy()
    if time_col and time_col in work.columns:
        work["_period"] = pd.to_datetime(work[time_col], errors="coerce", format="mixed").dt.to_period("M")
    else:
        work["_period"] = pd.NaT
    return work


def _month_filter(filters: list[str]) -> int | None:
    for item in filters:
        if item.startswith("__month__="):
            try:
                month = int(item.split("=", 1)[1])
            except ValueError:
                return None
            if 1 <= month <= 12:
                return month
    return None


def _find_column(columns: list[str], keywords: list[str]) -> str | None:
    lower_map = {column.lower(): column for column in columns}
    for keyword in keywords:
        if keyword.lower() in lower_map:
            return lower_map[keyword.lower()]
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for column in columns:
            if keyword_lower in column.lower():
                return column
    return None


def _require_column(columns: list[str], keywords: list[str]) -> str:
    column = _find_column(columns, keywords)
    if not column:
        raise ValueError(f"业务模板缺少必要字段：{'/'.join(keywords)}")
    return column


def _existing_columns(columns: list[str | None]) -> list[str]:
    return [column for column in columns if column]


def _first_numeric_column(df: pd.DataFrame) -> str:
    numeric = df.select_dtypes(include=[np.number]).columns
    if len(numeric) == 0:
        raise ValueError("业务模板需要至少一个数值指标。")
    return str(numeric[0])


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _round_sum(series: pd.Series) -> float:
    return round(float(pd.to_numeric(series, errors="coerce").fillna(0).sum()), 2)


def _unique_count(df: pd.DataFrame, column: str | None) -> int:
    if column and column in df.columns:
        return int(df[column].nunique(dropna=True))
    return int(len(df))


def _payment_issue_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.contains("逾期|失败|overdue|failed|past due", case=False, regex=True, na=False)


def _risk_mask(series: pd.Series, include_medium: bool) -> pd.Series:
    pattern = "高|high"
    if include_medium:
        pattern = "高|中|high|medium"
    return series.astype(str).str.contains(pattern, case=False, regex=True, na=False)


def _yes_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.contains("是|yes|true|1|流失|churn", case=False, regex=True, na=False)
