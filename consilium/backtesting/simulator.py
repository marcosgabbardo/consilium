"""Trade simulation for backtesting."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from consilium.backtesting.models import (
    BacktestTrade,
    DailySnapshot,
    HistoricalSignal,
    TradeAction,
)
from consilium.backtesting.strategies import TradingStrategy


@dataclass
class Position:
    """Current position state."""

    quantity: Decimal = Decimal("0")
    avg_cost: Decimal = Decimal("0")
    entry_date: date | None = None

    @property
    def has_position(self) -> bool:
        """Check if we have an open position."""
        return self.quantity > 0

    @property
    def cost_basis(self) -> Decimal:
        """Total cost basis of current position."""
        return self.quantity * self.avg_cost


@dataclass
class SimulationState:
    """Current state of the simulation."""

    cash: Decimal
    position: Position = field(default_factory=Position)
    trades: list[BacktestTrade] = field(default_factory=list)
    snapshots: list[DailySnapshot] = field(default_factory=list)
    peak_value: Decimal = Decimal("0")

    @property
    def position_value(self) -> Decimal:
        """Value of current position at last price."""
        if not self.snapshots:
            return Decimal("0")
        # Get the most recent snapshot's implied price
        if self.position.quantity > 0 and self.snapshots:
            latest = self.snapshots[-1]
            return latest.position_value
        return Decimal("0")

    @property
    def total_value(self) -> Decimal:
        """Total portfolio value."""
        if self.snapshots:
            return self.snapshots[-1].portfolio_value
        return self.cash


class TradeSimulator:
    """Simulates trade execution for backtesting."""

    def __init__(
        self,
        initial_capital: Decimal,
        slippage_pct: Decimal = Decimal("0.1"),
    ):
        """
        Initialize the trade simulator.

        Args:
            initial_capital: Starting cash amount
            slippage_pct: Slippage percentage applied to trades (e.g., 0.1 = 0.1%)
        """
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct / Decimal("100")  # Convert to decimal
        self.state = SimulationState(cash=initial_capital)
        self.state.peak_value = initial_capital

    def simulate(
        self,
        prices: dict[date, Decimal],
        benchmark_prices: dict[date, Decimal],
        signals: dict[date, HistoricalSignal],
        strategy: TradingStrategy,
    ) -> SimulationState:
        """
        Run the simulation over historical data.

        Args:
            prices: Dict of date -> price for the ticker
            benchmark_prices: Dict of date -> price for the benchmark
            signals: Dict of date -> HistoricalSignal
            strategy: The trading strategy to use

        Returns:
            Final SimulationState with all trades and snapshots
        """
        # Get sorted dates that exist in both prices and benchmark
        all_dates = sorted(set(prices.keys()) & set(benchmark_prices.keys()))

        if not all_dates:
            return self.state

        # Normalize benchmark to start at initial capital
        first_benchmark_price = benchmark_prices[all_dates[0]]
        benchmark_shares = self.initial_capital / first_benchmark_price

        for current_date in all_dates:
            price = prices[current_date]
            benchmark_price = benchmark_prices[current_date]

            # Check for signal and execute if strategy dictates
            if current_date in signals:
                signal = signals[current_date]
                action = strategy.get_action(signal, self.state.position.has_position)

                if action == TradeAction.BUY:
                    self._execute_buy(current_date, price, signal)
                elif action == TradeAction.SELL:
                    self._execute_sell(current_date, price, signal)

            # Record daily snapshot
            self._record_snapshot(
                current_date,
                price,
                benchmark_price * benchmark_shares,
            )

        return self.state

    def _execute_buy(
        self,
        trade_date: date,
        price: Decimal,
        signal: HistoricalSignal,
    ) -> None:
        """Execute a buy order."""
        if self.state.cash <= 0:
            return

        # Apply slippage (higher price for buy)
        execution_price = price * (Decimal("1") + self.slippage_pct)

        # Buy as many shares as we can with available cash
        quantity = self.state.cash / execution_price

        # Update state
        self.state.cash = Decimal("0")
        self.state.position = Position(
            quantity=quantity,
            avg_cost=execution_price,
            entry_date=trade_date,
        )

        # Record trade
        trade = BacktestTrade(
            trade_date=trade_date,
            trade_type=TradeAction.BUY,
            price=execution_price,
            quantity=quantity,
            signal=signal.signal,
            score=signal.weighted_score,
        )
        self.state.trades.append(trade)

    def _execute_sell(
        self,
        trade_date: date,
        price: Decimal,
        signal: HistoricalSignal,
    ) -> None:
        """Execute a sell order."""
        if not self.state.position.has_position:
            return

        # Apply slippage (lower price for sell)
        execution_price = price * (Decimal("1") - self.slippage_pct)

        # Sell entire position
        quantity = self.state.position.quantity
        proceeds = quantity * execution_price
        cost_basis = self.state.position.cost_basis
        realized_pnl = proceeds - cost_basis

        # Update state
        self.state.cash = proceeds
        old_position = self.state.position
        self.state.position = Position()

        # Record trade
        trade = BacktestTrade(
            trade_date=trade_date,
            trade_type=TradeAction.SELL,
            price=execution_price,
            quantity=quantity,
            signal=signal.signal,
            score=signal.weighted_score,
            realized_pnl=realized_pnl,
        )
        self.state.trades.append(trade)

    def _record_snapshot(
        self,
        snapshot_date: date,
        price: Decimal,
        benchmark_value: Decimal,
    ) -> None:
        """Record a daily snapshot of portfolio state."""
        position_value = self.state.position.quantity * price
        portfolio_value = self.state.cash + position_value

        # Update peak value and calculate drawdown
        if portfolio_value > self.state.peak_value:
            self.state.peak_value = portfolio_value

        drawdown = Decimal("0")
        if self.state.peak_value > 0:
            drawdown = (self.state.peak_value - portfolio_value) / self.state.peak_value

        snapshot = DailySnapshot(
            date=snapshot_date,
            portfolio_value=portfolio_value,
            cash=self.state.cash,
            position_value=position_value,
            position_qty=self.state.position.quantity,
            benchmark_value=benchmark_value,
            drawdown=drawdown,
        )
        self.state.snapshots.append(snapshot)

    def get_final_state(self) -> SimulationState:
        """Get the final simulation state."""
        return self.state
