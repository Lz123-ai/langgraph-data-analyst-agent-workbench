from __future__ import annotations

from app.graph.report import generate_report
from app.graph.state import AnalysisState


def build_report_from_state(state: AnalysisState) -> str:
    return generate_report(state)["report_markdown"]
