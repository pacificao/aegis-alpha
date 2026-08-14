from abc import ABC, abstractmethod

from .config import Settings


class BrokerAdapter(ABC):
    @abstractmethod
    def status(self) -> dict[str, str]:
        """Return connectivity only; Phase 1 adapters cannot place orders."""


class RobinhoodBrokerAdapter(BrokerAdapter):
    """Read-only Phase 1 boundary; deliberately has no order methods."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def status(self) -> dict[str, str]:
        if not self.settings.robinhood_connection_configured:
            return {"broker": "robinhood", "status": "NOT_CONFIGURED", "detail": "Official Robinhood Trading MCP authorization has not been completed"}
        return {"broker": "robinhood", "status": "DISCONNECTED", "detail": "Configured but no authenticated MCP connection is available to this service"}

