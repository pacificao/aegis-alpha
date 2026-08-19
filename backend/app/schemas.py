import json
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import TaskStatus


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ordinal: int
    title: str
    status: TaskStatus
    notes: str
    updated_at: datetime


class PhaseOut(BaseModel):
    id: int
    number: int
    name: str
    description: str
    status: TaskStatus
    completion_percentage: int
    tasks: list[TaskOut]


class RobinhoodConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9 _.-]+$")
    endpoint: Literal["https://agent.robinhood.com/mcp/trading"]


class RobinhoodConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    connection_name: str
    endpoint: str
    mode: str
    status: str = "NOT_CONFIGURED"
    updated_at: datetime


ParameterValue = bool | int | float | str | list[str]


class ScenarioBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9 _.-]+$")
    strategy_type: Literal["DIVIDEND_FARM", "CUSTOM_RESEARCH"]
    description: str = Field(default="", max_length=1000)
    lifecycle: Literal["RESEARCH", "PAUSED"] = "RESEARCH"
    parameters: dict[str, ParameterValue] = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def safe_parameters(cls, value: dict[str, ParameterValue]) -> dict[str, ParameterValue]:
        if len(value) > 64 or len(json.dumps(value)) > 16_000:
            raise ValueError("Scenario parameters exceed Phase 2 limits")
        if any(not key.replace("_", "").isalnum() or len(key) > 64 for key in value):
            raise ValueError("Scenario parameter names must be simple identifiers")
        return value


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(ScenarioBase):
    pass


class ScenarioOut(ScenarioBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class OperatorPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    compact_mode: bool
    page_size: int = Field(ge=10, le=100)
    confirm_sensitive_actions: Literal[True] = True


class OperatorPreferenceOut(OperatorPreferenceUpdate):
    model_config = ConfigDict(from_attributes=True)
    username: str
    updated_at: datetime

class DataIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["alpha_vantage", "fred", "sec_edgar"]
    dataset: Literal["historical", "quote", "fundamentals", "dividends", "news", "economic", "companyfacts"]
    symbol: str | None = Field(default=None, min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.-]+$")
    series_id: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    cik: str | None = Field(default=None, min_length=1, max_length=10, pattern=r"^[0-9]+$")

    @model_validator(mode="after")
    def required_identifiers(self):
        symbol_sets={"historical", "quote", "fundamentals", "dividends"}
        if self.dataset in symbol_sets and not self.symbol:
            raise ValueError("symbol is required for this dataset")
        if self.dataset == "economic" and not self.series_id:
            raise ValueError("series_id is required for economic data")
        if self.dataset == "companyfacts" and not self.cik:
            raise ValueError("cik is required for SEC company facts")
        return self

RobinhoodMarketTool = Literal[
    "get_equity_historicals", "get_equity_fundamentals", "get_financials", "get_equity_price_book",
    "get_equity_technical_indicators", "get_earnings_results", "get_earnings_calendar", "get_indexes",
    "get_index_quotes", "get_equity_quotes", "get_equity_tradability", "get_option_historicals",
    "get_option_chains", "get_option_instruments", "get_option_quotes", "get_currency_pairs", "get_crypto_quotes",
]

class RobinhoodDataIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: RobinhoodMarketTool
    symbol: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9./:-]+$")
    arguments: dict = Field(default_factory=dict)

    @field_validator("arguments")
    @classmethod
    def safe_arguments(cls, value: dict) -> dict:
        if len(json.dumps(value)) > 8_192:
            raise ValueError("Robinhood market-data arguments are too large")
        prohibited = {"password", "secret", "token", "authorization", "api_key", "apikey"}
        def contains_prohibited(item) -> bool:
            if isinstance(item, dict):
                return any(str(key).lower() in prohibited or contains_prohibited(child) for key, child in item.items())
            if isinstance(item, list):
                return any(contains_prohibited(child) for child in item)
            return False
        if contains_prohibited(value):
            raise ValueError("Credentials are prohibited in market-data arguments")
        return value

class DataRecordOut(BaseModel):
    id: int
    symbol: str | None
    data_type: str
    event_time: datetime
