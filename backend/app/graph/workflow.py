from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph import insight, nodes, planner, report, review
from app.graph.state import AnalysisState


def build_analysis_workflow():
    graph = StateGraph(AnalysisState)
    graph.add_node("load_dataset", nodes.load_dataset)
    graph.add_node("profile_dataset", nodes.profile_dataset)
    graph.add_node("understand_question", nodes.understand_question)
    graph.add_node("plan_analysis", planner.plan_analysis)
    graph.add_node("choose_execution_path", nodes.choose_execution_path)
    graph.add_node("run_sql_analysis", nodes.run_sql_analysis)
    graph.add_node("run_pandas_analysis", nodes.run_pandas_analysis)
    graph.add_node("generate_charts", nodes.generate_charts)
    graph.add_node("generate_insights", insight.generate_insights)
    graph.add_node("review_answer", review.review_answer)
    graph.add_node("generate_report", report.generate_report)

    graph.add_edge(START, "load_dataset")
    graph.add_edge("load_dataset", "profile_dataset")
    graph.add_edge("profile_dataset", "understand_question")
    graph.add_edge("understand_question", "plan_analysis")
    graph.add_edge("plan_analysis", "choose_execution_path")
    graph.add_conditional_edges(
        "choose_execution_path",
        _route_after_path_selection,
        {
            "duckdb_sql": "run_sql_analysis",
            "pandas": "run_pandas_analysis",
            "clarification": "generate_report",
        },
    )
    graph.add_edge("run_sql_analysis", "generate_charts")
    graph.add_edge("run_pandas_analysis", "generate_charts")
    graph.add_edge("generate_charts", "generate_insights")
    graph.add_edge("generate_insights", "review_answer")
    graph.add_edge("review_answer", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()


def _route_after_path_selection(state: AnalysisState) -> str:
    if state.get("needs_clarification"):
        return "clarification"
    execution_path = state.get("execution_path")
    if execution_path == "duckdb_sql":
        return "duckdb_sql"
    if execution_path == "pandas":
        return "pandas"
    return "clarification"
