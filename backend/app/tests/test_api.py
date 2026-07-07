from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_upload_dataset_api_profiles_csv() -> None:
    client = TestClient(app)
    csv_bytes = b"category,sales\nA,10\nB,20\nB,30\n"

    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sample.csv", csv_bytes, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dataset"]["row_count"] == 3
    assert body["profile"]["numeric_columns"] == ["sales"]
    assert len(body["preview"]) == 3
