from uuid import uuid4
from fastapi.testclient import TestClient
import pytest

from app.auth import Principal, csrf_protected, current_principal
from app.main import app
from app.gateway import BrokerGatewayClient


@pytest.fixture(autouse=True)
def broker_gateway_stub(monkeypatch):
    monkeypatch.setattr(BrokerGatewayClient, "status", lambda self: {"status": "NOT_CONFIGURED", "detail": "authorization has not been completed", "mode": "READ_ONLY", "trading": "DISABLED"})

principal = Principal(username="test-operator", session_id="test", csrf_token="csrf")


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


def test_broker_reports_not_configured_without_authorization():
    app.dependency_overrides[current_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            data = client.get("/api/broker/status").json()
            assert data["status"] == "NOT_CONFIGURED"
            assert "authorization has not been completed" in data["detail"]
    finally:
        app.dependency_overrides.clear()



def test_robinhood_mcp_config_is_persisted_and_rejects_secrets():
    app.dependency_overrides[current_principal] = lambda: principal
    app.dependency_overrides[csrf_protected] = lambda: principal
    try:
        with TestClient(app) as client:
            initial = client.get("/api/broker/robinhood/config")
            assert initial.status_code == 200
            assert initial.json()["endpoint"] == "https://agent.robinhood.com/mcp/trading"
            assert initial.json()["mode"] == "READ_ONLY"
            assert initial.json()["status"] == "NOT_CONFIGURED"

            changed = client.patch(
                "/api/broker/robinhood/config",
                json={"connection_name": "Test Robinhood Agentic", "endpoint": "https://agent.robinhood.com/mcp/trading"},
                headers={"X-CSRF-Token": "csrf"},
            )
            assert changed.status_code == 200
            assert changed.json()["connection_name"] == "Test Robinhood Agentic"

            secret_attempt = client.patch(
                "/api/broker/robinhood/config",
                json={"connection_name": "Unsafe", "endpoint": "https://agent.robinhood.com/mcp/trading", "token": "must-not-be-accepted"},
                headers={"X-CSRF-Token": "csrf"},
            )
            assert secret_attempt.status_code == 422

            arbitrary_endpoint = client.patch(
                "/api/broker/robinhood/config",
                json={"connection_name": "Unsafe", "endpoint": "https://example.com/mcp"},
                headers={"X-CSRF-Token": "csrf"},
            )
            assert arbitrary_endpoint.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_robinhood_browser_authorization_and_disconnect_are_csrf_protected(monkeypatch):
    monkeypatch.setattr(BrokerGatewayClient, "start_authorization", lambda self: {"status": "AUTHORIZING", "authorization_url": "https://robinhood.example/authorize"})
    monkeypatch.setattr(BrokerGatewayClient, "disconnect", lambda self: {"status": "NOT_CONFIGURED", "trading": "DISABLED", "mode": "READ_ONLY"})
    app.dependency_overrides[current_principal] = lambda: principal
    app.dependency_overrides[csrf_protected] = lambda: principal
    try:
        with TestClient(app) as client:
            started = client.post("/api/broker/robinhood/connect", headers={"X-CSRF-Token": "csrf"})
            assert started.status_code == 200
            assert started.json()["status"] == "AUTHORIZING"
            removed = client.post("/api/broker/robinhood/disconnect", headers={"X-CSRF-Token": "csrf"})
            assert removed.status_code == 200
            assert removed.json()["trading"] == "DISABLED"
    finally:
        app.dependency_overrides.clear()


def test_phase2_console_boundaries_and_persistence():
    app.dependency_overrides[current_principal] = lambda: principal
    app.dependency_overrides[csrf_protected] = lambda: principal
    try:
        with TestClient(app) as client:
            scenario_name = f"Test Research {uuid4().hex[:8]}"
            portfolio = client.get("/api/portfolio")
            assert portfolio.status_code == 200
            assert portfolio.json()["holdings_available"] is False
            assert portfolio.json()["trading"] == "DISABLED"

            scenarios = client.get("/api/scenarios")
            assert scenarios.status_code == 200
            dividend = next(item for item in scenarios.json() if item["name"] == "Dividend Farm")
            assert dividend["lifecycle"] == "RESEARCH"
            assert dividend["parameters"]["max_position_pct"] == 1.0

            created = client.post(
                "/api/scenarios",
                json={"name": scenario_name, "strategy_type": "CUSTOM_RESEARCH", "description": "test", "lifecycle": "RESEARCH", "parameters": {"threshold": 2.5}},
                headers={"X-CSRF-Token": "csrf"},
            )
            assert created.status_code == 201
            scenario_id = created.json()["id"]
            updated = client.patch(
                f"/api/scenarios/{scenario_id}",
                json={"name": scenario_name, "strategy_type": "CUSTOM_RESEARCH", "description": "paused", "lifecycle": "PAUSED", "parameters": {"threshold": 3.0}},
                headers={"X-CSRF-Token": "csrf"},
            )
            assert updated.status_code == 200
            assert updated.json()["parameters"]["threshold"] == 3.0

            live_attempt = client.patch(
                f"/api/scenarios/{scenario_id}",
                json={"name": scenario_name, "strategy_type": "CUSTOM_RESEARCH", "description": "unsafe", "lifecycle": "APPROVED_LIVE", "parameters": {}},
                headers={"X-CSRF-Token": "csrf"},
            )
            assert live_attempt.status_code == 422

            settings = client.get("/api/settings")
            assert settings.status_code == 200
            unsafe_settings = client.patch(
                "/api/settings",
                json={"compact_mode": True, "page_size": 25, "confirm_sensitive_actions": False},
                headers={"X-CSRF-Token": "csrf"},
            )
            assert unsafe_settings.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_phase2_console_routes_reject_unauthenticated_access():
    with TestClient(app) as client:
        for route in ("/api/portfolio", "/api/scenarios", "/api/settings", "/api/activity"):
            assert client.get(route).status_code == 401
