from fastapi.testclient import TestClient

from rtbdi_assistant.api import create_app


def test_api_health():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "browser": "playwright-chromium"}
