from __future__ import annotations

from app.domain import ChartArtifact, ExecutionResult


def build_charts(result: ExecutionResult) -> list[ChartArtifact]:
    if not result.tables:
        return []
    if result.kind == "multi_analysis":
        charts: list[ChartArtifact] = []
        sub_results = result.metrics.get("sub_results")
        if not isinstance(sub_results, list):
            return [_table_chart(result, "分析结果")]
        for index, item in enumerate(sub_results, start=1):
            if not isinstance(item, dict) or not item.get("result"):
                continue
            sub_result = ExecutionResult.model_validate(item["result"])
            for chart in build_charts(sub_result):
                charts.append(
                    chart.model_copy(
                        update={
                            "chart_id": f"q{index}_{chart.chart_id}",
                            "title": f"问题 {index}：{chart.title}",
                        }
                    )
                )
        return charts
    if result.kind in {"group_aggregate", "count_by_dimension", "top_records", "market_recommendation", "risk_customer_ranking"}:
        return [_bar_from_table(result)]
    if result.kind == "time_trend":
        return [_line_from_table(result)]
    if result.kind == "correlation":
        return [_scatter_from_table(result)]
    if result.kind == "distribution":
        return [_histogram_from_table(result)]
    if result.kind == "outlier":
        return [_table_chart(result, "异常值记录")]
    return [_table_chart(result, "分析结果")]


def _bar_from_table(result: ExecutionResult) -> ChartArtifact:
    table = result.tables[0]
    dimensions = result.metrics.get("dimensions")
    metrics = result.metrics.get("metrics")
    x_key = dimensions[0] if isinstance(dimensions, list) and dimensions and dimensions[0] in table.columns else "dimension"
    if x_key not in table.columns:
        x_key = table.columns[0]
    if result.kind == "market_recommendation" and "recommendation_score" in table.columns:
        y_key = "recommendation_score"
    elif result.kind == "risk_customer_ranking" and "MRR" in table.columns:
        y_key = "MRR"
    else:
        y_key = metrics[0] if isinstance(metrics, list) and metrics and metrics[0] in table.columns else next((column for column in table.columns if column != x_key), table.columns[-1])
    rows = table.rows
    return ChartArtifact(
        chart_id="chart_bar_1",
        title="市场扩张建议" if result.kind == "market_recommendation" else ("高风险客户 MRR 排名" if result.kind == "risk_customer_ranking" else ("Top 记录" if result.kind == "top_records" else "分组分析")),
        chart_type="bar",
        evidence_table=table.name,
        echarts_option={
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 48, "right": 20, "top": 48, "bottom": 72},
            "xAxis": {"type": "category", "data": [row.get(x_key) for row in rows], "axisLabel": {"rotate": 30}},
            "yAxis": {"type": "value"},
            "series": [{"name": y_key, "type": "bar", "data": [row.get(y_key) for row in rows]}],
        },
    )


def _line_from_table(result: ExecutionResult) -> ChartArtifact:
    table = result.tables[0]
    y_key = next((column for column in table.columns if column != "period"), table.columns[-1])
    rows = table.rows
    return ChartArtifact(
        chart_id="chart_line_1",
        title="时间趋势",
        chart_type="line",
        evidence_table=table.name,
        echarts_option={
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 48, "right": 20, "top": 48, "bottom": 52},
            "xAxis": {"type": "category", "data": [row.get("period") for row in rows]},
            "yAxis": {"type": "value"},
            "series": [{"name": y_key, "type": "line", "smooth": True, "data": [row.get(y_key) for row in rows]}],
        },
    )


def _scatter_from_table(result: ExecutionResult) -> ChartArtifact:
    table = result.tables[0]
    x_key = result.metrics.get("x", table.columns[0])
    y_key = result.metrics.get("y", table.columns[1])
    rows = table.rows
    return ChartArtifact(
        chart_id="chart_scatter_1",
        title="相关性散点图",
        chart_type="scatter",
        evidence_table=table.name,
        echarts_option={
            "tooltip": {"trigger": "item"},
            "grid": {"left": 48, "right": 20, "top": 48, "bottom": 52},
            "xAxis": {"type": "value", "name": x_key},
            "yAxis": {"type": "value", "name": y_key},
            "series": [{"type": "scatter", "data": [[row.get(x_key), row.get(y_key)] for row in rows]}],
        },
    )


def _histogram_from_table(result: ExecutionResult) -> ChartArtifact:
    table = result.tables[0]
    rows = table.rows
    labels = [f"{_safe_number(row.get('bin_start')):.2f}-{_safe_number(row.get('bin_end')):.2f}" for row in rows]
    return ChartArtifact(
        chart_id="chart_histogram_1",
        title="分布直方图",
        chart_type="histogram",
        evidence_table=table.name,
        echarts_option={
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 48, "right": 20, "top": 48, "bottom": 72},
            "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 30}},
            "yAxis": {"type": "value"},
            "series": [{"name": "count", "type": "bar", "data": [row.get("count") for row in rows]}],
        },
    )


def _safe_number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _table_chart(result: ExecutionResult, title: str) -> ChartArtifact:
    table = result.tables[0]
    return ChartArtifact(
        chart_id="chart_table_1",
        title=title,
        chart_type="table",
        evidence_table=table.name,
        echarts_option={
            "title": {"text": title},
            "dataset": {"source": table.rows},
            "xAxis": {"type": "category"},
            "yAxis": {"type": "value"},
            "series": [],
        },
    )
