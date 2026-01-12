"""Backtesting engine for historical performance analysis."""

from consilium.backtesting.engine import BacktestEngine, parse_period
from consilium.backtesting.metrics import MetricsCalculator
from consilium.backtesting.models import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResult,
    BacktestStrategyType,
    BacktestTrade,
    DailySnapshot,
    HistoricalSignal,
    TradeAction,
)
from consilium.backtesting.repository import BacktestRepository
from consilium.backtesting.simulator import TradeSimulator
from consilium.backtesting.strategies import (
    SignalStrategy,
    ThresholdStrategy,
    TradingStrategy,
    create_strategy,
)

__all__ = [
    "BacktestEngine",
    "BacktestMetrics",
    "BacktestRepository",
    "BacktestRequest",
    "BacktestResult",
    "BacktestStrategyType",
    "BacktestTrade",
    "create_strategy",
    "DailySnapshot",
    "HistoricalSignal",
    "MetricsCalculator",
    "parse_period",
    "SignalStrategy",
    "ThresholdStrategy",
    "TradeAction",
    "TradeSimulator",
    "TradingStrategy",
]
