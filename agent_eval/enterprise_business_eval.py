from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.graph.workflow import build_analysis_workflow  # noqa: E402
from app.settings import settings  # noqa: E402


DATASET_NAME = "enterprise_agent_eval_dataset_20260703_221458"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run enterprise business Agent evaluation cases.")
    parser.add_argument("--data-dir", default=None, help="Directory containing enterprise CSV files and benchmarks.json.")
    parser.add_argument("--output", default=None, help="Optional JSON result path.")
    args = parser.parse_args()

    data_dir = _resolve_data_dir(args.data_dir)
    benchmarks = json.loads((data_dir / "benchmarks.json").read_text(encoding="utf-8"))
    settings.ensure_directories()
    uploaded = _copy_eval_files(data_dir)

    cases = _cases(uploaded, benchmarks)
    app = build_analysis_workflow()
    results = [run_case(app, case) for case in cases]
    passed = sum(1 for result in results if result["passed"])
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {result['id']} -> kind={result.get('actual_kind')} path={result.get('actual_path')}")
        for failure in result["failures"]:
            print(f"  - {failure}")

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_dir": str(data_dir),
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
        "results": results,
    }
    output_path = Path(args.output) if args.output else ROOT / "agent_eval" / "results" / f"enterprise_business_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Summary: {passed}/{len(results)} passed")
    print(f"Result JSON: {output_path}")
    return 0 if passed == len(results) else 1


def _resolve_data_dir(data_dir: str | None) -> Path:
    if data_dir:
        resolved = Path(data_dir).resolve()
        if (resolved / "benchmarks.json").exists():
            return resolved
        nested = resolved / DATASET_NAME
        if (nested / "benchmarks.json").exists():
            return nested.resolve()
        raise FileNotFoundError(f"benchmarks.json not found under {resolved}")

    candidates = [
        ROOT / "external_eval_data" / DATASET_NAME,
        ROOT / ".run" / "enterprise_eval_dataset" / DATASET_NAME,
    ]
    for candidate in candidates:
        if (candidate / "benchmarks.json").exists():
            return candidate.resolve()

    zip_path = ROOT / "external_eval_data" / f"{DATASET_NAME}.zip"
    if zip_path.exists():
        target = ROOT / ".run" / "enterprise_eval_dataset"
        target.mkdir(parents=True, exist_ok=True)
        with ZipFile(zip_path) as zf:
            zf.extractall(target)
        extracted = target / DATASET_NAME
        if (extracted / "benchmarks.json").exists():
            return extracted.resolve()

    raise FileNotFoundError(
        "Enterprise eval dataset not found. Pass --data-dir or place the dataset under external_eval_data/."
    )


def _copy_eval_files(data_dir: Path) -> dict[str, Path]:
    uploaded = {}
    for name in ["customer_month_wide.csv", "invoices.csv", "sales_opportunities.csv"]:
        target = settings.upload_dir / f"enterprise_{name}"
        shutil.copy2(data_dir / name, target)
        uploaded[name] = target
    return uploaded


def _cases(uploaded: dict[str, Path], b: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "enterprise_mrr_scope",
            "file": uploaded["customer_month_wide.csv"],
            "question": "当前 MRR 与客户-月份累计 MRR 分别是多少？为什么不能混用？",
            "expected_kind": "mrr_snapshot_vs_cumulative",
            "expected_path": "pandas",
            "expected_strings": ["当前 MRR", "累计 MRR", "客户-月份"],
            "expected_numbers": [b["current_mrr_latest_month"], b["cumulative_customer_month_mrr"]],
            "expected_metrics_near": {
                "current_mrr": b["current_mrr_latest_month"],
                "cumulative_mrr": b["cumulative_customer_month_mrr"],
            },
            "expected_metrics_equal": {"latest_period": "2025-12"},
        },
        {
            "id": "enterprise_high_risk_latest",
            "file": uploaded["customer_month_wide.csv"],
            "question": "2025年12月高续约风险客户有多少？对应 MRR 是多少？列出 MRR 最高的 20 个高风险客户。",
            "expected_kind": "risk_customer_ranking",
            "expected_path": "pandas",
            "expected_strings": ["高风险", "MRR"],
            "expected_numbers": [b["high_risk_customers_latest"], b["high_risk_mrr_latest"]],
            "expected_metrics_near": {
                "high_risk_customer_count": b["high_risk_customers_latest"],
                "high_risk_mrr": b["high_risk_mrr_latest"],
            },
        },
        {
            "id": "enterprise_customer_success_priority",
            "file": uploaded["customer_month_wide.csv"],
            "question": "按客户经理比较客户数、MRR、高风险客户数和高风险MRR，谁最需要优先处理？",
            "expected_kind": "business_template_analysis",
            "expected_template_id": "customer_success_priority",
            "expected_path": "pandas",
            "expected_strings": [b["top_customer_success_manager_by_high_risk_mrr"]["manager"], "高风险MRR"],
            "expected_numbers": [
                b["top_customer_success_manager_by_high_risk_mrr"]["high_risk_mrr"],
                b["top_customer_success_manager_by_high_risk_mrr"]["high_risk_customers"],
            ],
        },
        {
            "id": "enterprise_expansion_contraction",
            "file": uploaded["customer_month_wide.csv"],
            "question": "比较 2025 年 1 月和 12 月每个客户 MRR，输出扩张客户、收缩客户、净变化、Top 扩张和 Top 收缩客户。",
            "expected_kind": "business_template_analysis",
            "expected_template_id": "expansion_contraction",
            "expected_path": "pandas",
            "expected_strings": [
                b["expansion_contraction"]["top_expansion_customer"],
                b["expansion_contraction"]["top_contraction_customer"],
                "扩张",
                "收缩",
            ],
            "expected_numbers": [
                b["expansion_contraction"]["total_expansion"],
                b["expansion_contraction"]["total_contraction"],
                b["expansion_contraction"]["net_change"],
            ],
        },
        {
            "id": "enterprise_health_signal",
            "file": uploaded["customer_month_wide.csv"],
            "question": "产品使用时长、活跃用户、工单数量、SLA 超时、NPS、CSAT 与续约风险有什么关系？",
            "expected_kind": "business_template_analysis",
            "expected_template_id": "health_signal_analysis",
            "expected_path": "pandas",
            "expected_strings": ["NPS", "CSAT", "续约风险"],
            "expected_numbers": [
                b["health_correlations"]["usage_vs_mrr"],
                b["health_correlations"]["tickets_vs_risk"],
                b["health_correlations"]["nps_vs_risk"],
                b["health_correlations"]["csat_vs_nps"],
            ],
        },
        {
            "id": "enterprise_data_quality",
            "file": uploaded["customer_month_wide.csv"],
            "question": "数据质量有哪些问题？请独立检查缺失渠道、NPS/CSAT缺失、重复客户月份、负MRR、未来月份、异常折扣。",
            "expected_kind": "data_quality",
            "expected_path": "pandas",
            "expected_strings": ["缺失", "重复", "NPS", "CSAT"],
            "expected_numbers": [
                b["data_quality"]["missing_channel_rows"],
                b["data_quality"]["missing_nps_rows"],
                b["data_quality"]["missing_csat_rows"],
                b["data_quality"]["duplicate_customer_month_rows"],
                b["data_quality"]["negative_mrr_rows"],
            ],
        },
        {
            "id": "enterprise_invoice_risk",
            "file": uploaded["invoices.csv"],
            "question": "逾期或支付失败发票造成多少应收风险？逾期45天以上金额是多少？列出催收优先级。",
            "expected_path": "pandas",
            "expected_strings": ["逾期", "失败", "催收"],
            "expected_numbers": [
                b["payment_risk"]["problem_invoice_count"],
                b["payment_risk"]["problem_ar_amount"],
                b["payment_risk"]["overdue_45plus_amount"],
            ],
        },
        {
            "id": "enterprise_pipeline",
            "file": uploaded["sales_opportunities.csv"],
            "question": "当前总 Pipeline、加权 Pipeline、赢单金额是多少？按销售负责人排序。",
            "expected_path": "pandas",
            "expected_strings": ["Pipeline", "销售负责人"],
            "expected_numbers": [
                b["pipeline"]["total_pipeline_amount"],
                b["pipeline"]["weighted_pipeline"],
                b["pipeline"]["win_amount"],
            ],
        },
    ]


def run_case(app: Any, case: dict[str, Any]) -> dict[str, Any]:
    try:
        state = app.invoke(
            {
                "dataset_id": f"enterprise-{case['id']}",
                "file_path": str(case["file"].resolve()),
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
    except Exception as exc:  # noqa: BLE001
        return {
            "id": case["id"],
            "question": case["question"],
            "passed": False,
            "failures": [f"workflow raised {type(exc).__name__}: {exc}"],
            "actual_kind": None,
            "actual_path": None,
            "metrics": {},
            "table_names": [],
            "first_rows": [],
            "errors": [str(exc)],
            "report_excerpt": "",
        }
    execution_result = state.get("execution_result") or {}
    tables = execution_result.get("tables") or []
    report_markdown = state.get("report_markdown") or ""
    serialized = json.dumps(execution_result, ensure_ascii=False) + "\n" + report_markdown

    failures: list[str] = []
    expected_kind = case.get("expected_kind")
    actual_kind = execution_result.get("kind")
    actual_path = state.get("execution_path")
    if expected_kind and actual_kind != expected_kind:
        failures.append(f"expected kind={expected_kind}, got {actual_kind}")
    if actual_path != case["expected_path"]:
        failures.append(f"expected path={case['expected_path']}, got {actual_path}")
    expected_template_id = case.get("expected_template_id")
    if expected_template_id:
        template_id = (execution_result.get("metrics") or {}).get("template_id")
        if template_id != expected_template_id:
            failures.append(f"expected template_id={expected_template_id}, got {template_id}")
    for text in case.get("expected_strings", []):
        if text not in serialized:
            failures.append(f"missing expected text: {text}")
    for number in case.get("expected_numbers", []):
        if not _number_present(serialized, float(number)):
            failures.append(f"missing expected number near: {number}")
    metrics = execution_result.get("metrics") or {}
    for key, expected in (case.get("expected_metrics_near") or {}).items():
        actual = metrics.get(key)
        if actual is None or abs(float(actual) - float(expected)) > max(0.05, abs(float(expected)) * 0.001):
            failures.append(f"metrics[{key}] expected near {expected}, got {actual}")
    for key, expected in (case.get("expected_metrics_equal") or {}).items():
        actual = metrics.get(key)
        if actual != expected:
            failures.append(f"metrics[{key}] expected {expected!r}, got {actual!r}")

    first_rows = []
    for table in tables[:3]:
        first_rows.append({"name": table.get("name"), "rows": (table.get("rows") or [])[:3]})

    return {
        "id": case["id"],
        "question": case["question"],
        "passed": not failures,
        "failures": failures,
        "actual_kind": actual_kind,
        "actual_path": actual_path,
        "metrics": execution_result.get("metrics") or {},
        "table_names": [table.get("name") for table in tables],
        "first_rows": first_rows,
        "errors": state.get("errors") or [],
        "report_excerpt": report_markdown[:1600],
    }


def _number_present(text: str, expected: float) -> bool:
    import re

    numbers = []
    for match in re.finditer(r"-?\d+(?:,\d{3})*(?:\.\d+)?(?:e[+-]?\d+)?", text, flags=re.IGNORECASE):
        token = match.group(0).replace(",", "")
        try:
            numbers.append(float(token))
        except ValueError:
            continue
    tolerance = max(0.05, abs(expected) * 0.001)
    return any(abs(value - expected) <= tolerance for value in numbers)


if __name__ == "__main__":
    raise SystemExit(main())
