from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


LogicalType = Literal["numeric", "categorical", "datetime", "boolean", "text", "unknown"]
ExecutionPath = Literal["duckdb_sql", "pandas", "clarification"]


class DatasetMetadata(BaseModel):
    dataset_id: str
    original_filename: str
    stored_filename: str
    file_path: str
    file_type: Literal["csv", "excel"]
    size_bytes: int
    row_count: int
    column_count: int
    columns: list[str]
    created_at: datetime


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    logical_type: LogicalType
    missing_count: int
    missing_rate: float
    unique_count: int
    sample_values: list[Any] = Field(default_factory=list)
    min: Any | None = None
    max: Any | None = None
    mean: float | None = None
    std: float | None = None
    q1: float | None = None
    q3: float | None = None
    outlier_count: int | None = None
    top_values: list[dict[str, Any]] = Field(default_factory=list)


class DataGrainProfile(BaseModel):
    grain_type: str
    grain_columns: list[str] = Field(default_factory=list)
    primary_key_candidates: list[list[str]] = Field(default_factory=list)
    time_field: str | None = None
    time_range: dict[str, Any] = Field(default_factory=dict)
    duplicate_key_count: int = 0
    notes: list[str] = Field(default_factory=list)


class DatasetProfile(BaseModel):
    dataset_id: str | None = None
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    numeric_columns: list[str]
    categorical_columns: list[str]
    datetime_columns: list[str]
    boolean_columns: list[str]
    grain: DataGrainProfile | None = None
    generated_at: datetime


class QuestionUnderstanding(BaseModel):
    objective: str
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    time_field: str | None = None
    target_columns: list[str] = Field(default_factory=list)
    analysis_goal: Literal[
        "group_aggregate",
        "count_by_dimension",
        "time_trend",
        "correlation",
        "distribution",
        "outlier",
        "top_records",
        "market_recommendation",
        "dataset_overview",
        "data_quality",
        "mrr_snapshot_vs_cumulative",
        "risk_customer_ranking",
        "business_template_analysis",
        "describe",
        "unanswerable",
        "clarification",
    ]
    confidence: float = Field(ge=0, le=1)
    needs_clarification: bool = False
    clarification_question: str | None = None


class AnalysisOperation(BaseModel):
    operation_type: Literal[
        "group_aggregate",
        "count_by_dimension",
        "time_trend",
        "correlation",
        "distribution",
        "outlier",
        "top_records",
        "market_recommendation",
        "dataset_overview",
        "data_quality",
        "mrr_snapshot_vs_cumulative",
        "risk_customer_ranking",
        "business_template_analysis",
        "describe",
        "unanswerable",
    ]
    path_hint: ExecutionPath
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    aggregation: Literal["sum", "avg", "count", "min", "max", "median"] | None = None
    template_id: str | None = None
    reason: str


class ChartRequest(BaseModel):
    chart_type: Literal["bar", "line", "scatter", "histogram", "table"]
    title: str
    x: str | None = None
    y: str | None = None
    reason: str


class AnalysisPlan(BaseModel):
    objective: str
    operations: list[AnalysisOperation]
    chart_requests: list[ChartRequest]
    safety_notes: list[str] = Field(default_factory=list)


class ExecutionTable(BaseModel):
    name: str
    columns: list[str]
    rows: list[dict[str, Any]]


class ExecutionResult(BaseModel):
    kind: str
    source: Literal["duckdb", "pandas"]
    tables: list[ExecutionTable] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    method: str


class ChartArtifact(BaseModel):
    chart_id: str
    title: str
    chart_type: str
    echarts_option: dict[str, Any]
    evidence_table: str | None = None


class Insight(BaseModel):
    text: str
    evidence: str
    confidence: Literal["high", "medium", "low"] = "medium"


class ReviewNote(BaseModel):
    severity: Literal["info", "warning", "error"]
    note: str
    evidence: str | None = None
