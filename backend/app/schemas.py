import json
from datetime import date, datetime

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
    account_scope: str = "NOT_SELECTED"
    updated_at: datetime


ParameterValue = bool | int | float | str | list[bool | int | float | str]


class ScenarioBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9 _.-]+$")
    strategy_type: Literal["DIVIDEND_FARM", "TREND_MOMENTUM", "MEAN_REVERSION", "QUALITY_VALUE", "VOLATILITY_BREAKOUT", "PAIRS_REVERSION", "CUSTOM_RESEARCH"]
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
    provider: Literal["alpaca", "alpha_vantage", "fred", "sec_edgar"]
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

Scalar = bool | int | float | str

class StrategyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1,max_length=64,pattern=r"^[a-z][a-z0-9_]*$")
    operator: Literal["eq","ne","gt","gte","lt","lte","in","not_in"]
    value: Scalar | list[Scalar]
    reason: str = Field(min_length=1,max_length=64,pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    @model_validator(mode="after")
    def collection_operator_contract(self):
        if self.operator in {"in","not_in"} and not isinstance(self.value,list):
            raise ValueError("in/not_in rules require a list value")
        return self

class IndicatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1,max_length=64,pattern=r"^[a-z][a-z0-9_]*$")
    kind: Literal["SOURCE_FIELD","SMA","EMA","RSI","ATR","EVENT_YIELD","RECOVERY_DAYS"]
    source: str = Field(min_length=1,max_length=64,pattern=r"^[a-z][a-z0-9_]*$")
    period: int | None = Field(default=None,ge=1,le=1000)

class UniverseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbols: list[str] = Field(default_factory=list,max_length=500)
    exclude_symbols: list[str] = Field(default_factory=list,max_length=500)
    asset_types: list[Literal["EQUITY","ETF","REIT"]] = Field(default_factory=lambda:["EQUITY"])
    @field_validator("symbols","exclude_symbols")
    @classmethod
    def symbols_are_safe(cls,value:list[str])->list[str]:
        clean=[item.strip().upper() for item in value]
        if any(not item or len(item)>16 or not item.replace(".","").replace("-","").isalnum() for item in clean): raise ValueError("Invalid universe symbol")
        if len(set(clean))!=len(clean): raise ValueError("Universe symbols must be unique")
        return clean

class PositionSizingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["FIXED_PERCENT","EQUAL_WEIGHT"] = "FIXED_PERCENT"
    max_position_pct: float = Field(gt=0,le=10)
    max_strategy_allocation_pct: float = Field(gt=0,le=100)
    cash_buffer_pct: float = Field(ge=0,lt=100)

class ScheduleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calendar: Literal["NYSE"] = "NYSE"
    timezone: Literal["America/New_York"] = "America/New_York"
    frequency: Literal["DAILY","WEEKLY","EVENT_DRIVEN"]
    evaluation_time: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")

class StrategySpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1,max_length=120)
    universe: UniverseSpec
    indicators: list[IndicatorSpec] = Field(max_length=64)
    entry_rules: list[StrategyRule] = Field(min_length=1,max_length=64)
    exit_rules: list[StrategyRule] = Field(min_length=1,max_length=64)
    filters: list[StrategyRule] = Field(default_factory=list,max_length=64)
    position_sizing: PositionSizingSpec
    schedule: ScheduleSpec
    parameters: dict[str,Scalar|list[Scalar]] = Field(default_factory=dict)
    @field_validator("parameters")
    @classmethod
    def bounded_parameters(cls,value):
        if len(value)>64 or len(json.dumps(value))>16000: raise ValueError("Strategy parameters exceed limits")
        return value

class StrategyVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    specification: StrategySpecification

class StrategyEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1,max_length=16,pattern=r"^[A-Za-z0-9.-]+$")
    as_of: datetime
    facts: dict[str,Scalar|list[Scalar]] = Field(max_length=128)
    @field_validator("as_of")
    @classmethod
    def timezone_required(cls,value):
        if value.tzinfo is None: raise ValueError("as_of must include timezone")
        return value
    @field_validator("facts")
    @classmethod
    def bounded_safe_facts(cls,value):
        prohibited={"password","secret","token","authorization","api_key","apikey"}
        if len(json.dumps(value))>32000: raise ValueError("Evaluation facts exceed limits")
        if any(not key.replace("_","").isalnum() or len(key)>64 for key in value): raise ValueError("Invalid fact name")
        if any(key.lower() in prohibited for key in value): raise ValueError("Credentials are prohibited in evaluation facts")
        return value

class LabBacktestRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    strategy_version_id:int=Field(gt=0)
    symbols:list[str]=Field(min_length=1,max_length=25)
    start_date:datetime
    end_date:datetime
    initial_capital:float=Field(gt=0,le=1_000_000_000)
    commission_per_trade:float=Field(ge=0,le=100)
    slippage_bps:float=Field(ge=0,le=500)
    spread_bps:float=Field(ge=0,le=500)
    max_position_pct:float=Field(gt=0,le=10)
    max_allocation_pct:float=Field(gt=0,le=100)
    min_dividend_event_pct:float=Field(ge=0,le=100)
    entry_days_before_ex_date:int=Field(ge=1,le=10)
    exit_method:Literal["PURCHASE_PRICE","PURCHASE_MINUS_DIVIDEND","PROFIT_TARGET","FIXED_5","FIXED_10","FIXED_15","FIXED_30","HISTORICAL_RECOVERY","VOLATILITY","HYBRID"]
    profit_target_pct:float=Field(ge=0,le=100)
    historical_recovery_days:int=Field(ge=1,le=1000)
    volatility_multiplier:float=Field(gt=0,le=20)
    hybrid_time_stop_days:int=Field(ge=1,le=1000)
    max_holding_days:int=Field(ge=1,le=1000)
    benchmark_symbol:str=Field(min_length=1,max_length=16,pattern=r"^[A-Za-z0-9.-]+$")
    monte_carlo_iterations:int=Field(ge=10,le=5000)
    random_seed:int=Field(ge=0,le=2_147_483_647)
    run_sensitivity:bool=True
    @field_validator("symbols")
    @classmethod
    def lab_symbols(cls,value):
        clean=[v.strip().upper() for v in value]
        if len(set(clean))!=len(clean) or any(not v or len(v)>16 or not v.replace(".","").replace("-","").isalnum() for v in clean):raise ValueError("Invalid or duplicate symbols")
        return clean
    @model_validator(mode="after")
    def valid_window(self):
        if self.start_date.tzinfo is None or self.end_date.tzinfo is None:raise ValueError("Backtest dates require timezone")
        if self.start_date>=self.end_date:raise ValueError("start_date must precede end_date")
        if (self.end_date-self.start_date).days>36525:raise ValueError("Backtest window exceeds 100 years")
        return self

class RiskAssessmentRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    proposal_id:str=Field(min_length=8,max_length=64,pattern=r"^[A-Za-z0-9._:-]+$")
    strategy_decision_id:int|None=Field(default=None,gt=0)
    symbol:str=Field(min_length=1,max_length=16,pattern=r"^[A-Za-z0-9.-]+$")
    side:Literal["BUY","SELL"]
    quantity:float=Field(gt=0,le=1_000_000_000);price:float=Field(gt=0,le=1_000_000);reference_price:float=Field(gt=0,le=1_000_000)
    fractional_eligible:bool=False;regular_session:bool=False
    portfolio_value:float=Field(gt=0,le=1_000_000_000_000);buying_power:float=Field(ge=0,le=1_000_000_000_000)
    current_position_value:float=Field(ge=0);total_exposure_value:float=Field(ge=0);sector_exposure_value:float=Field(ge=0);correlated_exposure_value:float=Field(ge=0)
    daily_pnl_pct:float=Field(ge=-100,le=1000);drawdown_pct:float=Field(ge=0,le=100);annualized_volatility_pct:float=Field(ge=0,le=1000)
    open_order_count:int=Field(ge=0,le=100000);market_data_as_of:datetime;proposal_created_at:datetime
    @field_validator("symbol")
    @classmethod
    def normalize_risk_symbol(cls,value):return value.upper()
    @field_validator("market_data_as_of","proposal_created_at")
    @classmethod
    def risk_timezones(cls,value):
        if value.tzinfo is None:raise ValueError("Risk timestamps require timezone")
        return value

class RiskControlUpdate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    kill_switch_engaged:bool
    circuit_breaker_engaged:bool
    reason:str=Field(min_length=3,max_length=500)


class RiskPolicyConfiguration(BaseModel):
    model_config=ConfigDict(extra="forbid")
    min_order_notional:float=Field(default=1.0,ge=1.0,le=1000);max_position_pct:float=Field(gt=0,le=100);max_portfolio_exposure_pct:float=Field(gt=0,le=200);max_sector_exposure_pct:float=Field(gt=0,le=100);max_correlated_exposure_pct:float=Field(gt=0,le=200)
    max_daily_loss_pct:float=Field(gt=0,le=100);max_drawdown_pct:float=Field(gt=0,le=100);max_annualized_volatility_pct:float=Field(gt=0,le=1000);max_buying_power_use_pct:float=Field(gt=0,le=100)
    max_order_notional:float=Field(gt=0,le=1_000_000_000);max_order_quantity:float=Field(gt=0,le=1_000_000_000);max_price_deviation_bps:float=Field(gt=0,le=10000)
    max_open_orders:int=Field(gt=0,le=100000);max_market_data_age_seconds:int=Field(gt=0,le=86400);max_proposal_age_seconds:int=Field(gt=0,le=86400)
    micro_account_trial_enabled:bool=True
    micro_account_portfolio_threshold:float=Field(default=100.0,gt=0,le=1000)
    micro_account_max_position_notional:float=Field(default=2.0,gt=0,le=10)

class RiskPolicyCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str=Field(min_length=3,max_length=120)
    configuration:RiskPolicyConfiguration

class IntelligenceEvidence(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_url:str=Field(min_length=12,max_length=500,pattern=r"^https://");title:str=Field(min_length=3,max_length=200);as_of:datetime;max_age_seconds:int=Field(gt=0,le=2592000);claim:str=Field(min_length=3,max_length=1000)
    @field_validator("as_of")
    @classmethod
    def intelligence_timezone(cls,value):
        if value.tzinfo is None:raise ValueError("Evidence timestamps require timezone")
        return value
class IntelligenceArtifactCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    artifact_type:Literal["STRATEGY_CREATION","STRATEGY_CRITIQUE","MARKET_REGIME","NEWS_ANALYSIS","FUNDAMENTAL_ANALYSIS","PARAMETER_RESEARCH","POST_TRADE_REVIEW","ANOMALY_DETECTION","PREMARKET_BRIEFING","POSTMARKET_DIGEST","ATTENTION_ALERT"]
    subject:str=Field(min_length=3,max_length=160);thesis:str=Field(min_length=10,max_length=5000);recommendation:Literal["RESEARCH","HOLD","ADJUST","BUY","SELL","PAUSE","ESCALATE"]
    confidence:float=Field(ge=0,le=1);evidence:list[IntelligenceEvidence]=Field(min_length=1,max_length=50);analysis:dict
    @model_validator(mode="after")
    def bounded_analysis(self):
        encoded=json.dumps(self.analysis,sort_keys=True,allow_nan=False)
        if len(encoded)>20000:raise ValueError("Analysis exceeds 20 KB")
        blocked={"password","passwd","secret","token","credential","api_key","authorization"}
        def keys(value):
            if isinstance(value,dict):return {str(k).lower() for k in value}|set().union(*(keys(v) for v in value.values()))
            if isinstance(value,list):return set().union(*(keys(v) for v in value),set())
            return set()
        if keys(self.analysis)&blocked:raise ValueError("Credential-like fields are prohibited")
        return self
class IntelligenceReviewCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    reviewer:str=Field(min_length=3,max_length=80);verdict:Literal["APPROVE","REJECT","ABSTAIN"];confidence:float=Field(ge=0,le=1);rationale:str=Field(min_length=10,max_length=3000);evidence_checksum:str=Field(min_length=64,max_length=64,pattern=r"^[a-f0-9]{64}$")

class PaperOrderCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    risk_assessment_id:int=Field(gt=0);quote_record_id:int=Field(gt=0)


class ControlledIntentCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    risk_assessment_id:int=Field(gt=0)
    order_type:Literal["LIMIT"]="LIMIT"

class ControlledIntentApproval(BaseModel):
    model_config=ConfigDict(extra="forbid")
    intent_checksum:str=Field(min_length=64,max_length=64)
    confirmation:Literal["APPROVE CONTROLLED TRIAL"]

class ControlledIntentRejection(BaseModel):
    model_config=ConfigDict(extra="forbid")
    reason:str=Field(min_length=10,max_length=500)

class PlannedTradeCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    strategy_decision_id:int=Field(gt=0);planned_entry_date:date;quantity:float=Field(gt=0,le=1_000_000_000);reference_price:float=Field(gt=0,le=1_000_000);rationale:str=Field(min_length=10,max_length=2000)
class PlannedTradeCancel(BaseModel):
    model_config=ConfigDict(extra="forbid")
    reason:str=Field(min_length=10,max_length=500)
class PlannedTradeRevalidate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    risk_assessment_id:int=Field(gt=0)

class LiveTradingAuthorizationUpdate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    enabled:bool
    max_order_notional:float=Field(ge=1,le=5)
    duration_minutes:int=Field(ge=5,le=60)
    confirmation:Literal["AUTHORIZE CONTROLLED LIVE TRADING","DISABLE LIVE TRADING"]
    reason:str=Field(min_length=10,max_length=500)

class ControlledExecutionRecovery(BaseModel):
    model_config=ConfigDict(extra="forbid")
    order_ref:str=Field(min_length=3,max_length=120,pattern=r"^[A-Za-z0-9_-]+$")
    confirmation:Literal["RECOVER UNKNOWN BROKER ORDER"]

class ControlledExecutionCancel(BaseModel):
    model_config=ConfigDict(extra="forbid")
    confirmation:Literal["CANCEL LIVE ORDER"]
    reason:str=Field(min_length=10,max_length=500)
