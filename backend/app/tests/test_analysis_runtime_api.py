from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import app
from app.runtime.task_store import task_store


def test_analysis_task_completes_with_replayable_events() -> None:
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/datasets/upload",
            files={
                "file": (
                    "runtime-analysis.csv",
                    b"region,sales,profit\nEast,10,2\nWest,20,3\nEast,30,8\n",
                    "text/csv",
                )
            },
        )
        assert uploaded.status_code == 200
        dataset_id = uploaded.json()["dataset"]["dataset_id"]

        created = client.post(
            "/api/analysis/tasks",
            json={"dataset_id": dataset_id, "question": "Average sales by region"},
        )
        assert created.status_code == 200
        task_id = created.json()["task_id"]

        body = None
        for _ in range(100):
            response = client.get(f"/api/analysis/tasks/{task_id}")
            body = response.json()
            if body["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)

        assert body and body["status"] == "succeeded"
        assert body["final_state"]["execution_result"]["kind"] == "group_aggregate"
        events_one = task_store.list_events(task_id)
        events_two = task_store.list_events(task_id)
        assert [event.event_id for event in events_one] == [event.event_id for event in events_two]
        assert events_one[-1].event_type == "task_completed"
        assert all(event.sequence_id for event in events_one)

        assert client.delete(f"/api/datasets/{dataset_id}").status_code == 204
