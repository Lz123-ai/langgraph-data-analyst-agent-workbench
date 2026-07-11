from __future__ import annotations

from typing import Any

from app.domain import DatasetProfile, QuestionUnderstanding
from app.graph import nodes
from app.graph.state import AnalysisState


def plan_analysis(state: AnalysisState) -> dict[str, Any]:
    profile = DatasetProfile.model_validate(state["profile"])
    understanding = QuestionUnderstanding.model_validate(state["question_understanding"])
    plan = nodes._build_plan(state["user_question"], profile, understanding)
    sub_questions = nodes._split_compound_questions(state["user_question"]) if len(plan.operations) > 1 else []
    return {
        "current_step": "plan_analysis",
        "analysis_plan": plan.model_dump(mode="json"),
        "sub_questions": sub_questions,
        "messages": [*state.get("messages", []), {"role": "assistant", "content": f"已规划 {len(plan.operations)} 个分析操作。"}],
    }
