from __future__ import annotations

from fastapi.testclient import TestClient

from app.improvements.defaults import DEFAULT_IMPROVEMENT_LOGS
from app.improvements.service import ImprovementLogService, improvement_log_service
from app.improvements.storage import ImprovementLogStorage
from app.main import app


def test_create_and_list_improvement_log() -> None:
    client = TestClient(app)
    payload = {
        "issue": "数据质量问题被误判为普通描述统计。",
        "resolution": "新增 data_quality 意图和 pandas 数据质量扫描，并加入回归测试。",
        "status": "resolved",
        "dataset_id": "dataset-for-test",
        "related_question": "数据质量有哪些明显问题？",
    }
    created_log_id = None

    try:
        create_response = client.post("/api/improvements", json=payload)

        assert create_response.status_code == 201
        created = create_response.json()
        created_log_id = created["log_id"]
        assert created["issue"] == payload["issue"]
        assert created["resolution"] == payload["resolution"]
        assert created["status"] == "resolved"
        assert created["dataset_id"] == "dataset-for-test"

        list_response = client.get("/api/improvements?limit=10")

        assert list_response.status_code == 200
        logs = list_response.json()["logs"]
        assert any(log["log_id"] == created["log_id"] for log in logs)
    finally:
        if created_log_id:
            improvement_log_service.delete_log(created_log_id)


def test_update_and_delete_improvement_log() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/improvements",
        json={
            "issue": "待更新的问题记录。",
            "resolution": "待更新的解决措施。",
            "status": "open",
        },
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["log_id"]

    patch_response = client.patch(
        f"/api/improvements/{log_id}",
        json={
            "status": "monitoring",
            "resolution": "已补充初步修复，继续观察回归结果。",
        },
    )
    assert patch_response.status_code == 200
    updated = patch_response.json()
    assert updated["status"] == "monitoring"
    assert updated["resolution"] == "已补充初步修复，继续观察回归结果。"

    delete_response = client.delete(f"/api/improvements/{log_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/improvements/{log_id}").status_code == 404


def test_seed_default_improvement_logs_is_idempotent(tmp_path) -> None:
    service = ImprovementLogService(ImprovementLogStorage(tmp_path / "improvements.sqlite"))

    first_synced = service.seed_default_logs()
    second_synced = service.seed_default_logs()

    logs = service.list_logs(limit=100)
    builtin_logs = [log for log in logs if log.log_id.startswith("builtin-")]

    assert first_synced == len(DEFAULT_IMPROVEMENT_LOGS)
    assert second_synced == 0
    assert len(builtin_logs) == len(DEFAULT_IMPROVEMENT_LOGS)
    assert any(log.log_id == "builtin-business-template-routing" for log in builtin_logs)
