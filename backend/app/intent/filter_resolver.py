from __future__ import annotations

import re

from app.domain import DatasetProfile


def resolve_value_filters(question: str, profile: DatasetProfile) -> list[str]:
    """Resolve categorical filters from profiled values instead of hard-coded cities."""
    lowered = question.lower()
    mentioned_columns = {column for column in profile.categorical_columns if column.lower() in lowered}
    candidates: list[tuple[int, str, str]] = []
    for column in profile.columns:
        if column.name not in profile.categorical_columns and column.name not in profile.boolean_columns:
            continue
        for value in _known_values(column.sample_values, column.top_values):
            normalized = value.lower()
            if len(normalized) < 2 or len(normalized) > 80:
                continue
            if not _contains_value(lowered, normalized):
                continue
            score = len(normalized) + (100 if column.name in mentioned_columns else 0)
            candidates.append((score, column.name, value))

    filters: list[str] = []
    seen_columns: set[str] = set()
    for _, column, value in sorted(candidates, reverse=True):
        if column in seen_columns:
            continue
        filters.append(f"{column}={value}")
        seen_columns.add(column)
    return filters


def _known_values(sample_values: list[object], top_values: list[dict[str, object]]) -> list[str]:
    values = [*sample_values, *(item.get("value") for item in top_values)]
    distinct: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if raw is None:
            continue
        value = str(raw).strip()
        key = value.lower()
        if key and key not in seen:
            seen.add(key)
            distinct.append(value)
    return distinct


def _contains_value(question: str, value: str) -> bool:
    if re.fullmatch(r"[a-z0-9_.-]+", value):
        return re.search(rf"(?<![a-z0-9_]){re.escape(value)}(?![a-z0-9_])", question) is not None
    return value in question
