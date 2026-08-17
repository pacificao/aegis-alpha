import json
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
