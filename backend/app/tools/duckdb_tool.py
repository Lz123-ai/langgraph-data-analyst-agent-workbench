from __future__ import annotations

import re
from typing import Any

import duckdb
import pandas as pd
from fastapi import HTTPException


FORBIDDEN_SQL_PATTERNS = re.compile(
    r"\b(copy|attach|install|load|pragma|create|insert|update|delete|drop|alter|export|import|read_csv|read_parquet|read_json)\b",
    re.IGNORECASE,
)


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def validate_select_sql(sql: str) -> None:
    normalized = sql.strip().rstrip(";")
    if not normalized.lower().startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT statements are allowed.")
    if ";" in normalized:
        raise HTTPException(status_code=400, detail="Multiple SQL statements are not allowed.")
    if FORBIDDEN_SQL_PATTERNS.search(normalized):
        raise HTTPException(status_code=400, detail="SQL contains a forbidden operation.")


def execute_select(df: pd.DataFrame, sql: str, limit: int = 200) -> pd.DataFrame:
    validate_select_sql(sql)
    limited_sql = f"SELECT * FROM ({sql.strip().rstrip(';')}) AS safe_result LIMIT {int(limit)}"
    connection = None
    try:
        connection = duckdb.connect(database=":memory:", read_only=False)
        connection.register("dataset", df)
        return connection.execute(limited_sql).fetchdf()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"DuckDB execution failed: {exc}") from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def build_group_aggregate_sql(
    dimension: str,
    metric: str,
    aggregation: str,
    filters: list[str] | None = None,
    descending: bool = True,
    limit: int = 20,
) -> str:
    agg_map: dict[str, str] = {
        "sum": "SUM",
        "avg": "AVG",
        "count": "COUNT",
        "min": "MIN",
        "max": "MAX",
        "median": "MEDIAN",
    }
    agg = agg_map.get(aggregation, "AVG")
    metric_expr = "*" if agg == "COUNT" else quote_identifier(metric)
    alias = f"{aggregation}_{metric}" if agg != "COUNT" else "row_count"
    order = "DESC" if descending else "ASC"
    where_clause = _build_where_clause([f"{dimension}=__NOT_NULL__", *(filters or [])])
    return (
        f"SELECT {quote_identifier(dimension)} AS dimension, "
        f"{agg}({metric_expr}) AS {quote_identifier(alias)} "
        f"FROM dataset "
        f"WHERE {where_clause} "
        f"GROUP BY {quote_identifier(dimension)} "
        f"ORDER BY {quote_identifier(alias)} {order} "
        f"LIMIT {int(limit)}"
    )


def build_count_by_dimension_sql(dimension: str, filters: list[str] | None = None, limit: int = 20) -> str:
    where_clause = _build_where_clause([f"{dimension}=__NOT_NULL__", *(filters or [])])
    return (
        f"SELECT {quote_identifier(dimension)} AS dimension, COUNT(*) AS row_count "
        f"FROM dataset "
        f"WHERE {where_clause} "
        f"GROUP BY {quote_identifier(dimension)} "
        f"ORDER BY row_count DESC "
        f"LIMIT {int(limit)}"
    )


def build_time_trend_sql(time_field: str, metric: str, aggregation: str, filters: list[str] | None = None, limit: int = 200) -> str:
    agg_map: dict[str, str] = {"sum": "SUM", "avg": "AVG", "min": "MIN", "max": "MAX", "median": "MEDIAN"}
    agg = agg_map.get(aggregation, "AVG")
    time_expr = f"date_trunc('month', TRY_CAST({quote_identifier(time_field)} AS TIMESTAMP))"
    alias = f"{aggregation}_{metric}"
    where_clause = _build_where_clause([*list(filters or [])])
    return (
        f"SELECT {time_expr} AS period, {agg}({quote_identifier(metric)}) AS {quote_identifier(alias)} "
        f"FROM dataset "
        f"WHERE {time_expr} IS NOT NULL AND {quote_identifier(metric)} IS NOT NULL"
        f"{' AND ' + where_clause if where_clause else ''} "
        f"GROUP BY period "
        f"ORDER BY period ASC "
        f"LIMIT {int(limit)}"
    )


def build_top_records_sql(dimensions: list[str], metric: str, filters: list[str] | None = None, descending: bool = True, limit: int = 20) -> str:
    selected_dimensions = dimensions[:3]
    if not selected_dimensions:
        selected_dimensions = []
    select_columns = [quote_identifier(column) for column in [*selected_dimensions, metric]]
    not_null_checks = [f"{quote_identifier(metric)} IS NOT NULL"]
    not_null_checks.extend(f"{quote_identifier(column)} IS NOT NULL" for column in selected_dimensions)
    filter_clause = _build_where_clause(filters or [])
    order = "DESC" if descending else "ASC"
    return (
        f"SELECT {', '.join(select_columns)} "
        f"FROM dataset "
        f"WHERE {' AND '.join(not_null_checks)}"
        f"{' AND ' + filter_clause if filter_clause else ''} "
        f"ORDER BY {quote_identifier(metric)} {order} "
        f"LIMIT {int(limit)}"
    )


def build_market_recommendation_sql(category_dimension: str, metrics: list[str], filters: list[str] | None = None, limit: int = 10) -> str:
    sales_metric = _first_matching_metric(metrics, ["销售额", "sales", "revenue", "amount"])
    profit_metric = _first_matching_metric(metrics, ["利润", "profit", "margin"])
    quantity_metric = _first_matching_metric(metrics, ["数量", "units", "quantity", "qty"])
    select_parts = [
        f"{quote_identifier(category_dimension)} AS dimension",
        "COUNT(*) AS order_count",
    ]
    score_terms = ["COUNT(*) * 10"]
    order_terms = []
    if sales_metric:
        sales_expr = f"SUM(TRY_CAST({quote_identifier(sales_metric)} AS DOUBLE))"
        select_parts.append(f"{sales_expr} AS total_sales")
        select_parts.append(f"AVG(TRY_CAST({quote_identifier(sales_metric)} AS DOUBLE)) AS avg_sales")
        score_terms.append(f"COALESCE({sales_expr}, 0) * 0.1")
        order_terms.append("total_sales DESC")
    if profit_metric:
        profit_expr = f"SUM(TRY_CAST({quote_identifier(profit_metric)} AS DOUBLE))"
        select_parts.append(f"{profit_expr} AS total_profit")
        select_parts.append(f"AVG(TRY_CAST({quote_identifier(profit_metric)} AS DOUBLE)) AS avg_profit")
        score_terms.insert(0, f"COALESCE({profit_expr}, 0)")
        order_terms.insert(0, "total_profit DESC")
    if quantity_metric:
        quantity_expr = f"SUM(TRY_CAST({quote_identifier(quantity_metric)} AS DOUBLE))"
        select_parts.append(f"{quantity_expr} AS total_quantity")
        score_terms.append(f"COALESCE({quantity_expr}, 0) * 5")
        order_terms.append("total_quantity DESC")

    score_expr = " + ".join(score_terms)
    select_parts.append(f"({score_expr}) AS recommendation_score")
    where_clause = _build_where_clause([f"{category_dimension}=__NOT_NULL__", *(filters or [])])
    order_clause = ", ".join([*order_terms, "order_count DESC", "dimension ASC"])
    return (
        f"SELECT {', '.join(select_parts)} "
        f"FROM dataset "
        f"WHERE {where_clause} "
        f"GROUP BY {quote_identifier(category_dimension)} "
        f"ORDER BY {order_clause} "
        f"LIMIT {int(limit)}"
    )


def build_dataset_overview_sql(date_field: str | None = None) -> str:
    if date_field:
        quoted_date = quote_identifier(date_field)
        return (
            "SELECT "
            "COUNT(*) AS row_count, "
            f"MIN(TRY_CAST({quoted_date} AS TIMESTAMP)) AS min_date, "
            f"MAX(TRY_CAST({quoted_date} AS TIMESTAMP)) AS max_date "
            "FROM dataset"
        )
    return "SELECT COUNT(*) AS row_count FROM dataset"


def build_describe_sql(metric: str) -> str:
    quoted = quote_identifier(metric)
    return (
        "SELECT "
        f"COUNT({quoted}) AS non_null_count, "
        f"AVG({quoted}) AS mean, "
        f"MIN({quoted}) AS min, "
        f"MAX({quoted}) AS max, "
        f"STDDEV_SAMP({quoted}) AS std "
        "FROM dataset"
    )


def _first_matching_metric(metrics: list[str], keywords: list[str]) -> str | None:
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for metric in metrics:
            if keyword_lower in metric.lower():
                return metric
    return None


def _build_where_clause(filters: list[str]) -> str:
    clauses: list[str] = []
    for filter_expr in filters:
        if "=" not in filter_expr:
            continue
        column, value = filter_expr.split("=", 1)
        column = column.strip()
        value = value.strip()
        if not column or column.startswith("__"):
            continue
        if value == "__NOT_NULL__":
            clauses.append(f"{quote_identifier(column)} IS NOT NULL")
            continue
        value = value.strip("'\"")
        escaped_value = value.replace("'", "''")
        clauses.append(f"{quote_identifier(column)} = '{escaped_value}'")
    return " AND ".join(clauses)
