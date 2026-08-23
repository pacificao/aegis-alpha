"""Narrow client for the isolated broker gateway; no generic MCP-call method exists."""
import httpx

from .config import Settings


class BrokerGatewayClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.broker_gateway_url.rstrip("/")
        self.headers = {"X-Aegis-Gateway-Key": settings.broker_gateway_shared_secret}

    def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        try:
            response = httpx.request(method, f"{self.base_url}{path}", headers=self.headers, json=json, timeout=35)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            status="REJECTED" if exc.response.status_code in {409,422} else "BLOCKED" if exc.response.status_code==403 else "ERROR"
            return {"status":status,"detail":"Broker gateway rejected or unavailable","trading":"DISABLED"}
        except (httpx.HTTPError, ValueError):
            return {"status": "ERROR", "detail": "Broker gateway unavailable", "trading": "DISABLED", "mode": "READ_ONLY"}

    def status(self) -> dict:
        return self._request("GET", "/internal/status")

    def market_data_capabilities(self) -> dict:
        return self._request("GET", "/internal/market-data/capabilities")

    def market_data(self, tool: str, arguments: dict) -> dict:
        return self._request("POST", "/internal/market-data", json={"tool": tool, "arguments": arguments})

    def account_snapshot(self, selected_account_ref: str) -> dict:
        """Fetch only the allowlisted pseudonymous brokerage account."""
        return self._request("POST", "/internal/account-snapshot", json={"selected_account_ref": selected_account_ref})

    def tool_schema(self, tool: str) -> dict:
        return self._request("GET", f"/internal/tool-schema/{tool}")

    def execution_review(self, payload: dict) -> dict:
        return self._request("POST", "/internal/execution/review", json=payload)

    def execution_place(self, payload: dict) -> dict:
        return self._request("POST", "/internal/execution/place", json=payload)

    def execution_cancel(self, payload: dict) -> dict:
        return self._request("POST", "/internal/execution/cancel", json=payload)

    def start_authorization(self) -> dict:
        return self._request("POST", "/internal/connect/start")

    def disconnect(self) -> dict:
        return self._request("POST", "/internal/disconnect")
