from __future__ import annotations

import re


def goal_label(goal: str) -> str:
    labels = {
        "group_aggregate": "分组聚合", "count_by_dimension": "维度计数", "time_trend": "时间趋势",
        "correlation": "相关性分析", "distribution": "分布分析", "outlier": "异常值检测",
        "top_records": "Top 记录查询", "market_recommendation": "市场扩张建议", "dataset_overview": "数据集概览",
        "data_quality": "数据质量审计", "mrr_snapshot_vs_cumulative": "MRR 口径区分",
        "risk_customer_ranking": "高风险客户排名", "business_template_analysis": "业务模板分析",
        "multi_analysis": "多问题综合分析", "describe": "描述统计", "unanswerable": "当前数据不可回答",
        "unanswerable_with_current_schema": "当前数据不可回答", "clarification": "需要澄清",
    }
    return labels.get(goal, goal)


def path_label(path: str) -> str:
    return {"duckdb_sql": "DuckDB SQL", "pandas": "pandas/scipy", "clarification": "追问澄清"}.get(path, path)


def operation_label(operation: str) -> str:
    return goal_label(operation)


def table_label(table_name: str) -> str:
    prefixed = re.match(r"q(\d+)_(.+)", table_name)
    if prefixed:
        return f"问题 {prefixed.group(1)} - {table_label(prefixed.group(2))}"
    labels = {
        "group_aggregate": "分组聚合结果", "count_by_dimension": "维度计数结果", "time_trend": "时间趋势结果",
        "correlation_sample": "相关性样本", "histogram_bins": "分布区间", "outlier_rows": "异常值记录",
        "top_records": "Top 记录结果", "market_recommendation": "市场扩张建议结果", "dataset_overview": "数据集概览",
        "data_quality_issues": "数据质量问题", "data_quality_detail_rows": "质量问题明细行",
        "mrr_scope_comparison": "MRR 口径对比", "monthly_mrr": "月度 MRR",
        "risk_customer_ranking": "高风险客户 MRR 排名", "risk_customer_summary": "风险客户汇总",
        "payment_renewal_summary": "账款与续约风险汇总", "payment_collection_priority": "催收优先级明细",
        "customer_success_priority": "客户成功优先级", "channel_performance_risk": "渠道表现与风险",
        "industry_market_selection": "行业市场选择", "segment_plan_strategy": "分层与套餐策略",
        "expansion_contraction_summary": "扩张收缩汇总", "expansion_contraction_top_expansion": "Top 扩张客户",
        "expansion_contraction_top_contraction": "Top 收缩客户", "expansion_contraction_customers": "扩张收缩客户明细",
        "health_signal_correlations": "健康信号相关性", "pipeline_summary": "Pipeline 汇总",
        "pipeline_by_owner": "销售负责人 Pipeline", "pipeline_by_stage": "销售阶段 Pipeline",
        "pipeline_by_type": "商机类型 Pipeline", "sales_overview_status": "经营总览口径对比",
        "order_status_impact": "订单状态影响", "product_pareto": "商品 Pareto 贡献",
        "discount_profit_by_rate": "折扣率与利润率", "discount_profit_anomalies": "异常折扣订单",
        "payment_mix": "支付方式结构", "sales_channel_strategy": "销售渠道策略",
        "numeric_describe": "数值描述统计", "unanswerable_questions": "不可回答问题说明",
    }
    return labels.get(table_name, table_name)


def business_template_label(template_id: str | None) -> str:
    labels = {
        "payment_renewal_risk": "账款与续约风险联动", "customer_success_priority": "客户成功优先级",
        "channel_performance_risk": "渠道表现与风险", "industry_market_selection": "行业市场选择",
        "segment_plan_strategy": "分层与套餐策略", "expansion_contraction": "MRR 扩张收缩",
        "health_signal_analysis": "客户健康信号", "pipeline_summary": "Pipeline 汇总",
        "sales_overview_status": "经营总览口径", "order_status_impact": "订单状态影响",
        "product_pareto": "商品 Pareto 贡献", "discount_profit_sensitivity": "折扣与利润敏感性",
        "payment_mix": "支付方式结构", "sales_channel_strategy": "销售渠道策略",
    }
    return labels.get(template_id or "", template_id or "业务模板")
