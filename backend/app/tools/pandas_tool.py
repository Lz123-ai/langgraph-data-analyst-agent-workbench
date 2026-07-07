from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from app.domain import AnalysisOperation, ExecutionResult, ExecutionTable
from app.tools.business_template_tool import run_business_template
from app.tools.serialization import dataframe_to_records, to_jsonable
from app.tools.time_scope import late_outlier_periods, latest_complete_period, period_filters


def _clean_numeric_pair(df: pd.DataFrame, left: str, right: str) -> pd.DataFrame:
    pair = df[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
    return pair


def run_pandas_operation(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    if operation.operation_type == "data_quality":
        return _run_data_quality(df, operation)
    if operation.operation_type == "mrr_snapshot_vs_cumulative":
        return _run_mrr_snapshot_vs_cumulative(df, operation)
    if operation.operation_type == "risk_customer_ranking":
        return _run_risk_customer_ranking(df, operation)
    if operation.operation_type == "business_template_analysis":
        return run_business_template(df, operation)
    if operation.operation_type == "correlation":
        return _run_correlation(df, operation)
    if operation.operation_type == "distribution":
        return _run_distribution(df, operation)
    if operation.operation_type == "outlier":
        return _run_outlier(df, operation)
    return _run_describe(df, operation)


def _run_data_quality(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    row_count = int(len(df))
    issues: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    duplicate_count = int(df.duplicated().sum())
    if duplicate_count:
        issues.append(
            {
                "issue_type": "重复行",
                "column": "__row__",
                "severity": "warning" if duplicate_count / max(row_count, 1) < 0.05 else "high",
                "metric": "duplicate_rows",
                "value": duplicate_count,
                "detail": f"检测到 {duplicate_count} 行完全重复记录。",
                "suggestion": "确认是否为重复订单或重复采集，必要时按业务主键去重。",
            }
        )
        detail_rows.extend(_detail_rows(df[df.duplicated(keep=False)], "重复行", limit=20))

    for key_columns in _business_key_candidates(df):
        key_duplicate_count = int(df.duplicated(subset=key_columns, keep="first").sum())
        if key_duplicate_count:
            key_name = "+".join(key_columns)
            issues.append(
                {
                    "issue_type": "重复业务键",
                    "column": key_name,
                    "severity": "high",
                    "metric": "duplicate_key_rows",
                    "value": key_duplicate_count,
                    "detail": f"{key_name} 存在 {key_duplicate_count} 行重复记录（按首次出现后的重复行计）。",
                    "suggestion": "按业务主键核对是否为重复订单、重复客户快照或需要保留的多版本记录。",
                }
            )
            detail_rows.extend(_detail_rows(df[df.duplicated(subset=key_columns, keep=False)], "重复业务键", limit=20))

    for column in df.columns:
        series = df[column]
        missing_count = int(series.isna().sum())
        missing_rate = float(missing_count / row_count) if row_count else 0.0
        unique_count = int(series.nunique(dropna=True))
        unique_rate = float(unique_count / max(row_count - missing_count, 1)) if row_count else 0.0

        if missing_count:
            severity = "high" if missing_rate >= 0.2 else "warning"
            issues.append(
                {
                    "issue_type": "缺失值",
                    "column": column,
                    "severity": severity,
                    "metric": "missing_rate",
                    "value": round(missing_rate, 4),
                    "detail": f"{column} 缺失 {missing_count} 行，占比 {missing_rate:.1%}。",
                    "suggestion": "分析前确认缺失含义；可按字段语义补全、删除或单独标记。",
                }
            )

        if row_count > 1 and unique_count <= 1:
            issues.append(
                {
                    "issue_type": "常量字段",
                    "column": column,
                    "severity": "info",
                    "metric": "unique_count",
                    "value": unique_count,
                    "detail": f"{column} 只有 {unique_count} 个非空唯一值。",
                    "suggestion": "如果该字段不参与筛选或分组，可从建模特征中剔除。",
                }
            )

        if series.dtype == "object" and unique_rate >= 0.9 and row_count >= 20:
            issues.append(
                {
                    "issue_type": "高基数字段",
                    "column": column,
                    "severity": "info",
                    "metric": "unique_rate",
                    "value": round(unique_rate, 4),
                    "detail": f"{column} 唯一值占比 {unique_rate:.1%}，可能是 ID 或自由文本。",
                    "suggestion": "避免直接作为普通类别维度聚合；可作为明细标识或先做分桶。",
                }
            )

        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if len(numeric) >= 8:
            q1 = numeric.quantile(0.25)
            q3 = numeric.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outlier_count = int(((numeric < lower) | (numeric > upper)).sum())
                if outlier_count:
                    severity = "warning" if outlier_count / len(numeric) < 0.1 else "high"
                    issues.append(
                        {
                            "issue_type": "数值异常值",
                            "column": column,
                            "severity": severity,
                            "metric": "outlier_count",
                            "value": outlier_count,
                            "detail": f"{column} 基于 IQR 规则检测到 {outlier_count} 个异常值。",
                            "suggestion": "核对是否为录入错误、极端业务场景或需要截尾处理。",
                        }
                    )

    issues.extend(_business_quality_issues(df, detail_rows))

    if not issues:
        issues.append(
            {
                "issue_type": "未发现明显问题",
                "column": "__dataset__",
                "severity": "info",
                "metric": "quality_scan",
                "value": 0,
                "detail": "未检测到重复行、缺失值、常量字段或明显数值异常值。",
                "suggestion": "仍建议结合业务规则检查取值范围、枚举合法性和主键唯一性。",
            }
        )

    issue_frame = pd.DataFrame(issues)
    tables = [
        ExecutionTable(
            name="data_quality_issues",
            columns=list(issue_frame.columns),
            rows=dataframe_to_records(issue_frame),
        )
    ]
    if detail_rows:
        detail_frame = pd.DataFrame(detail_rows)
        tables.append(
            ExecutionTable(
                name="data_quality_detail_rows",
                columns=list(detail_frame.columns),
                rows=dataframe_to_records(detail_frame, limit=50),
            )
        )
    result = ExecutionResult(
        kind="data_quality",
        source="pandas",
        tables=tables,
        metrics={
            "row_count": row_count,
            "column_count": int(len(df.columns)),
            "issue_count": len(issues),
            "duplicate_count": duplicate_count,
            "detail_row_count": len(detail_rows),
        },
        method="使用 pandas 计算重复行、业务键重复、字段缺失率、唯一值数量、高基数风险、IQR 数值异常值、未来/离群月份、负 MRR、异常折扣、0 金额、负利润和常见财务公式一致性。",
    )
    code = (
        "duplicate_count = df.duplicated().sum()\n"
        "business_key_duplicates = df.duplicated(subset=key_columns, keep=False)\n"
        "missing = df.isna().sum()\n"
        "unique_count = df.nunique(dropna=True)\n"
        "numeric_outliers = IQR rule per numeric column\n"
        "future_periods = period > latest_complete_period(period)\n"
        "negative_mrr = mrr < 0\n"
        "extreme_discount = discount_rate > 0.5\n"
        "formula_checks = sales/profit/profit_rate consistency when required columns exist"
    )
    return result, code


def _run_correlation(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = operation.metrics[:2]
    if len(columns) < 2:
        raise ValueError("相关性分析需要两个数值字段。")
    pair = _clean_numeric_pair(df, columns[0], columns[1])
    if len(pair) < 3:
        raise ValueError("相关性分析至少需要 3 行完整数据。")
    corr, p_value = stats.pearsonr(pair[columns[0]], pair[columns[1]])
    sample = pair.head(200).copy()
    table = ExecutionTable(
        name="correlation_sample",
        columns=list(sample.columns),
        rows=dataframe_to_records(sample),
    )
    result = ExecutionResult(
        kind="correlation",
        source="pandas",
        tables=[table],
        metrics={
            "x": columns[0],
            "y": columns[1],
            "method": "pearson",
            "correlation": to_jsonable(corr),
            "p_value": to_jsonable(p_value),
            "rows_used": int(len(pair)),
        },
        method=f"对非空数值配对字段 {columns[0]} 和 {columns[1]} 执行 scipy.stats.pearsonr。",
    )
    code = (
        f"pair = df[[{columns[0]!r}, {columns[1]!r}]].apply(pd.to_numeric, errors='coerce').dropna()\n"
        f"corr, p_value = scipy.stats.pearsonr(pair[{columns[0]!r}], pair[{columns[1]!r}])"
    )
    return result, code


def _run_mrr_snapshot_vs_cumulative(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    mrr_col = _find_column(columns, ["月经常性收入MRR", "mrr", "月经常性收入"])
    time_col = _find_column(columns, ["统计月份", "月份", "month", "date", "日期"])
    customer_col = _find_column(columns, ["客户ID", "customer_id", "customer id", "用户ID"])
    if not mrr_col or not time_col:
        raise ValueError("MRR 口径分析需要 MRR 指标字段和月份/日期字段。")

    work = df.copy()
    work["_mrr_value"] = pd.to_numeric(work[mrr_col], errors="coerce")
    work["_period"] = pd.to_datetime(work[time_col], errors="coerce", format="mixed").dt.to_period("M")
    valid = work.dropna(subset=["_mrr_value", "_period"])
    if valid.empty:
        raise ValueError("MRR 口径分析没有可用的 MRR 或月份数据。")

    latest_period = latest_complete_period(valid["_period"]) or valid["_period"].max()
    analysis_valid = valid[valid["_period"] <= latest_period]
    current = analysis_valid[analysis_valid["_period"] == latest_period]
    cumulative_mrr = float(analysis_valid["_mrr_value"].sum())
    current_mrr = float(current["_mrr_value"].sum())
    customer_count_all = _unique_count(analysis_valid, customer_col)
    customer_count_current = _unique_count(current, customer_col)

    comparison_rows = [
        {
            "口径": "当前 MRR",
            "计算方式": f"取最新月份 {latest_period} 的 {mrr_col} 求和",
            "月份范围": str(latest_period),
            "记录数": int(len(current)),
            "客户数": customer_count_current,
            "MRR": round(current_mrr, 2),
            "业务解释": "月度快照口径，用于回答当前规模。",
        },
        {
            "口径": "累计 MRR",
            "计算方式": f"对 {analysis_valid['_period'].nunique()} 个完整业务月份客户-月份记录的 {mrr_col} 求和",
            "月份范围": f"{analysis_valid['_period'].min()} 至 {latest_period}",
            "记录数": int(len(analysis_valid)),
            "客户数": customer_count_all,
            "MRR": round(cumulative_mrr, 2),
            "业务解释": "客户-月份记录累计求和，只能解释为历史记录累计，不等同于当前 MRR。",
        },
    ]
    monthly = (
        analysis_valid.groupby("_period")
        .agg(MRR=("_mrr_value", "sum"), record_count=("_mrr_value", "size"))
        .reset_index()
        .rename(columns={"_period": "月份", "record_count": "记录数"})
    )
    monthly["月份"] = monthly["月份"].astype(str)
    monthly["MRR"] = monthly["MRR"].round(2)
    if customer_col:
        customers_by_month = analysis_valid.groupby("_period")[customer_col].nunique().reset_index(name="客户数")
        customers_by_month["_period"] = customers_by_month["_period"].astype(str)
        monthly = monthly.merge(customers_by_month.rename(columns={"_period": "月份"}), on="月份", how="left")

    result = ExecutionResult(
        kind="mrr_snapshot_vs_cumulative",
        source="pandas",
        tables=[
            ExecutionTable(
                name="mrr_scope_comparison",
                columns=list(comparison_rows[0].keys()),
                rows=comparison_rows,
            ),
            ExecutionTable(
                name="monthly_mrr",
                columns=list(monthly.columns),
                rows=dataframe_to_records(monthly),
            ),
        ],
        metrics={
            "mrr_column": mrr_col,
            "time_column": time_col,
            "latest_period": str(latest_period),
            "excluded_late_periods": late_outlier_periods(valid["_period"]),
            "current_mrr": round(current_mrr, 2),
            "cumulative_mrr": round(cumulative_mrr, 2),
            "period_count": int(analysis_valid["_period"].nunique()),
            "customer_count": customer_count_all,
        },
        method="使用 pandas 按月份识别最新快照，并分别计算最新月份 MRR 与全期间客户-月份记录 MRR 累计值。",
    )
    code = (
        f"df['_period'] = pandas.to_datetime(df[{time_col!r}], errors='coerce').dt.to_period('M')\n"
        f"current_period = latest_complete_period(df['_period'])\n"
        f"current_mrr = df[df['_period'] == current_period][{mrr_col!r}].sum()\n"
        f"cumulative_mrr = df[{mrr_col!r}].sum()"
    )
    return result, code


def _run_risk_customer_ranking(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    columns = list(df.columns)
    mrr_col = _find_column(columns, ["月经常性收入MRR", "mrr", "月经常性收入"])
    risk_col = _find_column(columns, ["续约风险", "风险等级", "risk"])
    time_col = _find_column(columns, ["统计月份", "月份", "month", "date", "日期"])
    customer_col = _find_column(columns, ["客户ID", "customer_id", "customer id", "用户ID"])
    company_col = _find_column(columns, ["公司名称", "客户名称", "客户", "company", "customer_name"])
    manager_col = _find_column(columns, ["客户经理", "owner", "manager", "cs"])
    if not mrr_col or not risk_col or not time_col:
        raise ValueError("高风险客户排名需要 MRR、风险等级和月份字段。")

    work = df.copy()
    work["_mrr_value"] = pd.to_numeric(work[mrr_col], errors="coerce")
    work["_period"] = pd.to_datetime(work[time_col], errors="coerce", format="mixed").dt.to_period("M")
    valid = work.dropna(subset=["_mrr_value", "_period"])
    if valid.empty:
        raise ValueError("高风险客户排名没有可用的 MRR 或月份数据。")

    month_filter = _month_filter(operation.filters)
    explicit_periods = period_filters(operation.filters)
    if explicit_periods:
        period = explicit_periods[-1]
        scoped = valid[valid["_period"] == period]
        period_label = str(period)
    elif month_filter:
        scoped = valid[valid["_period"].dt.month == month_filter]
        period_label = f"{month_filter} 月"
    else:
        latest_period = latest_complete_period(valid["_period"]) or valid["_period"].max()
        scoped = valid[valid["_period"] == latest_period]
        period_label = str(latest_period)
    if scoped.empty:
        raise ValueError(f"{period_label} 没有可用记录。")

    risk_text = scoped[risk_col].astype(str)
    high = scoped[risk_text.str.contains("高|high", case=False, regex=True, na=False)].copy()
    medium_high = scoped[risk_text.str.contains("高|中|high|medium", case=False, regex=True, na=False)].copy()
    if high.empty:
        raise ValueError(f"{period_label} 未找到高风险客户记录。")

    group_columns = [column for column in [customer_col, company_col, manager_col] if column]
    if group_columns:
        ranking = (
            high.groupby(group_columns, dropna=False)
            .agg(
                续约风险=(risk_col, "first"),
                MRR=("_mrr_value", "sum"),
                记录数=("_mrr_value", "size"),
            )
            .reset_index()
            .sort_values("MRR", ascending=False)
            .head(20)
        )
    else:
        ranking = high.assign(MRR=high["_mrr_value"]).sort_values("MRR", ascending=False).head(20)
        ranking = ranking[[risk_col, "MRR"]].rename(columns={risk_col: "续约风险"})
    ranking["MRR"] = ranking["MRR"].round(2)
    ranking.insert(0, "排名", range(1, len(ranking) + 1))

    summary_rows = [
        {
            "范围": period_label,
            "口径": "高风险客户",
            "客户数": _unique_count(high, customer_col),
            "MRR": round(float(high["_mrr_value"].sum()), 2),
            "说明": f"{risk_col} 包含“高”的客户记录。",
        },
        {
            "范围": period_label,
            "口径": "高+中风险客户",
            "客户数": _unique_count(medium_high, customer_col),
            "MRR": round(float(medium_high["_mrr_value"].sum()), 2),
            "说明": f"{risk_col} 包含“高”或“中”的客户记录。",
        },
    ]

    result = ExecutionResult(
        kind="risk_customer_ranking",
        source="pandas",
        tables=[
            ExecutionTable(
                name="risk_customer_ranking",
                columns=list(ranking.columns),
                rows=dataframe_to_records(ranking),
            ),
            ExecutionTable(
                name="risk_customer_summary",
                columns=list(summary_rows[0].keys()),
                rows=summary_rows,
            ),
        ],
        metrics={
            "mrr_column": mrr_col,
            "risk_column": risk_col,
            "time_column": time_col,
            "period": period_label,
            "high_risk_customer_count": summary_rows[0]["客户数"],
            "high_risk_mrr": summary_rows[0]["MRR"],
        },
        method="使用 pandas 按月份筛选客户快照，筛选续约风险为高的客户，并按 MRR 降序排名。",
    )
    code = (
        f"scoped = df[df[{time_col!r}].month == {month_filter or 'latest_month'}]\n"
        f"high = scoped[scoped[{risk_col!r}].str.contains('高|high')]\n"
        f"ranking = high.groupby(customer_columns)[{mrr_col!r}].sum().sort_values(ascending=False)"
    )
    return result, code


def _unique_count(df: pd.DataFrame, column: str | None) -> int:
    if column and column in df.columns:
        return int(df[column].nunique(dropna=True))
    return int(len(df))


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


def _business_key_candidates(df: pd.DataFrame) -> list[list[str]]:
    columns = list(df.columns)
    candidates: list[list[str]] = []
    order_id = _find_column(columns, ["订单ID", "订单编号", "order_id", "order id"])
    if order_id:
        candidates.append([order_id])
    customer_id = _find_column(columns, ["客户ID", "客户编号", "customer_id", "customer id"])
    month = _find_column(columns, ["统计月份", "月份", "month", "billing_month"])
    if customer_id and month:
        candidates.append([customer_id, month])
    return candidates


def _business_quality_issues(df: pd.DataFrame, detail_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    columns = list(df.columns)

    time_col = _find_column(columns, ["统计月份", "月份", "month", "date", "日期"])
    sales_col = _find_column(columns, ["销售额", "订单金额", "发票金额", "sales", "revenue", "amount", "mrr"])
    mrr_col = _find_column(columns, ["月经常性收入MRR", "mrr", "月经常性收入"])
    profit_col = _find_column(columns, ["利润", "profit"])
    cost_col = _find_column(columns, ["成本", "cost"])
    quantity_col = _find_column(columns, ["数量", "件数", "units", "quantity", "qty"])
    unit_price_col = _find_column(columns, ["单价", "unit_price", "price"])
    discount_col = _find_column(columns, ["折扣率", "discount_rate", "discount"])
    profit_rate_col = _find_column(columns, ["利润率", "profit_rate", "margin_rate"])

    if time_col:
        periods = pd.to_datetime(df[time_col], errors="coerce", format="mixed").dt.to_period("M")
        latest_period = latest_complete_period(periods)
        if latest_period is not None:
            future_rows = df[periods > latest_period]
            if len(future_rows):
                issues.append(
                    {
                        "issue_type": "未来/离群月份",
                        "column": time_col,
                        "severity": "high",
                        "metric": "future_period_rows",
                        "value": int(len(future_rows)),
                        "detail": f"{time_col} 中有 {len(future_rows)} 行晚于最新完整业务月份 {latest_period}，疑似未来或离群月份。",
                        "suggestion": "当前快照类指标应默认排除这些月份，或由用户确认是否纳入分析。",
                    }
                )
                detail_rows.extend(_detail_rows(future_rows, "未来/离群月份", limit=20))

    if mrr_col:
        mrr = pd.to_numeric(df[mrr_col], errors="coerce")
        negative_mrr = df[mrr < 0]
        if len(negative_mrr):
            issues.append(
                {
                    "issue_type": "负 MRR",
                    "column": mrr_col,
                    "severity": "high",
                    "metric": "negative_mrr_rows",
                    "value": int(len(negative_mrr)),
                    "detail": f"{mrr_col} 存在 {len(negative_mrr)} 行负值记录。",
                    "suggestion": "确认是否为退款、冲销或数据错误；MRR 当前快照通常不应直接为负。",
                }
            )
            detail_rows.extend(_detail_rows(negative_mrr, "负 MRR", limit=20))

    if discount_col:
        discount = pd.to_numeric(df[discount_col], errors="coerce")
        normalized_discount = discount.where(discount <= 1, discount / 100)
        extreme_discount = df[normalized_discount > 0.5]
        if len(extreme_discount):
            issues.append(
                {
                    "issue_type": "异常折扣",
                    "column": discount_col,
                    "severity": "warning",
                    "metric": "extreme_discount_rows",
                    "value": int(len(extreme_discount)),
                    "detail": f"{discount_col} 存在 {len(extreme_discount)} 行超过 50% 的高折扣记录。",
                    "suggestion": "核对是否为特殊商务审批、促销政策或录入错误；利润和续约分析中应单独披露。",
                }
            )
            detail_rows.extend(_detail_rows(extreme_discount, "异常折扣", limit=20))

    if sales_col:
        sales = pd.to_numeric(df[sales_col], errors="coerce")
        zero_sales = df[sales.fillna(1) == 0]
        if len(zero_sales):
            issues.append(
                {
                    "issue_type": "零值金额",
                    "column": sales_col,
                    "severity": "warning",
                    "metric": "zero_value_rows",
                    "value": int(len(zero_sales)),
                    "detail": f"{sales_col} 存在 {len(zero_sales)} 行为 0 的记录。",
                    "suggestion": "核对是否为赠品、退款、录入错误或尚未结算记录；经营分析时应单独说明口径。",
                }
            )
            detail_rows.extend(_detail_rows(zero_sales, "零值金额", limit=20))

    if profit_col:
        profit = pd.to_numeric(df[profit_col], errors="coerce")
        negative_profit = df[profit < 0]
        if len(negative_profit):
            issues.append(
                {
                    "issue_type": "负利润",
                    "column": profit_col,
                    "severity": "high",
                    "metric": "negative_profit_rows",
                    "value": int(len(negative_profit)),
                    "detail": f"{profit_col} 存在 {len(negative_profit)} 行负值记录。",
                    "suggestion": "优先检查高折扣、成本异常或退货口径；利润分析应单独披露负利润订单。",
                }
            )
            detail_rows.extend(_detail_rows(negative_profit, "负利润", limit=20))

    if sales_col and quantity_col and unit_price_col and discount_col:
        quantity = pd.to_numeric(df[quantity_col], errors="coerce")
        unit_price = pd.to_numeric(df[unit_price_col], errors="coerce")
        discount = pd.to_numeric(df[discount_col], errors="coerce").fillna(0)
        discount = discount.where(discount <= 1, discount / 100)
        actual_sales = pd.to_numeric(df[sales_col], errors="coerce")
        expected_sales = quantity * unit_price * (1 - discount)
        bad_sales = df[(actual_sales - expected_sales).abs() > 0.01]
        if len(bad_sales):
            issues.append(
                {
                    "issue_type": "销售额公式不一致",
                    "column": sales_col,
                    "severity": "high",
                    "metric": "formula_error_rows",
                    "value": int(len(bad_sales)),
                    "detail": f"发现 {len(bad_sales)} 行不满足 {sales_col} = {quantity_col} x {unit_price_col} x (1 - {discount_col})。",
                    "suggestion": "复核数量、单价、折扣率和销售额字段来源；修正后再做利润和折扣分析。",
                }
            )
            detail_rows.extend(_detail_rows(bad_sales, "销售额公式不一致", limit=20))

    if profit_col and sales_col and cost_col:
        actual_profit = pd.to_numeric(df[profit_col], errors="coerce")
        sales = pd.to_numeric(df[sales_col], errors="coerce")
        cost = pd.to_numeric(df[cost_col], errors="coerce")
        bad_profit = df[(actual_profit - (sales - cost)).abs() > 0.01]
        if len(bad_profit):
            issues.append(
                {
                    "issue_type": "利润公式不一致",
                    "column": profit_col,
                    "severity": "high",
                    "metric": "formula_error_rows",
                    "value": int(len(bad_profit)),
                    "detail": f"发现 {len(bad_profit)} 行不满足 {profit_col} = {sales_col} - {cost_col}。",
                    "suggestion": "复核成本或利润计算逻辑，避免用错误利润字段生成结论。",
                }
            )
            detail_rows.extend(_detail_rows(bad_profit, "利润公式不一致", limit=20))

    if profit_rate_col and profit_col and sales_col:
        profit = pd.to_numeric(df[profit_col], errors="coerce")
        sales = pd.to_numeric(df[sales_col], errors="coerce")
        actual_rate = pd.to_numeric(df[profit_rate_col], errors="coerce")
        expected_rate = profit / sales.replace(0, np.nan)
        bad_rate = df[(actual_rate - expected_rate).abs() > 0.0001]
        if len(bad_rate):
            issues.append(
                {
                    "issue_type": "利润率公式不一致",
                    "column": profit_rate_col,
                    "severity": "high",
                    "metric": "formula_error_rows",
                    "value": int(len(bad_rate)),
                    "detail": f"发现 {len(bad_rate)} 行不满足 {profit_rate_col} = {profit_col} / {sales_col}。",
                    "suggestion": "复核利润率字段是否为百分比、比例值或使用不同分母。",
                }
            )
            detail_rows.extend(_detail_rows(bad_rate, "利润率公式不一致", limit=20))

    return issues


def _find_column(columns: list[str], keywords: list[str]) -> str | None:
    lower_map = {column.lower(): column for column in columns}
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in lower_map:
            return lower_map[keyword_lower]
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for column in columns:
            if keyword_lower in column.lower():
                return column
    return None


def _detail_rows(frame: pd.DataFrame, issue_type: str, limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index, row in frame.head(limit).iterrows():
        item = {"issue_type": issue_type, "row_index": int(row_index)}
        item.update(row.to_dict())
        rows.append(item)
    return rows


def _run_distribution(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    metric = operation.metrics[0]
    series = pd.to_numeric(df[metric], errors="coerce").dropna()
    if series.empty:
        raise ValueError(f"字段 {metric} 没有可用数值。")
    counts, edges = np.histogram(series, bins=min(12, max(4, int(np.sqrt(len(series))))))
    histogram = pd.DataFrame(
        {
            "bin_start": edges[:-1],
            "bin_end": edges[1:],
            "count": counts,
        }
    )
    describe = series.describe(percentiles=[0.25, 0.5, 0.75]).to_dict()
    result = ExecutionResult(
        kind="distribution",
        source="pandas",
        tables=[
            ExecutionTable(
                name="histogram_bins",
                columns=list(histogram.columns),
                rows=dataframe_to_records(histogram),
            )
        ],
        metrics={key: to_jsonable(value) for key, value in describe.items()},
        method=f"对字段 {metric} 执行 pandas 描述统计和 numpy 直方图分箱。",
    )
    code = f"series = pd.to_numeric(df[{metric!r}], errors='coerce').dropna()\ncounts, edges = np.histogram(series)"
    return result, code


def _run_outlier(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    metric = operation.metrics[0]
    series = pd.to_numeric(df[metric], errors="coerce")
    clean = series.dropna()
    if clean.empty:
        raise ValueError(f"字段 {metric} 没有可用数值。")
    q1 = clean.quantile(0.25)
    q3 = clean.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    mask = (series < lower) | (series > upper)
    outliers = df.loc[mask].copy().head(100)
    result = ExecutionResult(
        kind="outlier",
        source="pandas",
        tables=[
            ExecutionTable(
                name="outlier_rows",
                columns=list(outliers.columns),
                rows=dataframe_to_records(outliers),
            )
        ],
        metrics={
            "metric": metric,
            "q1": to_jsonable(q1),
            "q3": to_jsonable(q3),
            "iqr": to_jsonable(iqr),
            "lower_bound": to_jsonable(lower),
            "upper_bound": to_jsonable(upper),
            "outlier_count": int(mask.sum()),
        },
        method=f"对数值字段 {metric} 执行 IQR 异常值规则。",
    )
    code = f"q1, q3 = df[{metric!r}].quantile([0.25, 0.75]); mask = (series < lower) | (series > upper)"
    return result, code


def _run_describe(df: pd.DataFrame, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    numeric_columns = operation.metrics or list(df.select_dtypes(include=["number"]).columns)
    if not numeric_columns:
        raise ValueError("没有可用于描述统计的数值字段。")
    describe = df[numeric_columns].describe().transpose().reset_index().rename(columns={"index": "column"})
    result = ExecutionResult(
        kind="describe",
        source="pandas",
        tables=[
            ExecutionTable(
                name="numeric_describe",
                columns=list(describe.columns),
                rows=dataframe_to_records(describe),
            )
        ],
        metrics={"columns": numeric_columns},
        method="对数值字段执行 pandas.DataFrame.describe。",
    )
    code = f"df[{numeric_columns!r}].describe().transpose()"
    return result, code
