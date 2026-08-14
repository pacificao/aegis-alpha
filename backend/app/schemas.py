from datetime import datetime

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

