"""Provider-neutral broker read boundary. Execution is intentionally absent."""
from abc import ABC,abstractmethod
from .config import Settings
from .gateway import BrokerGatewayClient
class BrokerAdapter(ABC):
    @abstractmethod
    def status(self)->dict:...
    @abstractmethod
    def read_account_snapshot(self)->dict:...
class RobinhoodBrokerAdapter(BrokerAdapter):
    """Official Robinhood MCP read adapter; has no order/cancel method."""
    def __init__(self,settings:Settings):self.settings=settings;self.client=BrokerGatewayClient(settings)
    def status(self)->dict:
        if not self.settings.robinhood_connection_configured:return {"broker":"robinhood","status":"NOT_CONFIGURED","detail":"Official Robinhood authorization has not been completed"}
        return self.client.status()
    def read_account_snapshot(self)->dict:return self.client.account_snapshot()
