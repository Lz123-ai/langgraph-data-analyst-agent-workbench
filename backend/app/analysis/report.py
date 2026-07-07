from __future__ import annotations

from app.graph.state import AnalysisState
from app.graph.nodes import generate_report


def build_report_from_state(state: AnalysisState) -> str:
    return generate_report(state)["report_markdown"]
