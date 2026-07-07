from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    aliases: tuple[str, ...]
    metric_type: str
    default_aggregation: str
    note: str


METRIC_REGISTRY: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        name="MRR",
        aliases=("mrr", "月经常性收入", "月 recurring revenue"),
        metric_type="snapshot",
        default_aggregation="latest_period_or_time_trend",
        note="MRR 通常是月度快照指标，回答“当前 MRR”应默认取最新月份；全表求和只能解释为客户-月份记录累计求和。",
    ),
    MetricDefinition(
        name="销售额",
        aliases=("销售额", "sales", "revenue", "成交额", "订单金额"),
        metric_type="flow",
        default_aggregation="sum",
        note="销售额是流水指标；如存在订单状态，应说明是否包含取消、退货或处理中订单。",
    ),
    MetricDefinition(
        name="利润",
        aliases=("利润", "profit"),
        metric_type="flow",
        default_aggregation="sum",
        note="利润适合汇总，但负利润订单应单独披露，避免 TopN 掩盖异常折扣或成本问题。",
    ),
    MetricDefinition(
        name="利润率",
        aliases=("利润率", "margin", "profit rate", "profit_rate"),
        metric_type="ratio",
        default_aggregation="weighted_ratio",
        note="利润率不应直接简单求和；整体利润率应使用 总利润 / 总销售额。",
    ),
    MetricDefinition(
        name="流失率",
        aliases=("流失率", "churn", "churn rate", "logo churn"),
        metric_type="ratio",
        default_aggregation="count_ratio",
        note="流失率需要明确分母，例如期初客户数、当月客户数或记录数。",
    ),
    MetricDefinition(
        name="复购率",
        aliases=("复购率", "复购", "repeat purchase"),
        metric_type="ratio",
        default_aggregation="count_ratio",
        note="复购率需要明确客户唯一粒度，不能把订单行直接当客户数。",
    ),
    MetricDefinition(
        name="NPS",
        aliases=("nps",),
        metric_type="score",
        default_aggregation="avg",
        note="NPS 分析应说明缺失值处理，并避免把相关性解释成因果关系。",
    ),
    MetricDefinition(
        name="CSAT",
        aliases=("csat", "满意度"),
        metric_type="score",
        default_aggregation="avg",
        note="CSAT 分析应说明缺失值处理，并结合工单、NPS 或风险等级解释。",
    ),
    MetricDefinition(
        name="逾期金额",
        aliases=("逾期金额", "逾期", "失败", "支付失败", "overdue", "failed payment"),
        metric_type="risk_amount",
        default_aggregation="sum_and_priority",
        note="账款风险建议合并金额、支付状态和逾期天数排序，而不是只看记录数。",
    ),
)


def metric_notes_for_question(question: str, selected_columns: list[str]) -> list[str]:
    text = " ".join([question, *selected_columns]).lower()
    notes: list[str] = []
    for metric in METRIC_REGISTRY:
        if any(alias.lower() in text for alias in metric.aliases):
            notes.append(f"{metric.name}：{metric.note}")
    return notes
