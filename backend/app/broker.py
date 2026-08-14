from abc import ABC, abstractmethod


class BrokerAdapter(ABC):
    @abstractmethod
    def status(self) -> dict[str, str]:
        """Return connectivity only; Phase 1 adapters cannot place orders."""


class RobinhoodBrokerAdapter(BrokerAdapter):
    def status(self) -> dict[str, str]:
        return {"broker": "robinhood", "status": "DISCONNECTED", "detail": "Future integration; no credentials configured"}

