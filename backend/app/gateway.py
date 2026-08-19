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
        except (httpx.HTTPError, ValueError):
            return {"status": "ERROR", "detail": "Broker gateway unavailable", "trading": "DISABLED", "mode": "READ_ONLY"}

    def status(self) -> dict:
        return self._request("GET", "/internal/status")

    def market_data_capabilities(self) -> dict:
        return self._request("GET", "/internal/market-data/capabilities")

    def market_data(self, tool: str, arguments: dict) -> dict:
        return self._request("POST", "/internal/market-data", json={"tool": tool, "arguments": arguments})

    def start_authorization(self) -> dict:
        return self._request("POST", "/internal/connect/start")

    def disconnect(self) -> dict:
        return self._request("POST", "/internal/disconnect")
