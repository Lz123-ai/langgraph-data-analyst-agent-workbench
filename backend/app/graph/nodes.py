from __future__ import annotations

import os
import re
from typing import Any

from fastapi import HTTPException

from app.business.metric_registry import metric_notes_for_question
from app.datasets.profiler import profile_dataframe
from app.domain import (
    AnalysisOperation,
    AnalysisPlan,
    ChartRequest,
    DatasetProfile,
    ExecutionResult,
    ExecutionTable,
    Insight,
    QuestionUnderstanding,
    ReviewNote,
)
from app.graph.prompts import UNDERSTAND_QUESTION_PROMPT
from app.graph.state import AnalysisState
from app.settings import settings
from app.tools.chart_tool import build_charts
from app.tools.dataset_reader import read_dataframe
from app.tools.duckdb_tool import (
    build_count_by_dimension_sql,
    build_dataset_overview_sql,
    build_describe_sql,
    build_group_aggregate_sql,
    build_market_recommendation_sql,
    build_time_trend_sql,
    build_top_records_sql,
    execute_select,
)
from app.tools.pandas_tool import run_pandas_operation
from app.tools.report_tool import markdown_table
from app.tools.serialization import dataframe_to_records


ANSWERABILITY_REASON_FILTER = "__answerability_reason"
ANSWERABILITY_SUGGESTION_FILTER = "__answerability_suggestion"


def load_dataset(state: AnalysisState) -> dict[str, Any]:
    df = read_dataframe(state["file_path"], nrows=20)
    return {
        "current_step": "load_dataset",
        "dataset_preview": dataframe_to_records(df, limit=20),
        "messages": _append_message(state, "system", f"已读取数据集预览，共 {len(df)} 行。"),
    }


def profile_dataset(state: AnalysisState) -> dict[str, Any]:
    df = read_dataframe(state["file_path"])
    profile = profile_dataframe(df, dataset_id=state["dataset_id"])
    return {
        "current_step": "profile_dataset",
        "profile": profile.model_dump(mode="json"),
        "messages": _append_message(
            state,
            "system",
            f"已完成数据画像：{profile.row_count} 行，{profile.column_count} 列。",
        ),
    }


def understand_question(state: AnalysisState) -> dict[str, Any]:
    profile = DatasetProfile.model_validate(state["profile"])
    understanding = _try_llm_understanding(state["user_question"], profile) or _rule_based_understanding(
        state["user_question"],
        profile,
    )
    return {
        "current_step": "understand_question",
        "question_understanding": understanding.model_dump(mode="json"),
        "needs_clarification": understanding.needs_clarification,
        "messages": _append_message(state, "assistant", f"已识别分析目标：{_goal_label(understanding.analysis_goal)}。"),
    }


def plan_analysis(state: AnalysisState) -> dict[str, Any]:
    profile = DatasetProfile.model_validate(state["profile"])
    understanding = QuestionUnderstanding.model_validate(state["question_understanding"])
    plan = _build_plan(state["user_question"], profile, understanding)
    sub_questions = _split_compound_questions(state["user_question"]) if len(plan.operations) > 1 else []
    return {
        "current_step": "plan_analysis",
        "analysis_plan": plan.model_dump(mode="json"),
        "sub_questions": sub_questions,
        "messages": _append_message(state, "assistant", f"已规划 {len(plan.operations)} 个分析操作。"),
    }


def choose_execution_path(state: AnalysisState) -> dict[str, Any]:
    understanding = QuestionUnderstanding.model_validate(state["question_understanding"])
    plan = AnalysisPlan.model_validate(state["analysis_plan"])
    if understanding.needs_clarification or not plan.operations:
        return {
            "current_step": "choose_execution_path",
            "execution_path": "clarification",
            "needs_clarification": True,
            "messages": _append_message(state, "assistant", "问题信息不足，需要先补充说明。"),
        }
    paths = {operation.path_hint for operation in plan.operations}
    path = "duckdb_sql" if paths == {"duckdb_sql"} else "pandas"
    label = "混合执行（DuckDB SQL + pandas/scipy）" if len(paths) > 1 else _path_label(path)
    return {
        "current_step": "choose_execution_path",
        "execution_path": path,
        "needs_clarification": False,
        "messages": _append_message(state, "assistant", f"已选择执行路径：{label}。"),
    }


def run_sql_analysis(state: AnalysisState) -> dict[str, Any]:
    plan = AnalysisPlan.model_validate(state["analysis_plan"])
    df = read_dataframe(state["file_path"])
    profile = DatasetProfile.model_validate(state["profile"])
    result, sql_queries, generated_code = _execute_plan_operations(df, profile, plan)
    return {
        "current_step": "run_sql_analysis",
        "sql_queries": [*(state.get("sql_queries") or []), *sql_queries],
        "execution_result": result.model_dump(mode="json"),
        "generated_code": [*(state.get("generated_code") or []), *generated_code],
        "messages": _append_message(state, "assistant", f"已执行 {len(plan.operations)} 个分析操作，生成 {len(result.tables)} 张结果表。"),
    }


def run_pandas_analysis(state: AnalysisState) -> dict[str, Any]:
    plan = AnalysisPlan.model_validate(state["analysis_plan"])
    df = read_dataframe(state["file_path"])
    profile = DatasetProfile.model_validate(state["profile"])
    result, sql_queries, generated_code = _execute_plan_operations(df, profile, plan)
    return {
        "current_step": "run_pandas_analysis",
        "execution_result": result.model_dump(mode="json"),
        "sql_queries": [*(state.get("sql_queries") or []), *sql_queries],
        "generated_code": [*(state.get("generated_code") or []), *generated_code],
        "messages": _append_message(state, "assistant", f"已执行 {len(plan.operations)} 个分析操作，生成 {len(result.tables)} 张结果表。"),
    }


def _execute_plan_operations(
    df,
    profile: DatasetProfile,
    plan: AnalysisPlan,
) -> tuple[ExecutionResult, list[str], list[str]]:
    results: list[ExecutionResult] = []
    sql_queries: list[str] = []
    generated_code: list[str] = []

    for operation in plan.operations:
        if operation.operation_type == "unanswerable":
            result = _execute_unanswerable_operation(operation)
            generated_code.append(f"# Unanswerable by schema/value validation\n# {result.metrics.get('reason')}")
        elif operation.path_hint == "duckdb_sql":
            result, sql = _execute_duckdb_operation(df, profile, operation)
            sql_queries.append(sql)
            generated_code.append(f"-- DuckDB SQL\n{sql}")
        else:
            result, code = run_pandas_operation(df, operation)
            generated_code.append(code)
        results.append(result)

    if len(results) == 1:
        return results[0], sql_queries, generated_code
    return _combine_execution_results(results, plan.operations), sql_queries, generated_code


def _execute_duckdb_operation(df, profile: DatasetProfile, operation: AnalysisOperation) -> tuple[ExecutionResult, str]:
    sql = _build_sql(operation)
    result_df = execute_select(df, sql)
    if operation.operation_type == "dataset_overview":
        result_df["column_count"] = profile.column_count
        result_df["columns"] = ", ".join(column.name for column in profile.columns)
    if result_df.empty and _visible_filters(operation.filters):
        return _build_unanswerable_result(
            reason=f"筛选条件 {_format_filters(operation.filters)} 在当前数据集中没有匹配记录，继续聚合会产生误导性结论。",
            suggestion="请确认筛选值是否存在，或改用数据集中已有的地区、城市、类别等字段值重新提问。",
            metrics=operation.metrics,
            dimensions=operation.dimensions,
            requested_filters=operation.filters,
        ), sql
    table = ExecutionTable(
        name=operation.operation_type,
        columns=list(result_df.columns),
        rows=dataframe_to_records(result_df),
    )
    result = ExecutionResult(
        kind=operation.operation_type,
        source="duckdb",
        tables=[table],
        metrics={
            "operation": operation.operation_type,
            "metrics": operation.metrics,
            "dimensions": operation.dimensions,
            "filters": operation.filters,
            "aggregation": operation.aggregation,
            "row_count": len(result_df),
        },
        method="在内存中注册 pandas DataFrame，并使用 DuckDB SELECT 执行只读聚合查询。",
    )
    return result, sql


def _execute_unanswerable_operation(operation: AnalysisOperation) -> ExecutionResult:
    return _build_unanswerable_result(
        reason=_filter_value(operation.filters, ANSWERABILITY_REASON_FILTER) or operation.reason,
        suggestion=_filter_value(operation.filters, ANSWERABILITY_SUGGESTION_FILTER) or "请补充对应字段或改问当前数据集中存在的维度和指标。",
        metrics=operation.metrics,
        dimensions=operation.dimensions,
        requested_filters=operation.filters,
    )


def _build_unanswerable_result(
    reason: str,
    suggestion: str,
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
    requested_filters: list[str] | None = None,
) -> ExecutionResult:
    row = {
        "status": "unanswerable",
        "reason": reason,
        "suggestion": suggestion,
        "requested_metrics": ", ".join(metrics or []) or "无",
        "requested_dimensions": ", ".join(dimensions or []) or "无",
        "requested_filters": _format_filters(requested_filters or []) or "无",
    }
    return ExecutionResult(
        kind="unanswerable_with_current_schema",
        source="pandas",
        tables=[
            ExecutionTable(
                name="unanswerable_questions",
                columns=list(row.keys()),
                rows=[row],
            )
        ],
        metrics={
            "operation": "unanswerable",
            "reason": reason,
            "suggestion": suggestion,
            "metrics": metrics or [],
            "dimensions": dimensions or [],
            "filters": requested_filters or [],
            "answerability": "unanswerable",
        },
        method="在规划和执行前根据数据画像、字段语义和筛选值做可回答性校验；当前数据不足以支撑该问题，未生成替代性结论。",
    )


def _combine_execution_results(results: list[ExecutionResult], operations: list[AnalysisOperation]) -> ExecutionResult:
    tables: list[ExecutionTable] = []
    sub_results: list[dict[str, Any]] = []
    metric_names: list[str] = []
    dimension_names: list[str] = []
    sources: set[str] = set()

    for index, result in enumerate(results, start=1):
        operation = operations[index - 1] if index - 1 < len(operations) else None
        prefixed_tables: list[ExecutionTable] = []
        for table in result.tables:
            prefixed = ExecutionTable(
                name=f"q{index}_{table.name}",
                columns=table.columns,
                rows=table.rows,
            )
            tables.append(prefixed)
            prefixed_tables.append(prefixed)

        metrics = result.metrics.get("metrics")
        dimensions = result.metrics.get("dimensions")
        if isinstance(metrics, list):
            metric_names.extend(str(item) for item in metrics if item not in metric_names)
        if isinstance(dimensions, list):
            dimension_names.extend(str(item) for item in dimensions if item not in dimension_names)
        sources.add(result.source)
        sub_result = result.model_copy(update={"tables": prefixed_tables})
        sub_results.append(
            {
                "index": index,
                "kind": result.kind,
                "source": result.source,
                "method": result.method,
                "question": _subquestion_from_reason(operation.reason) if operation else None,
                "result": sub_result.model_dump(mode="json"),
            }
        )

    source = "duckdb" if sources == {"duckdb"} else "pandas"
    return ExecutionResult(
        kind="multi_analysis",
        source=source,
        tables=tables,
        metrics={
            "operation": "multi_analysis",
            "sub_result_count": len(results),
            "sub_results": sub_results,
            "metrics": metric_names,
            "dimensions": dimension_names,
        },
        method=f"将用户的复合问题拆分为 {len(results)} 个子分析，分别调用 DuckDB SQL 或 pandas/scipy 真实执行后合并结果。",
    )


def _subquestion_from_reason(reason: str) -> str | None:
    match = re.match(r"子问题\s+\d+：(.+?)。", reason)
    return match.group(1) if match else None


def _filter_value(filters: list[str], key: str) -> str | None:
    prefix = f"{key}="
    for item in filters:
        if item.startswith(prefix):
            return item.split("=", 1)[1]
    return None


def _visible_filters(filters: list[str]) -> list[str]:
    return [item for item in filters if not item.startswith("__")]


def _format_filters(filters: list[str]) -> str:
    return "、".join(_visible_filters(filters))


def generate_charts(state: AnalysisState) -> dict[str, Any]:
    result = ExecutionResult.model_validate(state["execution_result"])
    charts = build_charts(result)
    return {
        "current_step": "generate_charts",
        "charts": [chart.model_dump(mode="json") for chart in charts],
        "messages": _append_message(state, "assistant", f"已生成 {len(charts)} 个图表对象。"),
    }


def generate_insights(state: AnalysisState) -> dict[str, Any]:
    result = ExecutionResult.model_validate(state["execution_result"])
    insights = _derive_insights(result)
    return {
        "current_step": "generate_insights",
        "insights": [insight.model_dump(mode="json") for insight in insights],
        "messages": _append_message(state, "assistant", f"已生成 {len(insights)} 条有证据支撑的洞察。"),
    }


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
    if any("订单状态" in column or "status" in column.lower() for column in column_names):
        if any(keyword in question.lower() for keyword in ["销售额", "利润", "sales", "profit", "订单"]) and "已完成" not in question:
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
        "messages": _append_message(state, "assistant", "已复核证据链和数据质量风险。"),
    }


def generate_report(state: AnalysisState) -> dict[str, Any]:
    report = _build_report(state)
    return {
        "current_step": "generate_report",
        "report_markdown": report,
        "messages": _append_message(state, "assistant", "已生成 Markdown 分析报告。"),
    }


def _append_message(state: AnalysisState, role: str, content: str) -> list[dict[str, str]]:
    return [*(state.get("messages") or []), {"role": role, "content": content}]


def _goal_label(goal: str) -> str:
    labels = {
        "group_aggregate": "分组聚合",
        "count_by_dimension": "维度计数",
        "time_trend": "时间趋势",
        "correlation": "相关性分析",
        "distribution": "分布分析",
        "outlier": "异常值检测",
        "top_records": "Top 记录查询",
        "market_recommendation": "市场扩张建议",
        "dataset_overview": "数据集概览",
        "data_quality": "数据质量审计",
        "mrr_snapshot_vs_cumulative": "MRR 口径区分",
        "risk_customer_ranking": "高风险客户排名",
        "business_template_analysis": "业务模板分析",
        "multi_analysis": "多问题综合分析",
        "describe": "描述统计",
        "unanswerable": "当前数据不可回答",
        "unanswerable_with_current_schema": "当前数据不可回答",
        "clarification": "需要澄清",
    }
    return labels.get(goal, goal)


def _path_label(path: str) -> str:
    labels = {
        "duckdb_sql": "DuckDB SQL",
        "pandas": "pandas/scipy",
        "clarification": "追问澄清",
    }
    return labels.get(path, path)


def _operation_label(operation: str) -> str:
    return _goal_label(operation)


def _table_label(table_name: str) -> str:
    prefixed = re.match(r"q(\d+)_(.+)", table_name)
    if prefixed:
        return f"问题 {prefixed.group(1)} - {_table_label(prefixed.group(2))}"
    labels = {
        "group_aggregate": "分组聚合结果",
        "count_by_dimension": "维度计数结果",
        "time_trend": "时间趋势结果",
        "correlation_sample": "相关性样本",
        "histogram_bins": "分布区间",
        "outlier_rows": "异常值记录",
        "top_records": "Top 记录结果",
        "market_recommendation": "市场扩张建议结果",
        "dataset_overview": "数据集概览",
        "data_quality_issues": "数据质量问题",
        "data_quality_detail_rows": "质量问题明细行",
        "mrr_scope_comparison": "MRR 口径对比",
        "monthly_mrr": "月度 MRR",
        "risk_customer_ranking": "高风险客户 MRR 排名",
        "risk_customer_summary": "风险客户汇总",
        "payment_renewal_summary": "账款与续约风险汇总",
        "payment_collection_priority": "催收优先级明细",
        "customer_success_priority": "客户成功优先级",
        "channel_performance_risk": "渠道表现与风险",
        "industry_market_selection": "行业市场选择",
        "segment_plan_strategy": "分层与套餐策略",
        "expansion_contraction_summary": "扩张收缩汇总",
        "expansion_contraction_top_expansion": "Top 扩张客户",
        "expansion_contraction_top_contraction": "Top 收缩客户",
        "expansion_contraction_customers": "扩张收缩客户明细",
        "health_signal_correlations": "健康信号相关性",
        "pipeline_summary": "Pipeline 汇总",
        "pipeline_by_owner": "销售负责人 Pipeline",
        "pipeline_by_stage": "销售阶段 Pipeline",
        "pipeline_by_type": "商机类型 Pipeline",
        "sales_overview_status": "经营总览口径对比",
        "order_status_impact": "订单状态影响",
        "product_pareto": "商品 Pareto 贡献",
        "discount_profit_by_rate": "折扣率与利润率",
        "discount_profit_anomalies": "异常折扣订单",
        "payment_mix": "支付方式结构",
        "sales_channel_strategy": "销售渠道策略",
        "numeric_describe": "数值描述统计",
        "unanswerable_questions": "不可回答问题说明",
    }
    return labels.get(table_name, table_name)


def _try_llm_understanding(question: str, profile: DatasetProfile) -> QuestionUnderstanding | None:
    if not settings.use_llm:
        return None
    try:
        from langchain_openai import ChatOpenAI

        prompt = UNDERSTAND_QUESTION_PROMPT.format(
            question=question,
            profile=profile.model_dump(mode="json"),
        )
        model_name = os.getenv("OPENAI_MODEL", settings.openai_model)
        model = ChatOpenAI(model=model_name, temperature=0).with_structured_output(QuestionUnderstanding)
        result = model.invoke(prompt)
        if isinstance(result, QuestionUnderstanding):
            return _sanitize_understanding(result, profile)
        return _sanitize_understanding(QuestionUnderstanding.model_validate(result), profile)
    except Exception:
        return None


def _rule_based_understanding(question: str, profile: DatasetProfile) -> QuestionUnderstanding:
    mentioned = _mentioned_columns(question, [column.name for column in profile.columns])
    metrics = [column for column in mentioned if column in profile.numeric_columns]
    dimensions = [column for column in mentioned if column in profile.categorical_columns or column in profile.boolean_columns]
    time_field = next((column for column in mentioned if column in profile.datetime_columns), None)
    inferred_goal = _infer_goal(question)
    template_id = None if inferred_goal == "data_quality" else _infer_business_template(question, profile)
    goal = "business_template_analysis" if template_id else inferred_goal
    filters = _infer_value_filters(question, profile)
    filters.extend(_extract_period_filters(question))
    if template_id:
        filters.append(f"__template__={template_id}")
    month = _extract_month_number(question)
    if month:
        filters.append(f"__month__={month}")

    answerability_issue = _answerability_issue(question, profile, goal, filters)
    if answerability_issue:
        metric = _choose_metric(question, profile)
        return _make_unanswerable_understanding(
            question=question,
            profile=profile,
            reason=answerability_issue["reason"],
            suggestion=answerability_issue["suggestion"],
            metrics=[metric] if metric else metrics,
            dimensions=[],
            filters=filters,
        )

    if goal == "business_template_analysis":
        if profile.grain and profile.grain.time_field:
            time_field = profile.grain.time_field
    elif goal == "market_recommendation":
        market_metrics = _choose_market_metrics(profile)
        market_dimension = _choose_market_dimension(question, profile)
        metrics = market_metrics or metrics
        dimensions = [market_dimension] if market_dimension else dimensions
    elif goal == "mrr_snapshot_vs_cumulative":
        metric = _choose_mrr_metric(profile)
        metrics = [metric] if metric else metrics
        if profile.grain and profile.grain.time_field:
            time_field = profile.grain.time_field
    elif goal == "risk_customer_ranking":
        metric = _choose_mrr_metric(profile)
        customer_dimension = _choose_customer_dimension(profile)
        metrics = [metric] if metric else metrics
        dimensions = [customer_dimension] if customer_dimension else dimensions
        if profile.grain and profile.grain.time_field:
            time_field = profile.grain.time_field

    if goal == "correlation":
        if len(metrics) < 2:
            metrics = [*metrics, *[column for column in profile.numeric_columns if column not in metrics]][:2]
    elif goal in {"group_aggregate", "time_trend", "distribution", "outlier", "top_records", "describe"}:
        if not metrics and profile.numeric_columns:
            metrics = [_choose_metric(question, profile) or profile.numeric_columns[0]]

    if goal in {"group_aggregate", "count_by_dimension", "top_records"} and not dimensions and profile.categorical_columns:
        dimensions = [_choose_entity_dimension(question, profile) or profile.categorical_columns[0]]
    if goal == "dataset_overview" and not time_field and profile.datetime_columns:
        time_field = profile.datetime_columns[0]
    if goal == "time_trend" and not time_field and profile.datetime_columns:
        time_field = profile.datetime_columns[0]

    needs_clarification = False
    clarification_question = None
    if goal == "correlation" and len(metrics) < 2:
        needs_clarification = True
        clarification_question = "请指定两个用于相关性分析的数值字段。"
    elif goal in {"group_aggregate", "count_by_dimension", "top_records", "market_recommendation"} and not dimensions:
        needs_clarification = True
        clarification_question = "请指定要返回的实体字段，例如商品名称、客户名称或地区。"
    elif goal in {"group_aggregate", "distribution", "outlier", "top_records", "market_recommendation", "mrr_snapshot_vs_cumulative", "risk_customer_ranking", "describe"} and not metrics:
        needs_clarification = True
        clarification_question = "请指定一个数值指标字段。"
    elif goal == "time_trend" and (not time_field or not metrics):
        needs_clarification = True
        clarification_question = "请指定一个时间字段和一个数值指标，用于趋势分析。"

    return QuestionUnderstanding(
        objective=question,
        metrics=metrics,
        dimensions=dimensions,
        filters=filters,
        time_field=time_field,
        target_columns=sorted(set([*metrics, *dimensions, *([time_field] if time_field else [])])),
        analysis_goal="clarification" if needs_clarification else goal,
        confidence=0.65 if mentioned else 0.45,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
    )


def _answerability_issue(question: str, profile: DatasetProfile, goal: str, filters: list[str]) -> dict[str, str] | None:
    if goal == "top_records" and _question_requests_product_name(question) and not _has_product_name_dimension(profile):
        metric = _choose_metric(question, profile)
        metric_text = f"；已识别到指标 `{metric}`" if metric else ""
        return {
            "reason": f"问题要求返回商品名称，但当前数据集中没有商品名称、产品名称、product_name 或 name 类字段{metric_text}，不能把地区、类别等字段冒充为商品名称。",
            "suggestion": "请补充商品名称字段后重试；或改问“利润最高的类别/地区/记录是什么”。",
        }

    if goal == "market_recommendation":
        city_issue = _city_filter_issue(question, profile, filters)
        if city_issue:
            return city_issue
    return None


def _make_unanswerable_understanding(
    question: str,
    profile: DatasetProfile,
    reason: str,
    suggestion: str,
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
    filters: list[str] | None = None,
) -> QuestionUnderstanding:
    safe_metrics = [column for column in metrics or [] if column in profile.numeric_columns]
    allowed_dimensions = set(profile.categorical_columns) | set(profile.boolean_columns)
    safe_dimensions = [column for column in dimensions or [] if column in allowed_dimensions]
    answerability_filters = [
        *(filters or []),
        f"{ANSWERABILITY_REASON_FILTER}={reason}",
        f"{ANSWERABILITY_SUGGESTION_FILTER}={suggestion}",
    ]
    return QuestionUnderstanding(
        objective=question,
        metrics=safe_metrics,
        dimensions=safe_dimensions,
        filters=answerability_filters,
        time_field=None,
        target_columns=sorted(set([*safe_metrics, *safe_dimensions])),
        analysis_goal="unanswerable",
        confidence=0.9,
        needs_clarification=False,
        clarification_question=None,
    )


def _question_requests_product_name(question: str) -> bool:
    q = question.lower()
    return any(keyword in q for keyword in ["商品名称", "产品名称", "商品名", "产品名", "product name", "product_name", "item name"])


def _has_product_name_dimension(profile: DatasetProfile) -> bool:
    return _find_dimension_by_keywords(profile, ["商品名称", "产品名称", "商品名", "产品名", "product_name", "product name", "item_name", "item name"]) is not None


def _city_filter_issue(question: str, profile: DatasetProfile, filters: list[str]) -> dict[str, str] | None:
    city = _extract_city_value(question)
    if not city:
        return None
    geo_column = _choose_geo_column(profile)
    if not geo_column:
        return {
            "reason": f"问题限定了城市 `{city}`，但当前数据集中没有城市、地区或区域字段，无法计算该城市的市场建议。",
            "suggestion": "请补充城市字段，或改用当前数据集中已有的地域维度重新提问。",
        }
    if _column_value_may_exist(profile, geo_column, city):
        return None

    column = _profile_column(profile, geo_column)
    known_values = _column_known_values(profile, geo_column)
    value_text = f"；`{geo_column}` 已知取值包括：{', '.join(known_values[:8])}" if known_values else ""
    if column and column.unique_count <= max(len(known_values), 8):
        return {
            "reason": f"问题限定了城市 `{city}`，但当前 `{geo_column}` 字段中没有该取值{value_text}。",
            "suggestion": "请改用数据中真实存在的地域取值，或补充城市级字段后再做市场扩张建议。",
        }
    if _find_dimension_by_keywords(profile, ["城市", "city"]) is None and any(item.endswith(f"={city}") for item in filters):
        return {
            "reason": f"问题限定了城市 `{city}`，但当前数据只有 `{geo_column}` 等非城市字段，不能确认其是否代表城市级市场。",
            "suggestion": "请补充城市字段，或明确要按现有地域字段进行分析。",
        }
    return None


def _profile_column(profile: DatasetProfile, name: str) -> Any | None:
    return next((column for column in profile.columns if column.name == name), None)


def _column_known_values(profile: DatasetProfile, column_name: str) -> list[str]:
    column = _profile_column(profile, column_name)
    if not column:
        return []
    values: list[str] = []
    for value in column.sample_values:
        if value is not None:
            values.append(str(value))
    for item in column.top_values:
        value = item.get("value") if isinstance(item, dict) else None
        if value is not None:
            values.append(str(value))
    distinct: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            distinct.append(value.strip())
            seen.add(key)
    return distinct


def _column_value_may_exist(profile: DatasetProfile, column_name: str, value: str) -> bool:
    column = _profile_column(profile, column_name)
    known_values = _column_known_values(profile, column_name)
    if any(value == known or value.lower() == known.lower() for known in known_values):
        return True
    if not column:
        return False
    return column.unique_count > max(len(known_values), 8)


def _find_dimension_by_keywords(profile: DatasetProfile, keywords: list[str]) -> str | None:
    columns = [*profile.categorical_columns, *profile.boolean_columns]
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for column in columns:
            normalized_column = column.lower().replace(" ", "_")
            normalized_keyword = keyword_lower.replace(" ", "_")
            if normalized_keyword in normalized_column:
                return column
    return None


def _sanitize_understanding(understanding: QuestionUnderstanding, profile: DatasetProfile) -> QuestionUnderstanding:
    allowed = {column.name for column in profile.columns}
    data = understanding.model_dump()
    data["metrics"] = [column for column in understanding.metrics if column in allowed]
    data["dimensions"] = [column for column in understanding.dimensions if column in allowed]
    data["target_columns"] = [column for column in understanding.target_columns if column in allowed]
    if understanding.time_field not in allowed:
        data["time_field"] = None
    answerability_issue = _answerability_issue(
        str(data.get("objective") or ""),
        profile,
        str(data.get("analysis_goal") or ""),
        list(data.get("filters") or []),
    )
    if answerability_issue:
        return _make_unanswerable_understanding(
            question=str(data.get("objective") or ""),
            profile=profile,
            reason=answerability_issue["reason"],
            suggestion=answerability_issue["suggestion"],
            metrics=list(data.get("metrics") or []),
            dimensions=list(data.get("dimensions") or []),
            filters=list(data.get("filters") or []),
        )
    return QuestionUnderstanding.model_validate(data)


def _mentioned_columns(question: str, columns: list[str]) -> list[str]:
    q_lower = question.lower()
    q_compact = re.sub(r"\s+", "", q_lower)
    found: list[str] = []
    for column in columns:
        c_lower = column.lower()
        c_compact = re.sub(r"\s+", "", c_lower)
        if c_lower in q_lower or c_compact in q_compact:
            found.append(column)
    return found


def _infer_goal(question: str) -> str:
    q = question.lower()
    if "mrr" in q and any(keyword in q for keyword in ["当前", "累计", "口径", "快照", "current", "cumulative"]):
        return "mrr_snapshot_vs_cumulative"
    if any(keyword in q for keyword in ["高风险", "续约风险", "风险客户", "risk"]) and any(keyword in q for keyword in ["客户", "mrr", "排名", "top"]):
        return "risk_customer_ranking"
    if any(keyword in q for keyword in ["数据质量", "质量问题", "明显问题", "脏数据", "缺失", "空值", "重复", "quality", "missing", "duplicate"]):
        return "data_quality"
    if any(keyword in q for keyword in ["数据集", "字段", "原始字段", "日期范围", "多少条", "多少行", "多少个字段", "dataset", "columns", "date range"]):
        if any(keyword in q for keyword in ["字段", "日期范围", "多少条", "多少行", "数据集", "dataset", "columns", "date range"]):
            return "dataset_overview"
    if any(keyword in q for keyword in ["市场", "扩大", "扩张", "拓展", "建议", "投放", "增长", "market", "expand", "expansion", "recommend"]):
        return "market_recommendation"
    if any(keyword in q for keyword in ["最高", "最大", "最低", "最小", "top", "highest", "lowest", "largest", "smallest"]) and any(
        keyword in q for keyword in ["什么", "哪个", "哪一个", "名称", "name", "top"]
    ):
        return "top_records"
    if any(keyword in q for keyword in ["相关", "关系", "correlation", "correlate", "relationship"]):
        return "correlation"
    if any(keyword in q for keyword in ["趋势", "trend", "over time", "按月", "按年"]):
        return "time_trend"
    if any(keyword in q for keyword in ["分布", "distribution", "histogram"]):
        return "distribution"
    if any(keyword in q for keyword in ["异常", "离群", "outlier", "anomaly"]):
        return "outlier"
    if any(keyword in q for keyword in ["按", "每个", "各", "group by", "by "]):
        if any(keyword in q for keyword in ["数量", "个数", "count", "多少"]):
            return "count_by_dimension"
        return "group_aggregate"
    if any(keyword in q for keyword in ["数量", "个数", "count"]):
        return "count_by_dimension"
    return "describe"


def _infer_business_template(question: str, profile: DatasetProfile) -> str | None:
    q = question.lower()
    columns = " ".join(column.name.lower() for column in profile.columns)
    has_saas = any(keyword in columns for keyword in ["mrr", "续约风险", "获客渠道", "nps", "csat", "付款状态"])
    has_sales = any(keyword in columns for keyword in ["订单状态", "商品名称", "销售渠道", "支付方式", "折扣率"])
    has_pipeline = any(keyword in columns for keyword in ["商机金额", "销售阶段", "赢率", "pipeline", "opportunity"])

    if has_pipeline and any(keyword in q for keyword in ["pipeline", "商机", "赢单", "加权"]) and any(keyword in q for keyword in ["金额", "销售负责人", "负责人", "排序", "总"]):
        return "pipeline_summary"
    if any(keyword in q for keyword in ["账款", "逾期", "支付失败", "付款", "发票", "催收", "应收风险"]) and (
        any(keyword in q for keyword in ["续约", "风险", "联动"]) or not has_saas
    ):
        return "payment_renewal_risk"
    if has_saas and any(keyword in q for keyword in ["客户成功", "客户经理", "优先处理", "优先级"]) and any(keyword in q for keyword in ["风险", "mrr", "客户"]):
        return "customer_success_priority"
    if has_saas and any(keyword in q for keyword in ["获客渠道", "渠道复盘", "投放"]) and any(keyword in q for keyword in ["mrr", "流失", "风险", "贡献", "加大"]):
        return "channel_performance_risk"
    if has_saas and "行业" in q and any(keyword in q for keyword in ["市场", "重点", "谨慎", "适合", "选择"]):
        return "industry_market_selection"
    if has_saas and any(keyword in q for keyword in ["客户分层", "套餐", "客群", "群体"]):
        return "segment_plan_strategy"
    if has_saas and any(keyword in q for keyword in ["扩张", "收缩", "净变化", "变化", "对比"]) and "mrr" in q:
        return "expansion_contraction"
    if has_saas and any(keyword in q for keyword in ["使用时长", "工单", "nps", "csat", "健康"]) and any(keyword in q for keyword in ["关系", "相关", "风险", "mrr"]):
        return "health_signal_analysis"

    if has_sales and (
        "经营总览" in q
        or "已完成订单" in q
        or "全部订单" in q
        or ("总销售额" in q and any(keyword in q for keyword in ["总利润", "整体利润率", "区分", "口径"]))
    ):
        return "sales_overview_status"
    if has_sales and "订单状态" in q and any(keyword in q for keyword in ["影响", "统计", "取消", "退货", "销售额", "利润"]):
        return "order_status_impact"
    if has_sales and any(keyword in q for keyword in ["集中度", "pareto", "贡献", "主要销售额", "主要利润"]):
        return "product_pareto"
    if has_sales and "折扣" in q and any(keyword in q for keyword in ["利润率", "异常", "关系", "负利润"]):
        return "discount_profit_sensitivity"
    if has_sales and "支付方式" in q and any(keyword in q for keyword in ["结构", "贡献", "占比"]):
        return "payment_mix"
    if has_sales and any(keyword in q for keyword in ["渠道策略", "销售渠道", "哪个渠道"]) and any(keyword in q for keyword in ["销售额", "利润率", "取消率", "退货率"]):
        return "sales_channel_strategy"
    return None


def _business_template_label(template_id: str | None) -> str:
    labels = {
        "payment_renewal_risk": "账款与续约风险联动",
        "customer_success_priority": "客户成功优先级",
        "channel_performance_risk": "渠道表现与风险",
        "industry_market_selection": "行业市场选择",
        "segment_plan_strategy": "分层与套餐策略",
        "expansion_contraction": "MRR 扩张收缩",
        "health_signal_analysis": "客户健康信号",
        "pipeline_summary": "Pipeline 汇总",
        "sales_overview_status": "经营总览口径",
        "order_status_impact": "订单状态影响",
        "product_pareto": "商品 Pareto 贡献",
        "discount_profit_sensitivity": "折扣与利润敏感性",
        "payment_mix": "支付方式结构",
        "sales_channel_strategy": "销售渠道策略",
    }
    return labels.get(template_id or "", template_id or "业务模板")


def _infer_aggregation(question: str, goal: str) -> str:
    q = question.lower()
    if goal == "count_by_dimension" or any(keyword in q for keyword in ["数量", "个数", "count", "多少"]):
        return "count"
    if any(keyword in q for keyword in ["总", "sum", "合计"]):
        return "sum"
    if any(keyword in q for keyword in ["最大", "最高", "max"]):
        return "max"
    if any(keyword in q for keyword in ["最小", "最低", "min"]):
        return "min"
    if any(keyword in q for keyword in ["中位", "median"]):
        return "median"
    return "avg"


def _choose_metric(question: str, profile: DatasetProfile) -> str | None:
    mentioned = _mentioned_columns(question, profile.numeric_columns)
    if mentioned:
        return mentioned[0]
    semantic_groups = [
        (["mrr", "月经常性收入"], ["mrr", "月经常性收入"]),
        (["利润", "profit", "毛利"], ["利润", "profit", "margin"]),
        (["销售额", "销售金额", "收入", "营收", "sales", "revenue"], ["销售额", "销售金额", "sales", "revenue", "amount", "收入", "营收"]),
        (["金额", "amount"], ["金额", "amount"]),
        (["成本", "cost"], ["成本", "cost"]),
        (["数量", "销量", "件数", "units", "quantity", "qty"], ["数量", "销量", "units", "quantity", "qty"]),
        (["单价", "price"], ["单价", "price"]),
        (["评分", "score", "rating"], ["评分", "score", "rating"]),
    ]
    metric_keywords = ["mrr", "月经常性收入", "利润", "销售额", "金额", "收入", "成本", "数量", "单价", "评分", "profit", "sales", "revenue", "amount", "cost", "score"]
    q_lower = question.lower()
    for question_terms, column_terms in semantic_groups:
        if any(term.lower() in q_lower for term in question_terms):
            for column in profile.numeric_columns:
                column_lower = column.lower()
                if any(term.lower() in column_lower for term in column_terms):
                    return column
    for keyword in metric_keywords:
        for column in profile.numeric_columns:
            if keyword.lower() in q_lower and keyword.lower() in column.lower():
                return column
    return None


def _choose_mrr_metric(profile: DatasetProfile) -> str | None:
    for keyword in ["mrr", "月经常性收入"]:
        for column in profile.numeric_columns:
            if keyword.lower() in column.lower():
                return column
    return _choose_metric("收入", profile)


def _choose_customer_dimension(profile: DatasetProfile) -> str | None:
    for keyword in ["客户ID", "客户编号", "customer_id", "customer id"]:
        for column in profile.categorical_columns:
            if keyword.lower() in column.lower():
                return column
    for keyword in ["公司名称", "客户名称", "客户", "company", "customer"]:
        for column in profile.categorical_columns:
            if keyword.lower() in column.lower():
                return column
    return None


def _choose_entity_dimension(question: str, profile: DatasetProfile) -> str | None:
    mentioned = _mentioned_columns(question, [*profile.categorical_columns, *profile.boolean_columns])
    if mentioned:
        return mentioned[0]
    entity_keywords = ["商品名称", "产品名称", "名称", "商品", "产品", "客户名称", "客户", "地区", "城市", "类别", "name", "product", "item", "customer", "region", "city"]
    q_lower = question.lower()
    for keyword in entity_keywords:
        for column in [*profile.categorical_columns, *profile.boolean_columns]:
            column_lower = column.lower()
            if keyword.lower() in q_lower and (keyword.lower() in column_lower or column_lower in keyword.lower()):
                return column
    for preferred in ["商品名称", "产品名称", "商品", "产品", "name", "product", "item"]:
        for column in profile.categorical_columns:
            if preferred.lower() in column.lower():
                return column
    return None


def _choose_market_dimension(question: str, profile: DatasetProfile) -> str | None:
    preferred_keywords = ["商品类别", "产品类别", "品类", "类别", "category"]
    q_lower = question.lower()
    for keyword in preferred_keywords:
        for column in profile.categorical_columns:
            if keyword.lower() in q_lower and keyword.lower() in column.lower():
                return column
    for keyword in preferred_keywords:
        for column in profile.categorical_columns:
            if keyword.lower() in column.lower():
                return column
    return _choose_entity_dimension(question, profile)


def _choose_market_metrics(profile: DatasetProfile) -> list[str]:
    preferred_groups = [
        ["销售额", "sales", "revenue", "amount"],
        ["利润", "profit", "margin"],
        ["数量", "units", "quantity", "qty"],
    ]
    selected: list[str] = []
    for group in preferred_groups:
        for keyword in group:
            match = next((column for column in profile.numeric_columns if keyword.lower() in column.lower()), None)
            if match and match not in selected:
                selected.append(match)
                break
    if selected:
        return selected
    return profile.numeric_columns[:3]


def _infer_value_filters(question: str, profile: DatasetProfile) -> list[str]:
    filters: list[str] = []
    geo_column = _choose_geo_column(profile)
    if not geo_column:
        return filters
    city = _extract_city_value(question)
    if city:
        filters.append(f"{geo_column}={city}")
    return filters


def _choose_geo_column(profile: DatasetProfile) -> str | None:
    geo_keywords = ["城市", "地区", "区域", "省份", "city", "region", "province", "area"]
    for keyword in geo_keywords:
        for column in profile.categorical_columns:
            if keyword.lower() in column.lower():
                return column
    return None


def _extract_city_value(question: str) -> str | None:
    known_cities = [
        "上海",
        "北京",
        "广州",
        "深圳",
        "杭州",
        "南京",
        "苏州",
        "成都",
        "重庆",
        "天津",
        "武汉",
        "长沙",
        "西安",
        "青岛",
        "郑州",
        "厦门",
        "广州",
    ]
    return next((city for city in known_cities if city in question), None)


def _extract_period_filters(question: str) -> list[str]:
    periods: list[tuple[int, int, int]] = []
    for match in re.finditer(r"(\d{4})\s*[-/年]\s*(1[0-2]|0?[1-9])\s*月?", question):
        periods.append((match.start(), int(match.group(1)), int(match.group(2))))

    year_match = re.search(r"(\d{4})\s*年", question)
    if year_match:
        year = int(year_match.group(1))
        month_matches = list(re.finditer(r"(?<!\d)(1[0-2]|[1-9])\s*月", question))
        if len(month_matches) >= 2:
            periods.extend((match.start(), year, int(match.group(1))) for match in month_matches)

    seen: set[str] = set()
    ordered_periods: list[str] = []
    for _, year, month in sorted(periods, key=lambda item: item[0]):
        value = f"{year:04d}-{month:02d}"
        if value not in seen:
            ordered_periods.append(value)
            seen.add(value)

    filters = [f"__period__={period}" for period in ordered_periods]
    if len(ordered_periods) >= 2:
        filters.append(f"__start_period__={ordered_periods[0]}")
        filters.append(f"__end_period__={ordered_periods[-1]}")
    return filters


def _extract_month_number(question: str) -> int | None:
    match = re.search(r"(?<!\d)(1[0-2]|[1-9])\s*月", question)
    if match:
        return int(match.group(1))
    lower = question.lower()
    month_names = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    for name, value in month_names.items():
        if name in lower:
            return value
    return None


def _build_plan(question: str, profile: DatasetProfile, understanding: QuestionUnderstanding, allow_multi: bool = True) -> AnalysisPlan:
    if allow_multi and not understanding.needs_clarification:
        sub_questions = _split_compound_questions(question)
        if len(sub_questions) > 1:
            operations: list[AnalysisOperation] = []
            charts: list[ChartRequest] = []
            seen_operations: set[tuple[Any, ...]] = set()
            for index, sub_question in enumerate(sub_questions, start=1):
                sub_understanding = _rule_based_understanding(sub_question, profile)
                if sub_understanding.needs_clarification:
                    sub_understanding = _make_unanswerable_understanding(
                        question=sub_question,
                        profile=profile,
                        reason=sub_understanding.clarification_question or "该子问题缺少必要字段，无法在当前数据上安全计算。",
                        suggestion="请补充明确的指标、维度或筛选范围后重新提问。",
                        metrics=sub_understanding.metrics,
                        dimensions=sub_understanding.dimensions,
                        filters=sub_understanding.filters,
                    )
                sub_plan = _build_plan(sub_question, profile, sub_understanding, allow_multi=False)
                for operation in sub_plan.operations:
                    key = _operation_key(operation)
                    if key in seen_operations:
                        continue
                    seen_operations.add(key)
                    operations.append(
                        operation.model_copy(
                            update={"reason": f"子问题 {index}：{sub_question}。{operation.reason}"}
                        )
                    )
                for chart in sub_plan.chart_requests:
                    charts.append(chart.model_copy(update={"title": f"问题 {index}：{chart.title}"}))

            collapsible_goals = {"mrr_snapshot_vs_cumulative", "risk_customer_ranking", "business_template_analysis"}
            primary_operation_types = {operation.operation_type for operation in operations if operation.operation_type != "describe"}
            if (
                len(operations) > 1
                and understanding.analysis_goal in collapsible_goals
                and primary_operation_types == {understanding.analysis_goal}
            ):
                return _build_plan(question, profile, understanding, allow_multi=False)

            if len(operations) > 1:
                return AnalysisPlan(
                    objective=question,
                    operations=operations,
                    chart_requests=charts,
                    safety_notes=[
                        "复合问题已拆分为多个子分析；每个子分析必须来自 DuckDB、pandas、numpy 或 scipy 的真实执行。",
                        "聚合报告必须逐项引用结果表、生成的 SQL 或生成的 pandas 代码，不能把某个子问题遗漏。",
                    ],
                )

    if understanding.needs_clarification:
        return AnalysisPlan(
            objective=understanding.objective,
            operations=[],
            chart_requests=[],
            safety_notes=["问题缺少必要字段，系统不会编造计算结果。"],
        )

    goal = understanding.analysis_goal
    aggregation = _infer_aggregation(question, goal)
    metrics = list(understanding.metrics)
    dimensions = list(understanding.dimensions)

    if goal == "unanswerable":
        operation = AnalysisOperation(
            operation_type="unanswerable",
            path_hint="pandas",
            metrics=metrics,
            dimensions=dimensions,
            filters=understanding.filters,
            aggregation=None,
            reason=_filter_value(understanding.filters, ANSWERABILITY_REASON_FILTER) or "当前数据画像不足以支撑该问题。",
        )
        chart = ChartRequest(chart_type="table", title="不可回答问题说明", x=None, y=None, reason="不可回答问题以原因和建议表展示。")
    elif goal == "data_quality":
        operation = AnalysisOperation(
            operation_type="data_quality",
            path_hint="pandas",
            metrics=[],
            dimensions=[],
            filters=[],
            aggregation=None,
            reason="数据质量审计需要对真实 DataFrame 执行缺失率、重复行、唯一值和异常值扫描。",
        )
        chart = ChartRequest(chart_type="table", title="数据质量问题", x=None, y=None, reason="质量问题以明细表展示最清晰。")
    elif goal == "business_template_analysis":
        template_id = next((item.split("=", 1)[1] for item in understanding.filters if item.startswith("__template__=")), None)
        operation = AnalysisOperation(
            operation_type="business_template_analysis",
            path_hint="pandas",
            metrics=metrics,
            dimensions=dimensions,
            filters=understanding.filters,
            aggregation=None,
            template_id=template_id,
            reason=f"该问题匹配业务模板：{_business_template_label(template_id)}，需要执行固定 pandas 业务计算，避免退化为普通描述统计。",
        )
        chart = ChartRequest(chart_type="table", title=_business_template_label(template_id), x=None, y=None, reason="业务模板结果以多张可追溯结果表展示。")
    elif goal == "mrr_snapshot_vs_cumulative":
        operation = AnalysisOperation(
            operation_type="mrr_snapshot_vs_cumulative",
            path_hint="pandas",
            metrics=metrics[:1],
            dimensions=[],
            filters=understanding.filters,
            aggregation=None,
            reason="MRR 是月度快照指标，需要按时间字段区分最新月份快照与客户-月份记录累计求和。",
        )
        chart = ChartRequest(chart_type="table", title="MRR 口径对比", x=None, y=None, reason="口径对比更适合用表格展示。")
    elif goal == "risk_customer_ranking":
        operation = AnalysisOperation(
            operation_type="risk_customer_ranking",
            path_hint="pandas",
            metrics=metrics[:1],
            dimensions=dimensions[:1],
            filters=understanding.filters,
            aggregation=None,
            reason="高风险客户排名需要按月份筛选客户快照，筛选续约风险为高的客户，并按 MRR 排序。",
        )
        chart = ChartRequest(chart_type="bar", title="高风险客户 MRR 排名", x=operation.dimensions[0] if operation.dimensions else None, y="MRR", reason="柱状图展示高风险客户 MRR 排名。")
    elif goal == "dataset_overview":
        operation = AnalysisOperation(
            operation_type="dataset_overview",
            path_hint="duckdb_sql",
            metrics=[],
            dimensions=[understanding.time_field] if understanding.time_field else [],
            filters=[],
            aggregation=None,
            reason="数据集概览通过 profile 获取字段信息，并通过 DuckDB 计算真实行数和日期范围。",
        )
        chart = ChartRequest(chart_type="table", title="数据集概览", x=None, y=None, reason="概览问题以表格展示最清晰。")
    elif goal == "market_recommendation":
        operation = AnalysisOperation(
            operation_type="market_recommendation",
            path_hint="duckdb_sql",
            metrics=metrics[:3],
            dimensions=dimensions[:1],
            filters=understanding.filters,
            aggregation=None,
            reason="市场扩张建议需要先在真实数据内按品类聚合销售额、利润、订单数和数量，再基于排行给出建议。",
        )
        chart = ChartRequest(chart_type="bar", title="市场扩张建议", x=operation.dimensions[0], y="recommendation_score", reason="柱状图展示各品类的综合推荐得分。")
    elif goal == "top_records":
        operation = AnalysisOperation(
            operation_type="top_records",
            path_hint="duckdb_sql",
            metrics=metrics[:1],
            dimensions=dimensions[:2],
            filters=understanding.filters,
            aggregation="min" if _infer_aggregation(question, goal) == "min" else "max",
            reason="Top 记录查询可通过 DuckDB SQL 按真实指标排序后返回对应实体字段。",
        )
        chart = ChartRequest(chart_type="bar", title="Top 记录", x=operation.dimensions[0], y=operation.metrics[0], reason="柱状图展示排序后的实体和指标值。")
    elif goal == "count_by_dimension":
        path = "duckdb_sql"
        operation = AnalysisOperation(
            operation_type="count_by_dimension",
            path_hint=path,
            metrics=[],
            dimensions=dimensions[:1],
            filters=understanding.filters,
            aggregation="count",
            reason="按类别维度计数可通过安全的 SQL 聚合完成。",
        )
        chart = ChartRequest(chart_type="bar", title="按维度计数", x=dimensions[0], y="row_count", reason="柱状图适合对比不同分组。")
    elif goal in {"group_aggregate", "time_trend"}:
        path = "duckdb_sql"
        operation = AnalysisOperation(
            operation_type=goal,
            path_hint=path,
            metrics=metrics[:1],
            dimensions=dimensions[:1] if goal == "group_aggregate" else [understanding.time_field or ""],
            filters=understanding.filters,
            aggregation=aggregation if aggregation != "count" else "avg",
            reason="结构化聚合可在上传数据集上通过 DuckDB SQL 执行。",
        )
        chart = ChartRequest(
            chart_type="line" if goal == "time_trend" else "bar",
            title="趋势分析" if goal == "time_trend" else "分组指标",
            x=operation.dimensions[0],
            y=operation.metrics[0],
            reason="图表基于真实聚合结果生成。",
        )
    elif goal == "correlation":
        operation = AnalysisOperation(
            operation_type="correlation",
            path_hint="pandas",
            metrics=metrics[:2],
            dimensions=[],
            filters=understanding.filters,
            aggregation=None,
            reason="相关性分析需要 pandas/scipy 处理数值配对并计算 p 值。",
        )
        chart = ChartRequest(chart_type="scatter", title="相关性散点图", x=metrics[0], y=metrics[1], reason="散点图用于展示配对观测值。")
    elif goal == "distribution":
        operation = AnalysisOperation(
            operation_type="distribution",
            path_hint="pandas",
            metrics=metrics[:1],
            dimensions=[],
            filters=understanding.filters,
            aggregation=None,
            reason="分布分析使用数值描述统计和直方图区间。",
        )
        chart = ChartRequest(chart_type="histogram", title="分布直方图", x=metrics[0], y="count", reason="直方图用于展示数值分布。")
    elif goal == "outlier":
        operation = AnalysisOperation(
            operation_type="outlier",
            path_hint="pandas",
            metrics=metrics[:1],
            dimensions=[],
            filters=understanding.filters,
            aggregation=None,
            reason="异常值检测基于真实数值执行 IQR 规则。",
        )
        chart = ChartRequest(chart_type="table", title="异常值记录", x=None, y=None, reason="异常值记录适合用表格检查。")
    else:
        operation = AnalysisOperation(
            operation_type="describe",
            path_hint="pandas",
            metrics=metrics or profile.numeric_columns[:5],
            dimensions=[],
            filters=understanding.filters,
            aggregation=None,
            reason="默认描述统计会汇总真实数值字段。",
        )
        chart = ChartRequest(chart_type="table", title="描述统计", x=None, y=None, reason="汇总表是主要结果。")

    return AnalysisPlan(
        objective=understanding.objective,
        operations=[operation],
        chart_requests=[chart],
        safety_notes=[
            "所有结果必须来自 DuckDB、pandas、numpy 或 scipy 的真实执行。",
            "报告必须引用结果表、生成的 SQL 或生成的 pandas 代码。",
        ],
    )


def _split_compound_questions(question: str) -> list[str]:
    normalized = re.sub(r"[\r\n]+", "；", question.strip())
    coarse_parts = [part.strip(" ，,、：:") for part in re.split(r"[？?；;。]+", normalized) if part.strip()]
    parts: list[str] = []
    for part in coarse_parts:
        connector_parts = _split_connector_question(part)
        parts.extend(connector_parts if len(connector_parts) > 1 else [part])

    distinct: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = part.strip(" ，,、：:")
        if len(cleaned) < 2:
            continue
        if _is_modifier_fragment(cleaned) and distinct:
            distinct[-1] = f"{distinct[-1]}，{cleaned}"
            continue
        if _is_overview_fragment(cleaned) and distinct and _is_overview_fragment(distinct[-1]):
            distinct[-1] = f"{distinct[-1]}，{cleaned}"
            continue
        key = re.sub(r"\s+", "", cleaned.lower())
        if key in seen:
            continue
        seen.add(key)
        distinct.append(cleaned)
    return distinct or [question]


def _is_modifier_fragment(text: str) -> bool:
    compact = re.sub(r"\s+", "", text.lower())
    return (
        compact.startswith(("按", "根据", "依照", "按照", "by"))
        and any(keyword in compact for keyword in ["排序", "排名", "分组", "拆分", "汇总", "对比", "比较", "sort", "rank", "group"])
        and not any(keyword in compact for keyword in ["多少", "是什么", "哪些", "哪类", "哪个", "分析", "建议", "?"])
    )


def _is_overview_fragment(text: str) -> bool:
    q = text.lower()
    return any(keyword in q for keyword in ["数据集", "字段", "原始字段", "日期范围", "多少条", "多少行", "columns", "date range"])


def _split_connector_question(text: str) -> list[str]:
    candidates = [part.strip(" ，,、：:") for part in re.split(r"(?:，并|, and|并且|以及|同时|另外|还有)", text) if part.strip(" ，,、：:")]
    if len(candidates) <= 1:
        return [text]
    if all(_looks_like_subquestion(part) for part in candidates):
        return candidates
    return [text]


def _looks_like_subquestion(text: str) -> bool:
    q = text.lower()
    intent_keywords = [
        "多少",
        "字段",
        "日期范围",
        "数据质量",
        "质量问题",
        "最高",
        "最低",
        "排名",
        "top",
        "市场",
        "建议",
        "mrr",
        "风险",
        "pipeline",
        "商机",
        "相关",
        "关系",
        "趋势",
        "分布",
        "异常",
        "按",
        "统计",
        "总",
        "平均",
        "口径",
    ]
    return any(keyword in q for keyword in intent_keywords)


def _operation_key(operation: AnalysisOperation) -> tuple[Any, ...]:
    if operation.operation_type == "business_template_analysis":
        return (
            operation.operation_type,
            operation.template_id,
            tuple(operation.filters),
            operation.aggregation,
        )
    return (
        operation.operation_type,
        tuple(operation.metrics),
        tuple(operation.dimensions),
        tuple(operation.filters),
        operation.aggregation,
        operation.template_id,
    )


def _build_sql(operation: AnalysisOperation) -> str:
    if operation.operation_type == "group_aggregate":
        if not operation.dimensions or not operation.metrics or not operation.aggregation:
            raise HTTPException(status_code=400, detail="分组聚合需要一个维度字段和一个指标字段。")
        return build_group_aggregate_sql(operation.dimensions[0], operation.metrics[0], operation.aggregation, filters=operation.filters)
    if operation.operation_type == "count_by_dimension":
        if not operation.dimensions:
            raise HTTPException(status_code=400, detail="按维度计数需要一个维度字段。")
        return build_count_by_dimension_sql(operation.dimensions[0], filters=operation.filters)
    if operation.operation_type == "time_trend":
        if not operation.dimensions or not operation.metrics or not operation.aggregation:
            raise HTTPException(status_code=400, detail="时间趋势分析需要一个时间字段和一个指标字段。")
        return build_time_trend_sql(operation.dimensions[0], operation.metrics[0], operation.aggregation, filters=operation.filters)
    if operation.operation_type == "top_records":
        if not operation.dimensions or not operation.metrics:
            raise HTTPException(status_code=400, detail="Top 记录查询需要至少一个实体字段和一个指标字段。")
        return build_top_records_sql(operation.dimensions, operation.metrics[0], filters=operation.filters, descending=operation.aggregation != "min")
    if operation.operation_type == "market_recommendation":
        if not operation.dimensions or not operation.metrics:
            raise HTTPException(status_code=400, detail="市场建议需要一个品类维度和至少一个数值指标。")
        return build_market_recommendation_sql(operation.dimensions[0], operation.metrics, filters=operation.filters)
    if operation.operation_type == "dataset_overview":
        date_field = operation.dimensions[0] if operation.dimensions else None
        return build_dataset_overview_sql(date_field)
    if operation.metrics:
        return build_describe_sql(operation.metrics[0])
    raise HTTPException(status_code=400, detail="无法构建 SQL 分析操作。")


def _derive_insights(result: ExecutionResult) -> list[Insight]:
    insights: list[Insight] = []
    if result.kind == "multi_analysis":
        sub_results = result.metrics.get("sub_results")
        if isinstance(sub_results, list):
            for item in sub_results:
                if not isinstance(item, dict) or not item.get("result"):
                    continue
                index = item.get("index")
                sub_result = ExecutionResult.model_validate(item["result"])
                for insight in _derive_insights(sub_result):
                    insights.append(
                        Insight(
                            text=f"问题 {index}：{insight.text}",
                            evidence=insight.evidence,
                            confidence=insight.confidence,
                        )
                    )
        if not insights:
            insights.append(
                Insight(
                    text=f"已完成 {result.metrics.get('sub_result_count', len(result.tables))} 个子分析，并合并生成可追溯结果表。",
                    evidence="结果表：multi_analysis",
                    confidence="medium",
                )
            )
    elif result.kind == "unanswerable_with_current_schema":
        reason = str(result.metrics.get("reason") or "当前数据不足以支撑该问题。")
        suggestion = str(result.metrics.get("suggestion") or "请补充字段或调整问题后重试。")
        insights.append(
            Insight(
                text=f"当前问题无法被该数据集直接回答：{reason} 建议：{suggestion}",
                evidence=f"结果表：{_table_label(result.tables[0].name) if result.tables else 'unanswerable_questions'}；方法：{result.method}",
                confidence="high",
            )
        )
    elif result.kind == "data_quality" and result.tables:
        table = result.tables[0]
        rows = table.rows
        issue_count = result.metrics.get("issue_count", len(rows))
        duplicate_count = result.metrics.get("duplicate_count", 0)
        high_severity = [row for row in rows if row.get("severity") == "high"]
        warning = [row for row in rows if row.get("severity") == "warning"]
        insights.append(
            Insight(
                text=f"本次数据质量扫描发现 {issue_count} 条质量提示，其中高风险 {len(high_severity)} 条、警告 {len(warning)} 条、重复行 {duplicate_count} 行。",
                evidence=f"结果表：{_table_label(table.name)}；方法：{result.method}",
                confidence="high",
            )
        )
        if rows:
            first = rows[0]
            insights.append(
                Insight(
                    text=f"首要问题是 {first.get('issue_type')}：{first.get('detail')} 建议：{first.get('suggestion')}",
                    evidence=f"结果表：{_table_label(table.name)}",
                    confidence="high" if first.get("severity") in {"high", "warning"} else "medium",
                )
            )
    elif result.kind == "dataset_overview" and result.tables:
        table = result.tables[0]
        rows = table.rows
        if rows:
            row = rows[0]
            row_count = row.get("row_count")
            column_count = row.get("column_count")
            min_date = row.get("min_date")
            max_date = row.get("max_date")
            if min_date and max_date:
                text = f"该数据集共有 {row_count} 行记录、{column_count} 个原始字段，日期范围为 {min_date} 至 {max_date}。"
            else:
                text = f"该数据集共有 {row_count} 行记录、{column_count} 个原始字段。"
            insights.append(
                Insight(
                    text=text,
                    evidence=f"结果表：{_table_label(table.name)}；方法：{result.method}",
                    confidence="high",
                )
            )
    elif result.kind == "market_recommendation" and result.tables:
        table = result.tables[0]
        rows = table.rows
        if rows:
            top = rows[0]
            scope = result.metrics.get("filters") or []
            scope_text = f"在 {'、'.join(scope)} 条件下，" if isinstance(scope, list) and scope else ""
            insights.append(
                Insight(
                    text=f"{scope_text}{top.get('dimension')} 的综合推荐得分最高，订单数为 {top.get('order_count')}，总销售额为 {top.get('total_sales')}，总利润为 {top.get('total_profit')}。建议优先评估该品类的扩张机会。",
                    evidence=f"结果表：{_table_label(table.name)}；方法：{result.method}",
                    confidence="high",
                )
            )
            insights.append(
                Insight(
                    text="该建议只基于上传数据的销售表现，不代表外部市场容量、竞品强度或供应链能力；正式扩张前应补充外部市场和成本约束数据。",
                    evidence="review: 数据边界说明",
                    confidence="medium",
                )
            )
    elif result.kind == "mrr_snapshot_vs_cumulative" and result.tables:
        rows = result.tables[0].rows
        if len(rows) >= 2:
            current = rows[0]
            cumulative = rows[1]
            insights.append(
                Insight(
                    text=f"当前 MRR 为 {current.get('MRR')}，口径是 {current.get('计算方式')}；累计 MRR 为 {cumulative.get('MRR')}，口径是 {cumulative.get('计算方式')}。",
                    evidence=f"结果表：{_table_label(result.tables[0].name)}；方法：{result.method}",
                    confidence="high",
                )
            )
            insights.append(
                Insight(
                    text="当前 MRR 是最新月份快照，用于衡量当前订阅规模；累计 MRR 是客户-月份记录求和，不能当作当前 MRR 或 ARR。",
                    evidence=f"指标口径：{result.metrics.get('mrr_column')}；最新期间：{result.metrics.get('latest_period')}",
                    confidence="high",
                )
            )
    elif result.kind == "risk_customer_ranking" and result.tables:
        ranking = result.tables[0].rows
        summary = result.tables[1].rows if len(result.tables) > 1 else []
        if ranking:
            top = ranking[0]
            name = top.get("公司名称") or top.get("客户ID") or top.get("排名")
            insights.append(
                Insight(
                    text=f"{result.metrics.get('period')} 高风险客户中，{name} 的 MRR 最高，为 {top.get('MRR')}。",
                    evidence=f"结果表：{_table_label(result.tables[0].name)}；方法：{result.method}",
                    confidence="high",
                )
            )
        if summary:
            high = summary[0]
            insights.append(
                Insight(
                    text=f"{high.get('范围')} 高风险客户共 {high.get('客户数')} 个，对应 MRR 为 {high.get('MRR')}。",
                    evidence=f"结果表：{_table_label(result.tables[1].name)}",
                    confidence="high",
                )
            )
    elif result.kind == "business_template_analysis" and result.tables:
        template_id = str(result.metrics.get("template_id") or "")
        table = result.tables[0]
        rows = table.rows
        if rows:
            if template_id == "payment_renewal_risk":
                current = rows[1] if len(rows) > 1 else rows[0]
                insights.append(
                    Insight(
                        text=f"{current.get('范围')} 的{current.get('口径')}共有 {current.get('记录数')} 条，涉及 {current.get('客户数')} 个客户，金额为 {current.get('发票金额')}。",
                        evidence=f"结果表：{_table_label(table.name)}；方法：{result.method}",
                        confidence="high",
                    )
                )
                if len(result.tables) > 1 and result.tables[1].rows:
                    top = result.tables[1].rows[0]
                    customer = top.get("客户ID") or top.get("公司名称") or top.get("客户名称") or "首位客户"
                    amount = top.get("发票金额") or top.get("逾期金额")
                    insights.append(
                        Insight(
                            text=f"催收优先级最高的是 {customer}，问题账款金额为 {amount}。",
                            evidence=f"结果表：{_table_label(result.tables[1].name)}",
                            confidence="high",
                        )
                    )
            else:
                label = _business_template_label(template_id)
                first = rows[0]
                key_values = "，".join(f"{key}={value}" for key, value in list(first.items())[:4])
                insights.append(
                    Insight(
                        text=f"{label} 已生成 {len(rows)} 行核心结果，首行结果为：{key_values}。",
                        evidence=f"结果表：{_table_label(table.name)}；方法：{result.method}",
                        confidence="high",
                    )
                )
    elif result.kind in {"group_aggregate", "count_by_dimension", "time_trend", "top_records"} and result.tables:
        table = result.tables[0]
        rows = table.rows
        if rows:
            metric_candidates = result.metrics.get("metrics")
            dimension_candidates = result.metrics.get("dimensions")
            measure = metric_candidates[0] if isinstance(metric_candidates, list) and metric_candidates and metric_candidates[0] in table.columns else next((column for column in table.columns if column not in {"dimension", "period"}), table.columns[-1])
            label_key = dimension_candidates[0] if isinstance(dimension_candidates, list) and dimension_candidates and dimension_candidates[0] in table.columns else ("period" if "period" in table.columns else "dimension")
            top = rows[0] if result.kind == "top_records" else max(rows, key=lambda row: row.get(measure) if row.get(measure) is not None else float("-inf"))
            insights.append(
                Insight(
                    text=f"{label_key}={top.get(label_key)} 的 {measure} 最高，为 {top.get(measure)}。",
                    evidence=f"结果表：{_table_label(table.name)}；方法：{result.method}",
                    confidence="high",
                )
            )
            insights.append(
                Insight(
                    text=f"结果表共包含 {len(rows)} 行计算结果；如原始结果更大，已按展示限制截断。",
                    evidence=f"结果表：{_table_label(table.name)}",
                    confidence="medium",
                )
            )
    elif result.kind == "correlation":
        corr = result.metrics.get("correlation")
        p_value = result.metrics.get("p_value")
        x = result.metrics.get("x")
        y = result.metrics.get("y")
        insights.append(
            Insight(
                text=f"{x} 与 {y} 的 Pearson 相关系数为 {corr}，p 值为 {p_value}。",
                evidence=f"指标：correlation、p_value；方法：{result.method}",
                confidence="high",
            )
        )
    elif result.kind == "distribution":
        insights.append(
            Insight(
                text=f"分布摘要：均值={result.metrics.get('mean')}，中位数={result.metrics.get('50%')}，标准差={result.metrics.get('std')}。",
                evidence=f"指标：describe；结果表：{_table_label(result.tables[0].name)}",
                confidence="high",
            )
        )
    elif result.kind == "outlier":
        insights.append(
            Insight(
                text=f"基于 IQR 规则，字段 {result.metrics.get('metric')} 检测到 {result.metrics.get('outlier_count')} 行异常值。",
                evidence=f"指标：IQR 边界；结果表：{_table_label(result.tables[0].name)}",
                confidence="high",
            )
        )
    elif result.kind == "describe" and result.tables:
        insights.append(
            Insight(
                text=f"已为 {len(result.tables[0].rows)} 个数值字段计算描述统计。",
                evidence=f"结果表：{_table_label(result.tables[0].name)}；方法：{result.method}",
                confidence="high",
            )
        )
    return insights


def _build_report(state: AnalysisState) -> str:
    if state.get("needs_clarification") and not state.get("execution_result"):
        understanding = QuestionUnderstanding.model_validate(state["question_understanding"])
        question = understanding.clarification_question or "请补充说明分析目标。"
        return f"# 分析需要澄清\n\n{question}\n\n当前未生成任何数据结论。"

    profile = DatasetProfile.model_validate(state["profile"])
    plan = AnalysisPlan.model_validate(state["analysis_plan"])
    result = ExecutionResult.model_validate(state["execution_result"])
    insights = [Insight.model_validate(item) for item in state.get("insights", [])]
    review_notes = [ReviewNote.model_validate(item) for item in state.get("review_notes", [])]

    parts: list[str] = [
        "# 数据分析报告",
        "",
        "## 分析目标",
        state["user_question"],
        "",
        "## 数据概况",
        f"- 行数：{profile.row_count}",
        f"- 列数：{profile.column_count}",
        f"- 数值字段：{', '.join(profile.numeric_columns) or '无'}",
        f"- 类别字段：{', '.join(profile.categorical_columns) or '无'}",
        f"- 时间字段：{', '.join(profile.datetime_columns) or '无'}",
    ]
    if profile.grain:
        grain = profile.grain
        grain_columns = " + ".join(grain.grain_columns) if grain.grain_columns else "未识别"
        parts.extend(
            [
                f"- 业务粒度：{grain.grain_type}",
                f"- 候选粒度字段：{grain_columns}",
            ]
        )
        if grain.time_field and grain.time_range:
            parts.append(f"- 时间范围：{grain.time_field} = {grain.time_range.get('min')} 至 {grain.time_range.get('max')}")
        for note in grain.notes[:2]:
            parts.append(f"- 口径提示：{note}")
    operation_summary = "、".join(_operation_label(operation.operation_type) for operation in plan.operations) if plan.operations else "无"
    parts.extend(
        [
            "",
            "## 分析方法",
            f"- 执行路径：{_path_label(str(state.get('execution_path')))}",
            f"- 分析操作：{operation_summary}",
            f"- 方法说明：{result.method}",
        ]
    )
    if result.kind == "multi_analysis":
        parts.extend(["", "## 子问题执行清单"])
        sub_results = result.metrics.get("sub_results")
        if isinstance(sub_results, list):
            for item in sub_results:
                if not isinstance(item, dict):
                    continue
                question_text = item.get("question")
                prefix = f"问题 {item.get('index')}：{question_text}" if question_text else f"问题 {item.get('index')}"
                status = "不可回答" if item.get("kind") == "unanswerable_with_current_schema" else "已回答"
                parts.append(
                    f"- {prefix}；状态：{status}；分析类型：{_operation_label(str(item.get('kind')))}，"
                    f"执行引擎：{_path_label('duckdb_sql') if item.get('source') == 'duckdb' else _path_label('pandas')}。"
                )
    metric_notes = metric_notes_for_question(
        state["user_question"],
        [*result.metrics.get("metrics", []), *result.metrics.get("dimensions", [])]
        if isinstance(result.metrics.get("metrics"), list) and isinstance(result.metrics.get("dimensions"), list)
        else [],
    )
    if metric_notes:
        parts.extend(["", "## 指标口径提示"])
        parts.extend([f"- {note}" for note in metric_notes[:4]])

    if state.get("sql_queries"):
        parts.extend(["", "## SQL 追踪", "```sql", "\n\n".join(state["sql_queries"]), "```"])
    if state.get("generated_code"):
        parts.extend(["", "## 执行追踪", "```python", "\n\n".join(state["generated_code"]), "```"])

    parts.extend(["", "## 结果表"])
    for table in result.tables:
        parts.extend(["", f"### {_table_label(table.name)}", markdown_table(table.rows, table.columns)])

    parts.extend(["", "## 核心发现"])
    if insights:
        parts.extend([f"- {insight.text} _（证据：{insight.evidence}）_" for insight in insights])
    else:
        parts.append("- 未生成可被数据支撑的发现。")

    parts.extend(["", "## 图表"])
    charts = state.get("charts") or []
    if charts:
        parts.extend([f"- {chart['title']}（`{chart['chart_id']}`），来源结果表：{_table_label(str(chart.get('evidence_table')))}" for chart in charts])
    else:
        parts.append("- 未生成图表。")

    parts.extend(["", "## 风险与数据质量提示"])
    if review_notes:
        parts.extend([f"- [{note.severity}] {note.note}" for note in review_notes])
    else:
        parts.append("- 复核节点未发现主要数据质量风险。")

    parts.extend(
        [
            "",
            "## 下一步建议",
            "- 确认当前指标和维度是否符合业务定义。",
            "- 如果问题需要更细分的人群或范围，可增加过滤条件或分组维度。",
            "- 对高缺失或口径不一致的字段完成清洗后，重新运行分析。",
        ]
    )
    return "\n".join(parts)
