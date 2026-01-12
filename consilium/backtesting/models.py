"""Backtesting domain models for Consilium."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field

from consilium.core.enums import SignalType


class BacktestStrategyType(str, Enum):
    """Strategy type for backtesting."""

    SIGNAL = "signal"  # Buy on BUY/STRONG_BUY, sell on SELL/STRONG_SELL
    THRESHOLD = "threshold"  # Buy when score > threshold, sell when < threshold

    def __str__(self) -> str:
        return self.value


class SignalGranularity(str, Enum):
    """Granularity for retroactive signal generation."""

    MONTHLY = "monthly"  # 12 signals per year
    QUARTERLY = "quarterly"  # 4 signals per year
    SEMIANNUAL = "semiannual"  # 2 signals per year
    ANNUAL = "annual"  # 1 signal per year

    def __str__(self) -> str:
        return self.value

    @property
    def months_interval(self) -> int:
        """Return the interval in months between signals."""
        intervals = {
            SignalGranularity.MONTHLY: 1,
            SignalGranularity.QUARTERLY: 3,
            SignalGranularity.SEMIANNUAL: 6,
            SignalGranularity.ANNUAL: 12,
        }
        return intervals[self]

    @property
    def signals_per_year(self) -> int:
        """Return the number of signals generated per year."""
        return 12 // self.months_interval


class TradeAction(str, Enum):
    """Trade action type."""

    BUY = "BUY"
    SELL = "SELL"

    def __str__(self) -> str:
        return self.value


class BacktestTrade(BaseModel):
    """Individual trade in a backtest."""

    id: int | None = None
    trade_date: date
    trade_type: TradeAction
    price: Decimal
    quantity: Decimal
    signal: SignalType | None = None
    score: Decimal | None = None
    realized_pnl: Decimal | None = None

    @computed_field
    @property
    def total_value(self) -> Decimal:
        """Total value of the trade."""
        return self.price * self.quantity


class DailySnapshot(BaseModel):
    """Daily portfolio state during backtest."""

    date: date
    portfolio_value: Decimal
    cash: Decimal
    position_value: Decimal
    position_qty: Decimal
    benchmark_value: Decimal
    drawdown: Decimal = Decimal("0")

    @computed_field
    @property
    def daily_return(self) -> Decimal | None:
        """Daily return percentage (requires previous day comparison)."""
        return None  # Calculated externally in sequence


class BacktestMetrics(BaseModel):
    """Complete metrics for a backtest."""

    # Returns
    total_return: Decimal
    total_return_pct: Decimal
    cagr: Decimal
    alpha: Decimal

    # Risk
    beta: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    max_drawdown: Decimal
    max_drawdown_duration_days: int
    var_95: Decimal

    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    profit_factor: Decimal
    avg_holding_days: int
    avg_win: Decimal
    avg_loss: Decimal

    # Benchmark
    benchmark_return: Decimal
    excess_return: Decimal

    @computed_field
    @property
    def risk_reward_ratio(self) -> Decimal:
        """Risk/reward ratio (avg win / avg loss)."""
        if self.avg_loss == 0:
            return Decimal("0")
        return abs(self.avg_win / self.avg_loss)


class BacktestResult(BaseModel):
    """Complete backtest result."""

    id: int | None = None
    ticker: str
    benchmark: str
    start_date: date
    end_date: date
    strategy_type: BacktestStrategyType
    threshold_value: Decimal | None = None
    initial_capital: Decimal
    final_value: Decimal
    agent_filter: list[str] | None = None

    metrics: BacktestMetrics
    trades: list[BacktestTrade] = Field(default_factory=list)
    daily_snapshots: list[DailySnapshot] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def duration_days(self) -> int:
        """Total duration of backtest in days."""
        return (self.end_date - self.start_date).days

    @computed_field
    @property
    def total_pnl(self) -> Decimal:
        """Total profit/loss."""
        return self.final_value - self.initial_capital


class BacktestRequest(BaseModel):
    """User backtest request."""

    ticker: str
    start_date: date | None = None
    end_date: date | None = None
    period: str | None = None  # e.g., "1y", "2y", "6m"
    benchmark: str = "SPY"
    strategy: BacktestStrategyType = BacktestStrategyType.SIGNAL
    threshold: Decimal | None = None
    initial_capital: Decimal = Decimal("100000")
    agent_filter: list[str] | None = None
    slippage_pct: Decimal = Decimal("0.1")


class HistoricalSignal(BaseModel):
    """Historical signal data point for backtesting."""

    date: date
    signal: SignalType
    weighted_score: Decimal
    confidence_multiplier: Decimal
    source: str  # "database" or "simulated"

    @computed_field
    @property
    def is_buy_signal(self) -> bool:
        """Check if this is a buy signal."""
        return self.signal.is_bullish

    @computed_field
    @property
    def is_sell_signal(self) -> bool:
        """Check if this is a sell signal."""
        return self.signal.is_bearish
