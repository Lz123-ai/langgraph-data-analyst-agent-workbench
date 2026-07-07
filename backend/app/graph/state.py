from __future__ import annotations

from typing import Any, TypedDict


class AnalysisState(TypedDict, total=False):
    dataset_id: str
    file_path: str
    user_question: str
    profile: dict[str, Any] | None
    messages: list[dict[str, str]]
    analysis_plan: dict[str, Any] | None
    execution_path: str | None
    sql_queries: list[str]
    generated_code: list[str]
    execution_result: dict[str, Any] | None
    charts: list[dict[str, Any]]
    insights: list[dict[str, Any]]
    review_notes: list[dict[str, Any]]
    report_markdown: str | None
    errors: list[str]
    needs_clarification: bool
    current_step: str
    question_understanding: dict[str, Any] | None
    dataset_preview: list[dict[str, Any]]
    sub_questions: list[str]
