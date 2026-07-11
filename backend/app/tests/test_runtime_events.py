from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.analysis.service import AnalysisService
from app.ops.models import IdentityContext
from app.ops.service import AgentOpsService
from app.ops.storage import AgentOpsStorage
from app.runtime.events import TaskEvent
from app.runtime.sse import event_stream, format_sse
from app.runtime.task_store import TaskStore


def test_persisted_events_support_multiple_readers_and_replay(tmp_path) -> None:
    async def scenario() -> None:
        store = TaskStore(tmp_path / "runtime.sqlite")
        task = store.create("dataset-1", "question")
        started = await store.publish(
            TaskEvent(task_id=task.task_id, event_type="task_started", status="running", message="started")
        )
        completed = await store.publish(
            TaskEvent(task_id=task.task_id, event_type="task_completed", status="succeeded", message="done")
        )
        store.set_final_state(task.task_id, {"ok": True})

        reader_one = store.list_events(task.task_id)
        reader_two = store.list_events(task.task_id)
        assert [event.event_id for event in reader_one] == [event.event_id for event in reader_two]
        assert started.sequence_id and completed.sequence_id
        assert f"id: {started.sequence_id}" in format_sse(started)

        replayed = []
        async for message in event_stream(store, task.task_id, after_sequence=started.sequence_id):
            replayed.append(message)
        assert len(replayed) == 1
        assert "task_completed" in replayed[0]

    asyncio.run(scenario())


def test_runtime_cancel_request_is_persisted(tmp_path) -> None:
    store = TaskStore(tmp_path / "runtime.sqlite")
    task = store.create("dataset-1", "question")
    store.request_cancel(task.task_id)
    assert store.is_cancel_requested(task.task_id)


def test_analysis_service_cancels_active_background_task(tmp_path) -> None:
    class FakeDatasets:
        def get_dataset(self, dataset_id: str, identity=None):
            return SimpleNamespace(file_path="unused.csv"), None

    class SlowWorkflow:
        async def astream(self, initial_state, stream_mode):
            await asyncio.sleep(30)
            if False:
                yield initial_state, stream_mode

    async def scenario() -> None:
        store = TaskStore(tmp_path / "runtime.sqlite")
        ops = AgentOpsService(AgentOpsStorage(tmp_path / "ops.sqlite"))
        service = AnalysisService(FakeDatasets(), store, ops)  # type: ignore[arg-type]
        service.workflow = SlowWorkflow()
        task_id = service.create_task("dataset", "question", IdentityContext())
        await asyncio.sleep(0.05)
        response = service.cancel_task(task_id)
        assert response["status"] in {"cancelling", "cancelled"}
        for _ in range(100):
            if store.get(task_id).status == "cancelled":
                break
            await asyncio.sleep(0.01)
        assert store.get(task_id).status == "cancelled"
        assert ops.require_task(task_id).status == "cancelled"
        assert store.list_events(task_id)[-1].event_type == "task_cancelled"

    asyncio.run(scenario())


def test_interrupted_task_is_automatically_rerun_after_restart(tmp_path) -> None:
    class FakeDatasets:
        def get_dataset(self, dataset_id: str, identity=None):
            return SimpleNamespace(file_path="unused.csv"), None

    class CompletedWorkflow:
        async def astream(self, initial_state, stream_mode):
            yield {"resume_node": {"current_step": "generate_report", "report_markdown": "resumed"}}

    async def scenario() -> None:
        store = TaskStore(tmp_path / "runtime.sqlite")
        ops = AgentOpsService(AgentOpsStorage(tmp_path / "ops.sqlite"))
        runtime_task = store.create("dataset", "question")
        ops.create_task(
            task_id=runtime_task.task_id,
            dataset_id="dataset",
            question="question",
            identity=IdentityContext(),
        )
        await store.publish(
            TaskEvent(
                task_id=runtime_task.task_id,
                event_type="task_started",
                status="running",
                message="started before restart",
            )
        )
        ops.mark_running(runtime_task.task_id)

        restarted = AnalysisService(FakeDatasets(), store, ops)  # type: ignore[arg-type]
        restarted.workflow = CompletedWorkflow()
        assert restarted.resume_incomplete() == 1
        for _ in range(100):
            if store.get(runtime_task.task_id).status == "succeeded":
                break
            await asyncio.sleep(0.01)

        assert store.get(runtime_task.task_id).status == "succeeded"
        assert ops.require_task(runtime_task.task_id).status == "succeeded"
        event_types = [event.event_type for event in store.list_events(runtime_task.task_id)]
        assert "task_resumed" in event_types
        assert event_types[-1] == "task_completed"

    asyncio.run(scenario())


def test_failed_task_can_be_explicitly_retried_with_same_task_id(tmp_path) -> None:
    class FakeDatasets:
        def get_dataset(self, dataset_id: str, identity=None):
            return SimpleNamespace(file_path="unused.csv"), None

    class CompletedWorkflow:
        async def astream(self, initial_state, stream_mode):
            yield {"retry_node": {"current_step": "generate_report", "report_markdown": "retried"}}

    async def scenario() -> None:
        store = TaskStore(tmp_path / "runtime.sqlite")
        ops = AgentOpsService(AgentOpsStorage(tmp_path / "ops.sqlite"))
        service = AnalysisService(FakeDatasets(), store, ops)  # type: ignore[arg-type]
        service.workflow = CompletedWorkflow()
        runtime_task = store.create("dataset", "question")
        task_id = runtime_task.task_id
        ops.create_task(
            task_id=task_id,
            dataset_id="dataset",
            question="question",
            identity=IdentityContext(),
        )
        store.set_error(task_id, "transient failure")
        ops.fail_task(task_id, "transient failure")

        response = service.retry_task(task_id, IdentityContext())
        assert response == {"task_id": task_id, "status": "queued"}
        for _ in range(100):
            if store.get(task_id).status == "succeeded":
                break
            await asyncio.sleep(0.01)
        assert store.get(task_id).status == "succeeded"
        assert ops.require_task(task_id).status == "succeeded"
        assert "task_retried" in [event.event_type for event in store.list_events(task_id)]

    asyncio.run(scenario())
