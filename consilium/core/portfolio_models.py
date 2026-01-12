"""Portfolio domain models for Consilium."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, computed_field

from consilium.core.enums import SignalType, ConfidenceLevel


class PositionAction(str, Enum):
    """Recommended action for a portfolio position."""

    BUY_MORE = "BUY_MORE"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL_ALL = "SELL_ALL"
    REBALANCE = "REBALANCE"


class ConcentrationRisk(str, Enum):
    """Portfolio concentration risk level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransactionType(str, Enum):
    """Type of portfolio transaction."""

    BUY = "BUY"
    SELL = "SELL"


class Portfolio(BaseModel):
    """Portfolio metadata."""

    id: int | None = None
    name: str
    description: str | None = None
    currency: str = "USD"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Portfolio name cannot be empty")
        if len(v) > 100:
            raise ValueError("Portfolio name cannot exceed 100 characters")
        return v


class PortfolioPosition(BaseModel):
    """Individual position in a portfolio."""

    id: int | None = None
    portfolio_id: int | None = None
    ticker: str
    quantity: Decimal
    purchase_price: Decimal
    purchase_date: date
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Runtime fields (not stored in DB)
    current_price: Decimal | None = None
    company_name: str | None = None
    sector: str | None = None

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, v: Any) -> Decimal:
        v = Decimal(str(v))
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @field_validator("purchase_price", mode="before")
    @classmethod
    def validate_price(cls, v: Any) -> Decimal:
        v = Decimal(str(v))
        if v <= 0:
            raise ValueError("Purchase price must be positive")
        return v

    @computed_field
    @property
    def cost_basis(self) -> Decimal:
        """Total cost basis for this position."""
        return self.quantity * self.purchase_price

    @computed_field
    @property
    def current_value(self) -> Decimal | None:
        """Current market value of this position."""
        if self.current_price is None:
            return None
        return self.quantity * self.current_price

    @computed_field
    @property
    def unrealized_pnl(self) -> Decimal | None:
        """Unrealized profit/loss in currency."""
        if self.current_value is None:
            return None
        return self.current_value - self.cost_basis

    @computed_field
    @property
    def unrealized_pnl_percent(self) -> Decimal | None:
        """Unrealized profit/loss as percentage."""
        if self.unrealized_pnl is None or self.cost_basis == 0:
            return None
        return (self.unrealized_pnl / self.cost_basis) * 100


class PortfolioTransaction(BaseModel):
    """Individual transaction (buy or sell) in a portfolio."""

    id: int | None = None
    portfolio_id: int | None = None
    ticker: str
    transaction_type: TransactionType
    quantity: Decimal
    price: Decimal
    transaction_date: date
    fees: Decimal = Decimal("0")
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Fields calculated on SELL transactions
    realized_pnl: Decimal | None = None
    holding_period_days: int | None = None
    cost_basis_used: Decimal | None = None  # Avg price used for P&L calculation

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, v: Any) -> Decimal:
        v = Decimal(str(v))
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, v: Any) -> Decimal:
        v = Decimal(str(v))
        if v <= 0:
            raise ValueError("Price must be positive")
        return v

    @field_validator("fees", mode="before")
    @classmethod
    def validate_fees(cls, v: Any) -> Decimal:
        v = Decimal(str(v)) if v else Decimal("0")
        if v < 0:
            raise ValueError("Fees cannot be negative")
        return v

    @computed_field
    @property
    def total_value(self) -> Decimal:
        """Total transaction value (quantity * price)."""
        return self.quantity * self.price

    @computed_field
    @property
    def net_value(self) -> Decimal:
        """Net value after fees (for buys: cost, for sells: proceeds)."""
        if self.transaction_type == TransactionType.BUY:
            return self.total_value + self.fees
        return self.total_value - self.fees


class PositionWithAnalysis(BaseModel):
    """Portfolio position enriched with analysis data."""

    position: PortfolioPosition
    signal: SignalType | None = None
    confidence: ConfidenceLevel | None = None
    target_price: Decimal | None = None
    recommended_action: PositionAction = PositionAction.HOLD
    action_reasoning: str | None = None
    weight_in_portfolio: Decimal = Decimal("0")

    @computed_field
    @property
    def upside_potential(self) -> Decimal | None:
        """Upside potential to target price as percentage."""
        if self.target_price is None or self.position.current_price is None:
            return None
        if self.position.current_price == 0:
            return None
        return ((self.target_price - self.position.current_price) / self.position.current_price) * 100


class SectorAllocation(BaseModel):
    """Sector allocation in portfolio."""

    sector: str
    value: Decimal
    weight: Decimal  # Percentage of portfolio
    ticker_count: int
    tickers: list[str] = Field(default_factory=list)


class PortfolioSummary(BaseModel):
    """Summary metrics for a portfolio."""

    portfolio: Portfolio
    positions: list[PortfolioPosition]
    total_value: Decimal = Decimal("0")
    total_cost_basis: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    total_pnl_percent: Decimal = Decimal("0")
    position_count: int = 0
    sector_allocations: list[SectorAllocation] = Field(default_factory=list)

    @computed_field
    @property
    def concentration_risk(self) -> ConcentrationRisk:
        """Calculate concentration risk based on top holdings."""
        if not self.positions or self.total_value == 0:
            return ConcentrationRisk.LOW

        # Sort positions by value
        position_values = []
        for p in self.positions:
            if p.current_value is not None:
                position_values.append(p.current_value)

        if not position_values:
            return ConcentrationRisk.LOW

        position_values.sort(reverse=True)

        # Calculate top 3 concentration
        top_3_value = sum(position_values[:3])
        top_3_weight = (top_3_value / self.total_value) * 100

        if top_3_weight >= 80:
            return ConcentrationRisk.CRITICAL
        elif top_3_weight >= 60:
            return ConcentrationRisk.HIGH
        elif top_3_weight >= 40:
            return ConcentrationRisk.MEDIUM
        return ConcentrationRisk.LOW

    @computed_field
    @property
    def top_3_concentration(self) -> Decimal:
        """Weight of top 3 holdings as percentage."""
        if not self.positions or self.total_value == 0:
            return Decimal("0")

        position_values = []
        for p in self.positions:
            if p.current_value is not None:
                position_values.append(p.current_value)

        if not position_values:
            return Decimal("0")

        position_values.sort(reverse=True)
        top_3_value = sum(position_values[:3])
        return (top_3_value / self.total_value) * 100


class PortfolioAnalysisResult(BaseModel):
    """Complete portfolio analysis result."""

    portfolio: Portfolio
    positions_with_analysis: list[PositionWithAnalysis]
    portfolio_signal: SignalType
    portfolio_confidence: ConfidenceLevel
    portfolio_score: Decimal
    total_value: Decimal
    total_cost_basis: Decimal
    total_pnl: Decimal
    total_pnl_percent: Decimal
    sector_allocations: list[SectorAllocation]
    concentration_risk: ConcentrationRisk
    top_3_concentration: Decimal
    key_recommendations: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    analysis_id: str | None = None


class CSVColumnMapping(BaseModel):
    """Mapping of CSV columns to position/transaction fields."""

    ticker: str = "ticker"
    quantity: str = "quantity"
    purchase_price: str = "purchase_price"
    purchase_date: str = "purchase_date"
    notes: str | None = None
    # New fields for transaction support
    transaction_type: str | None = None  # If None, assumes BUY
    fees: str | None = None


class CSVImportError(BaseModel):
    """Error during CSV import."""

    row_number: int
    field: str
    value: str
    error: str


class CSVImportResult(BaseModel):
    """Result of CSV import operation."""

    portfolio_id: int
    file_name: str
    records_total: int
    records_success: int
    records_failed: int
    positions_created: list[PortfolioPosition] = Field(default_factory=list)
    transactions_created: list[PortfolioTransaction] = Field(default_factory=list)
    errors: list[CSVImportError] = Field(default_factory=list)
    column_mapping: CSVColumnMapping | None = None

    @computed_field
    @property
    def success_rate(self) -> Decimal:
        """Percentage of successfully imported records."""
        if self.records_total == 0:
            return Decimal("0")
        return (Decimal(self.records_success) / Decimal(self.records_total)) * 100


class PortfolioPerformance(BaseModel):
    """Portfolio performance metrics including realized P&L."""

    portfolio: Portfolio
    total_value: Decimal = Decimal("0")
    total_cost_basis: Decimal = Decimal("0")
    total_unrealized_pnl: Decimal = Decimal("0")
    total_unrealized_pnl_percent: Decimal = Decimal("0")
    total_realized_pnl: Decimal = Decimal("0")
    total_fees_paid: Decimal = Decimal("0")

    # Trade statistics
    total_trades: int = 0
    buy_trades: int = 0
    sell_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Calculated metrics
    avg_holding_period_days: int | None = None
    largest_gain: Decimal | None = None
    largest_loss: Decimal | None = None
    largest_gain_ticker: str | None = None
    largest_loss_ticker: str | None = None

    @computed_field
    @property
    def total_pnl(self) -> Decimal:
        """Total P&L (unrealized + realized)."""
        return self.total_unrealized_pnl + self.total_realized_pnl

    @computed_field
    @property
    def net_realized_pnl(self) -> Decimal:
        """Realized P&L after fees."""
        return self.total_realized_pnl - self.total_fees_paid

    @computed_field
    @property
    def win_rate(self) -> Decimal | None:
        """Percentage of winning trades."""
        if self.sell_trades == 0:
            return None
        return (Decimal(self.winning_trades) / Decimal(self.sell_trades)) * 100

    @computed_field
    @property
    def total_return_percent(self) -> Decimal:
        """Total return as percentage of cost basis."""
        if self.total_cost_basis == 0:
            return Decimal("0")
        return (self.total_pnl / self.total_cost_basis) * 100
