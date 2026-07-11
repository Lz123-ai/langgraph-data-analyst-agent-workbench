from __future__ import annotations

from typing import Any

from app.graph import nodes
from app.graph.state import AnalysisState


def generate_report(state: AnalysisState) -> dict[str, Any]:
    report = nodes._build_report(state)
    return {
        "current_step": "generate_report",
        "report_markdown": report,
        "messages": [
            *state.get("messages", []),
            {"role": "assistant", "content": "已生成 Markdown 分析报告。"},
        ],
    }
