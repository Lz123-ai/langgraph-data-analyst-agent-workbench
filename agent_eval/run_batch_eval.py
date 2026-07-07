from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.graph.workflow import build_analysis_workflow  # noqa: E402
from app.ops.service import agent_ops_service  # noqa: E402
from app.settings import settings  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run batch natural-language Agent evaluation cases.")
    parser.add_argument("--cases", default="agent_eval/cases.json", help="Path to evaluation cases JSON.")
    parser.add_argument("--output", default=None, help="Optional JSON result path.")
    args = parser.parse_args()

    cases_path = (ROOT / args.cases).resolve()
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    settings.ensure_directories()
    app = build_analysis_workflow()

    results = []
    for case in cases:
        result = run_case(app, case)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {case['id']} -> kind={result.get('actual_kind')} path={result.get('actual_path')}")
        if result["failures"]:
            for failure in result["failures"]:
                print(f"  - {failure}")

    passed = sum(1 for result in results if result["passed"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases_path": str(cases_path),
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        },
        "results": results,
    }

    output_path = Path(args.output) if args.output else ROOT / "agent_eval" / "results" / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        agent_ops_service.record_eval_report(report, source_path=str(output_path))
    except Exception as exc:  # noqa: BLE001 - eval output should not fail because observability persistence failed.
        print(f"AgentOps persistence warning: {exc}")

    print("")
    print(f"Summary: {passed}/{len(results)} passed")
    print(f"Result JSON: {output_path}")
    return 0 if passed == len(results) else 1


def run_case(app: Any, case: dict[str, Any]) -> dict[str, Any]:
    dataset_path = prepare_dataset(case["dataset_path"], case["id"])
    failures: list[str] = []
    state: dict[str, Any] = {}
    try:
        state = app.invoke(
            {
                "dataset_id": f"agent-eval-{case['id']}",
                "file_path": str(dataset_path),
                "user_question": case["question"],
                "profile": None,
                "messages": [],
                "analysis_plan": None,
                "execution_path": None,
                "sql_queries": [],
                "generated_code": [],
                "execution_result": None,
                "charts": [],
                "insights": [],
                "review_notes": [],
                "report_markdown": None,
                "errors": [],
                "needs_clarification": False,
                "current_step": "queued",
                "dataset_preview": [],
            }
        )
    except Exception as exc:  # noqa: BLE001 - evaluation should report every failure as data.
        return {
            "id": case["id"],
            "question": case["question"],
            "passed": False,
            "failures": [f"workflow raised {type(exc).__name__}: {exc}"],
        }

    execution_result = state.get("execution_result") or {}
    tables = execution_result.get("tables") or []
    rows = tables[0].get("rows", []) if tables else []
    report_markdown = state.get("report_markdown") or ""

    actual_kind = execution_result.get("kind")
    actual_path = state.get("execution_path")
    if actual_kind != case.get("expected_kind"):
        failures.append(f"expected kind={case.get('expected_kind')}, got {actual_kind}")
    if actual_path != case.get("expected_path"):
        failures.append(f"expected path={case.get('expected_path')}, got {actual_path}")

    if "first_row_contains" in case:
        if not rows:
            failures.append("expected first result row, got empty result table")
        else:
            failures.extend(compare_mapping("first row", rows[0], case["first_row_contains"]))

    if "any_row_contains" in case:
        expected = case["any_row_contains"]
        if not any(mapping_contains(row, expected) for row in rows):
            failures.append(f"expected any row containing {expected}, got first rows {rows[:5]}")

    if "metrics_contains" in case:
        failures.extend(compare_mapping("metrics", execution_result.get("metrics") or {}, case["metrics_contains"]))

    for keyword in case.get("report_keywords", []):
        if keyword not in report_markdown:
            failures.append(f"report missing keyword: {keyword}")

    return {
        "id": case["id"],
        "question": case["question"],
        "passed": not failures,
        "failures": failures,
        "actual_kind": actual_kind,
        "actual_path": actual_path,
        "table_names": [table.get("name") for table in tables],
        "first_rows": rows[:3],
        "metrics": execution_result.get("metrics") or {},
        "errors": state.get("errors") or [],
    }


def prepare_dataset(relative_path: str, case_id: str) -> Path:
    source = (ROOT / relative_path).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    target = settings.upload_dir / f"agent_eval_{case_id}{source.suffix.lower()}"
    shutil.copy2(source, target)
    return target.resolve()


def compare_mapping(label: str, actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures = []
    for key, expected_value in expected.items():
        if key not in actual:
            failures.append(f"{label} missing key {key!r}")
            continue
        actual_value = actual[key]
        if not values_equal(actual_value, expected_value):
            failures.append(f"{label}[{key!r}] expected {expected_value!r}, got {actual_value!r}")
    return failures


def mapping_contains(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(key in actual and values_equal(actual[key], expected_value) for key, expected_value in expected.items())


def values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(float(actual) - float(expected)) < 1e-6
    return actual == expected


if __name__ == "__main__":
    raise SystemExit(main())
