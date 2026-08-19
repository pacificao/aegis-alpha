from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aegis_env: Literal["development", "test", "staging", "production"] = "development"
    aegis_version: str = "0.8.0-gateway"
    aegis_trading_enabled: bool = False
    database_url: str = "sqlite:///./aegis-test.db"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: str = "test-only-not-for-deployment"
    session_ttl_seconds: int = 28_800
    session_idle_ttl_seconds: int = 1_800
    allowed_origins: str = "http://localhost"
    trusted_hosts: str = "localhost,127.0.0.1"
    pam_bridge_socket: str = "/run/aegis-auth/pam.sock"
    authorized_user: str = ""
    auth_cookie_name: str = "aegis_session"
    robinhood_mcp_url: str = "https://agent.robinhood.com/mcp/trading"
    robinhood_connection_configured: bool = False
    broker_gateway_url: str = "http://broker-gateway:8100"
    broker_gateway_shared_secret: str = Field(default="", min_length=32)

    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""
    sec_user_agent: str = "Aegis Alpha admin@pacificao.com"
    data_cache_ttl_seconds: int = Field(default=300, ge=30, le=86_400)
    default_market_symbols: str = "SPY,QQQ,AAPL"
    @field_validator("aegis_trading_enabled")
    @classmethod
    def trading_must_remain_disabled(cls, value: bool) -> bool:
        if value:
            raise ValueError("Trading is prohibited in Phase 1")
        return value

    @property
    def is_secure_cookie(self) -> bool:
        return self.aegis_env in {"staging", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
