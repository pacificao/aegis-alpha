from fastapi.testclient import TestClient

from app.auth import Principal, csrf_protected, current_principal
from app.main import app


principal = Principal(username="nathan", session_id="test", csrf_token="csrf")


def test_health_is_public_and_trading_disabled():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["trading"] == "DISABLED"


def test_protected_api_rejects_unauthorized_access():
    with TestClient(app) as client:
        assert client.get("/api/roadmap").status_code == 401
        assert client.get("/api/status").status_code == 401


def test_roadmap_contains_all_phases_and_persists_update():
    app.dependency_overrides[current_principal] = lambda: principal
    app.dependency_overrides[csrf_protected] = lambda: principal
    try:
        with TestClient(app) as client:
            roadmap = client.get("/api/roadmap")
            assert roadmap.status_code == 200
            phases = roadmap.json()
            assert len(phases) == 12
            assert len(phases[0]["tasks"]) == 69
            task_id = phases[0]["tasks"][0]["id"]
            changed = client.patch(f"/api/tasks/{task_id}", json={"status": "IN_PROGRESS", "notes": "Verified persistence"}, headers={"X-CSRF-Token": "csrf"})
            assert changed.status_code == 200
            assert changed.json()["notes"] == "Verified persistence"
        with TestClient(app) as second_client:
            phases = second_client.get("/api/roadmap").json()
            assert phases[0]["tasks"][0]["status"] == "IN_PROGRESS"
    finally:
        app.dependency_overrides.clear()


def test_broker_is_placeholder_only():
    app.dependency_overrides[current_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            data = client.get("/api/broker/status").json()
            assert data["status"] == "DISCONNECTED"
            assert "Future integration" in data["detail"]
    finally:
        app.dependency_overrides.clear()

