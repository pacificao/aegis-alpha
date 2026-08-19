import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TaskStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"
    WAITING_FOR_CREDENTIALS = "WAITING_FOR_CREDENTIALS"


class Phase(Base):
    __tablename__ = "phases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    tasks: Mapped[list["Task"]] = relationship(back_populates="phase", order_by="Task.ordinal", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phase_id: Mapped[int] = mapped_column(ForeignKey("phases.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, native_enum=False), default=TaskStatus.NOT_STARTED)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    phase: Mapped[Phase] = relationship(back_populates="tasks")


class DevelopmentActivity(Base):
    __tablename__ = "development_activity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class BrokerConnectionConfig(Base):
    __tablename__ = "broker_connection_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    connection_name: Mapped[str] = mapped_column(String(80))
    endpoint: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(20), default="READ_ONLY")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StrategyScenario(Base):
    __tablename__ = "strategy_scenarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    strategy_type: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text, default="")
    lifecycle: Mapped[str] = mapped_column(String(20), default="RESEARCH")
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OperatorPreference(Base):
    __tablename__ = "operator_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    compact_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    page_size: Mapped[int] = mapped_column(Integer, default=20)
    confirm_sensitive_actions: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DataProvider(Base):
    __tablename__ = "data_providers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(40))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    credential_status: Mapped[str] = mapped_column(String(30), default="NOT_REQUIRED")
    base_url: Mapped[str] = mapped_column(String(255))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    asset_type: Mapped[str] = mapped_column(String(30), default="EQUITY")
    exchange: Mapped[str] = mapped_column(String(30), default="")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    cik: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

class DataRecord(Base):
    __tablename__ = "data_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id", ondelete="RESTRICT"), index=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), nullable=True, index=True)
    data_type: Mapped[str] = mapped_column(String(40), index=True)
    external_id: Mapped[str] = mapped_column(String(255), default="")
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    interval: Mapped[str] = mapped_column(String(20), default="")
    payload: Mapped[dict] = mapped_column(JSON)
    source_url: Mapped[str] = mapped_column(String(500))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    quality_status: Mapped[str] = mapped_column(String(20), default="VALID")
    checksum: Mapped[str] = mapped_column(String(64), index=True)

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id", ondelete="RESTRICT"), index=True)
    dataset: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")

class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int | None] = mapped_column(ForeignKey("data_records.id", ondelete="CASCADE"), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(60), index=True)
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
