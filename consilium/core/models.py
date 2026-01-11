"""Core domain models for Consilium."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, computed_field

from consilium.core.enums import (
    SignalType,
    ConfidenceLevel,
    AssetClass,
    AgentType,
    InvestmentStyle,
)


class StockPrice(BaseModel):
    """Current and historical price data."""

    current: Decimal
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    change_percent: Decimal
    fifty_two_week_high: Decimal
    fifty_two_week_low: Decimal

    @computed_field
    @property
    def from_52w_high_pct(self) -> Decimal:
        """Percentage below 52-week high."""
        if self.fifty_two_week_high == 0:
            return Decimal("0")
        return ((self.fifty_two_week_high - self.current) / self.fifty_two_week_high) * 100

    @computed_field
    @property
    def from_52w_low_pct(self) -> Decimal:
        """Percentage above 52-week low."""
        if self.fifty_two_week_low == 0:
            return Decimal("0")
        return ((self.current - self.fifty_two_week_low) / self.fifty_two_week_low) * 100


class Fundamentals(BaseModel):
    """Fundamental financial metrics."""

    market_cap: Decimal | None = None
    pe_ratio: Decimal | None = None
    forward_pe: Decimal | None = None
    peg_ratio: Decimal | None = None
    price_to_book: Decimal | None = None
    price_to_sales: Decimal | None = None
    enterprise_value: Decimal | None = None
    ev_to_ebitda: Decimal | None = None
    ev_to_revenue: Decimal | None = None
    profit_margin: Decimal | None = None
    operating_margin: Decimal | None = None
    gross_margin: Decimal | None = None
    roe: Decimal | None = None
    roa: Decimal | None = None
    roic: Decimal | None = None
    debt_to_equity: Decimal | None = None
    current_ratio: Decimal | None = None
    quick_ratio: Decimal | None = None
    revenue: Decimal | None = None
    revenue_growth: Decimal | None = None
    earnings_growth: Decimal | None = None
    free_cash_flow: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    dividend_yield: Decimal | None = None
    payout_ratio: Decimal | None = None
    beta: Decimal | None = None
    shares_outstanding: int | None = None


class Technicals(BaseModel):
    """Technical analysis indicators."""

    sma_20: Decimal | None = None
    sma_50: Decimal | None = None
    sma_200: Decimal | None = None
    ema_12: Decimal | None = None
    ema_26: Decimal | None = None
    rsi_14: Decimal | None = None
    macd: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None
    bollinger_upper: Decimal | None = None
    bollinger_middle: Decimal | None = None
    bollinger_lower: Decimal | None = None
    atr_14: Decimal | None = None
    volume_sma_20: int | None = None
    relative_volume: Decimal | None = None

    @computed_field
    @property
    def trend(self) -> str | None:
        """Simple trend indicator based on moving averages."""
        if self.sma_50 is None or self.sma_200 is None:
            return None
        if self.sma_50 > self.sma_200:
            return "BULLISH"
        elif self.sma_50 < self.sma_200:
            return "BEARISH"
        return "NEUTRAL"


class CompanyInfo(BaseModel):
    """Company metadata."""

    name: str
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    website: str | None = None
    employees: int | None = None
    country: str | None = None
    exchange: str | None = None
    currency: str = "USD"


class Stock(BaseModel):
    """Complete stock data aggregation."""

    ticker: str
    asset_class: AssetClass = AssetClass.EQUITY
    company: CompanyInfo
    price: StockPrice
    fundamentals: Fundamentals
    technicals: Technicals
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper().strip()


class AgentProfile(BaseModel):
    """Agent configuration and metadata."""

    id: str
    name: str
    agent_type: AgentType
    investment_style: InvestmentStyle | None = None
    weight: Decimal = Field(default=Decimal("1.0"), ge=0, le=10)
    description: str
    enabled: bool = True


class AgentResponse(BaseModel):
    """Individual agent analysis response."""

    agent_id: str
    agent_name: str
    ticker: str
    signal: SignalType
    confidence: ConfidenceLevel
    target_price: Decimal | None = None
    reasoning: str
    key_factors: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    time_horizon: str | None = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def weighted_score(self) -> Decimal:
        """Calculate weighted score for this response."""
        return Decimal(str(self.signal.score)) * Decimal(str(self.confidence.multiplier))


class SpecialistReport(BaseModel):
    """Specialist agent analysis report for investor consumption."""

    specialist_id: str
    specialist_name: str
    ticker: str
    summary: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    analysis: str
    score: Decimal | None = Field(default=None, ge=0, le=100)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ConsensusResult(BaseModel):
    """Aggregated consensus from all agents."""

    ticker: str
    final_signal: SignalType
    signal_score: Decimal
    confidence: ConfidenceLevel
    buy_votes: int
    sell_votes: int
    hold_votes: int
    weighted_score: Decimal
    agent_responses: list[AgentResponse]
    specialist_reports: list[SpecialistReport] = Field(default_factory=list)
    dissenters: list[str] = Field(default_factory=list)
    key_themes: list[str] = Field(default_factory=list)
    primary_risks: list[str] = Field(default_factory=list)
    consensus_reasoning: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def total_votes(self) -> int:
        """Total number of agent votes."""
        return self.buy_votes + self.sell_votes + self.hold_votes

    @computed_field
    @property
    def agreement_ratio(self) -> Decimal:
        """Ratio of agents agreeing with final signal."""
        if self.total_votes == 0:
            return Decimal("0")
        agreeing = self.total_votes - len(self.dissenters)
        return Decimal(str(agreeing)) / Decimal(str(self.total_votes))


class AnalysisRequest(BaseModel):
    """User analysis request."""

    tickers: list[str]
    include_specialists: bool = True
    agent_filter: list[str] | None = None
    export_format: str | None = None

    @field_validator("tickers", mode="before")
    @classmethod
    def validate_tickers(cls, v: list[str]) -> list[str]:
        return [t.upper().strip() for t in v if t.strip()]


class AnalysisResult(BaseModel):
    """Complete analysis output."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    tickers: list[str]
    results: list[ConsensusResult]
    execution_time_seconds: Decimal
    agents_used: int
    started_at: datetime
    completed_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def success_count(self) -> int:
        """Number of successfully analyzed tickers."""
        return len(self.results)
