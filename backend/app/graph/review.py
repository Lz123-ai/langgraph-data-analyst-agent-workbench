from __future__ import annotations

from typing import Any

from app.domain import DatasetProfile, ExecutionResult, Insight, ReviewNote
from app.graph.state import AnalysisState


def review_answer(state: AnalysisState) -> dict[str, Any]:
    profile = DatasetProfile.model_validate(state["profile"])
    insights = [Insight.model_validate(item) for item in state.get("insights", [])]
    notes: list[ReviewNote] = []
    question = state.get("user_question", "")
    if not insights:
        notes.append(ReviewNote(severity="warning", note="未生成可被结果支撑的洞察。", evidence="execution_result"))

    high_missing = [column.name for column in profile.columns if column.missing_rate >= 0.2]
    if high_missing:
        notes.append(
            ReviewNote(
                severity="warning",
                note=f"以下字段缺失率不低于 20%，可能影响解读：{', '.join(high_missing)}。",
                evidence="dataset_profile",
            )
        )

    column_names = [column.name for column in profile.columns]
    has_order_status = any("订单状态" in column or "status" in column.lower() for column in column_names)
    asks_order_metrics = any(keyword in question.lower() for keyword in ["销售额", "利润", "sales", "profit", "订单"])
    if has_order_status and asks_order_metrics and "已完成" not in question:
        notes.append(
            ReviewNote(
                severity="warning",
                note="数据中存在订单状态字段，当前问题未明确是否只看已完成订单；报告结论应说明是否包含取消、退货或处理中订单。",
                evidence="dataset_profile",
            )
        )

    if any("mrr" in column.lower() for column in column_names):
        notes.append(
            ReviewNote(
                severity="info",
                note="MRR 通常是月度快照指标；当前 MRR 应优先取最新月份，跨月全表求和只能解释为客户-月份累计记录求和。",
                evidence="metric_registry",
            )
        )

    if state.get("sub_questions") and state.get("execution_result"):
        result = ExecutionResult.model_validate(state["execution_result"])
        if result.kind == "multi_analysis":
            expected = len(state.get("sub_questions") or [])
            actual = int(result.metrics.get("sub_result_count") or 0)
            if actual < expected:
                notes.append(
                    ReviewNote(
                        severity="warning",
                        note=f"复合问题包含 {expected} 个子问题，但当前只生成 {actual} 个子结果；需要检查是否存在漏答。",
                        evidence="multi_analysis.sub_result_count",
                    )
                )

    reviewed_insights = [insight for insight in insights if insight.evidence]
    return {
        "current_step": "review_answer",
        "insights": [insight.model_dump(mode="json") for insight in reviewed_insights],
        "review_notes": [note.model_dump(mode="json") for note in notes],
        "messages": [
            *state.get("messages", []),
            {"role": "assistant", "content": "已复核证据链和数据质量风险。"},
        ],
    }
