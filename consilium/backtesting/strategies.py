"""Trading strategies for backtesting."""

from abc import ABC, abstractmethod
from decimal import Decimal

from consilium.backtesting.models import (
    BacktestStrategyType,
    HistoricalSignal,
    TradeAction,
)
from consilium.core.enums import SignalType


class TradingStrategy(ABC):
    """Abstract base class for trading strategies."""

    @property
    @abstractmethod
    def strategy_type(self) -> BacktestStrategyType:
        """Return the strategy type."""
        pass

    @abstractmethod
    def should_buy(self, signal: HistoricalSignal, has_position: bool) -> bool:
        """Determine if we should buy based on the signal."""
        pass

    @abstractmethod
    def should_sell(self, signal: HistoricalSignal, has_position: bool) -> bool:
        """Determine if we should sell based on the signal."""
        pass

    def get_action(self, signal: HistoricalSignal, has_position: bool) -> TradeAction | None:
        """Get the trading action for a given signal."""
        if not has_position and self.should_buy(signal, has_position):
            return TradeAction.BUY
        elif has_position and self.should_sell(signal, has_position):
            return TradeAction.SELL
        return None


class SignalStrategy(TradingStrategy):
    """
    Signal-based strategy.

    Buy when signal is BUY or STRONG_BUY.
    Sell when signal is SELL or STRONG_SELL.
    """

    @property
    def strategy_type(self) -> BacktestStrategyType:
        return BacktestStrategyType.SIGNAL

    def should_buy(self, signal: HistoricalSignal, has_position: bool) -> bool:
        """Buy on bullish signals (BUY, STRONG_BUY)."""
        if has_position:
            return False
        return signal.is_buy_signal

    def should_sell(self, signal: HistoricalSignal, has_position: bool) -> bool:
        """Sell on bearish signals (SELL, STRONG_SELL)."""
        if not has_position:
            return False
        return signal.is_sell_signal


class ThresholdStrategy(TradingStrategy):
    """
    Threshold-based strategy.

    Buy when weighted score exceeds buy threshold.
    Sell when weighted score falls below sell threshold.
    """

    def __init__(
        self,
        buy_threshold: Decimal = Decimal("50"),
        sell_threshold: Decimal | None = None,
    ):
        """
        Initialize threshold strategy.

        Args:
            buy_threshold: Score above which to buy
            sell_threshold: Score below which to sell (defaults to negative of buy_threshold)
        """
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold or -buy_threshold

    @property
    def strategy_type(self) -> BacktestStrategyType:
        return BacktestStrategyType.THRESHOLD

    def should_buy(self, signal: HistoricalSignal, has_position: bool) -> bool:
        """Buy when score exceeds buy threshold."""
        if has_position:
            return False
        return signal.weighted_score >= self.buy_threshold

    def should_sell(self, signal: HistoricalSignal, has_position: bool) -> bool:
        """Sell when score falls below sell threshold."""
        if not has_position:
            return False
        return signal.weighted_score <= self.sell_threshold


def create_strategy(
    strategy_type: BacktestStrategyType,
    threshold: Decimal | None = None,
) -> TradingStrategy:
    """
    Factory function to create a trading strategy.

    Args:
        strategy_type: The type of strategy to create
        threshold: Threshold value for threshold-based strategy

    Returns:
        A TradingStrategy instance
    """
    if strategy_type == BacktestStrategyType.SIGNAL:
        return SignalStrategy()
    elif strategy_type == BacktestStrategyType.THRESHOLD:
        if threshold is None:
            threshold = Decimal("50")
        return ThresholdStrategy(buy_threshold=threshold)
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
