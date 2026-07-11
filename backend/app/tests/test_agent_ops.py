from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.ops.models import IdentityContext
from app.ops.service import AgentOpsService
from app.ops.storage import AgentOpsStorage


def test_agent_ops_service_records_task_trace_tokens_and_eval(tmp_path) -> None:
    service = AgentOpsService(AgentOpsStorage(tmp_path / "ops.sqlite"))
    task = service.create_task(
        task_id="task-for-ops-test",
        dataset_id="dataset-for-ops-test",
        question="测试 AgentOps 记录。",
        identity=IdentityContext(tenant_id="tenant-a", user_id="user-a"),
        token_budget=1000,
    )

    service.mark_running(task.task_id)
    started_at = datetime.now(timezone.utc)
    service.record_trace_span(
        task_id=task.task_id,
        name="understand_question",
        span_type="node",
        status="succeeded",
        started_at=started_at,
        ended_at=started_at,
        duration_ms=0,
        output_summary="识别为数据概览。",
    )
    service.record_node_payload_metric(
        task_id=task.task_id,
        node="understand_question",
        input_summary="这个数据集有多少行？",
        output_payload={"analysis_goal": "dataset_overview"},
    )
    service.record_token_usage(
        task_id=task.task_id,
        node="understand_question",
        model_name="test-model",
        prompt_version="test-v1",
        prompt_tokens=10,
        completion_tokens=5,
        source="provider",
    )
    service.complete_task(task.task_id, {"execution_result": {"kind": "dataset_overview"}})
    service.record_eval_report(
        {
            "summary": {"total": 1, "passed": 1, "failed": 0},
            "results": [{"id": "case-1", "passed": True}],
        },
        source_path="agent_eval/results/test.json",
    )

    detail_task, trace, usage = service.get_task_detail(task.task_id)
    summary = service.summary()
    eval_runs = service.list_eval_runs()

    assert detail_task.status == "succeeded"
    assert detail_task.tenant_id == "tenant-a"
    assert trace[0].name == "understand_question"
    assert usage[0].total_tokens > 0
    assert summary.task_count == 1
    assert summary.total_tokens == usage[0].total_tokens
    assert summary.deterministic_payload_bytes > 0
    assert eval_runs[0].passed == 1


def test_agent_ops_summary_api() -> None:
    client = TestClient(app)
    response = client.get("/api/ops/summary")

    assert response.status_code == 200
    body = response.json()
    assert "task_count" in body
    assert "total_tokens" in body
