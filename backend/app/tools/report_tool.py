from __future__ import annotations

from typing import Any


def markdown_table(rows: list[dict[str, Any]], columns: list[str], max_rows: int = 10) -> str:
    if not rows or not columns:
        return "_没有返回数据行。_"
    head = rows[:max_rows]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in head:
        body.append("| " + " | ".join(_format_cell(row.get(column)) for column in columns) + " |")
    suffix = f"\n\n_显示 {len(head)} / {len(rows)} 行。_" if len(rows) > len(head) else ""
    return "\n".join([header, separator, *body]) + suffix


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value).replace("|", "\\|").replace("\n", " ")
