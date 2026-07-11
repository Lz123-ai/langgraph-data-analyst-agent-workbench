from __future__ import annotations

from typing import Any

from app.domain import ExecutionResult
from app.graph import nodes
from app.graph.state import AnalysisState


def generate_insights(state: AnalysisState) -> dict[str, Any]:
    result = ExecutionResult.model_validate(state["execution_result"])
    insights = nodes._derive_insights(result)
    return {
        "current_step": "generate_insights",
        "insights": [insight.model_dump(mode="json") for insight in insights],
        "messages": [
            *state.get("messages", []),
            {"role": "assistant", "content": f"已生成 {len(insights)} 条有证据支撑的洞察。"},
        ],
    }
