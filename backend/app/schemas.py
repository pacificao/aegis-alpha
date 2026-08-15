from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
