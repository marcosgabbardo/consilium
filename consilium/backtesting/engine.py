"""Backtesting engine orchestrator."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import partial
from typing import Callable

import yfinance as yf

from consilium.backtesting.metrics import MetricsCalculator
from consilium.backtesting.models import (
    BacktestResult,
    BacktestStrategyType,
    HistoricalSignal,
)
from consilium.backtesting.repository import BacktestRepository
from consilium.backtesting.simulator import TradeSimulator
from consilium.backtesting.strategies import create_strategy
from consilium.config import Settings, get_settings
from consilium.core.enums import ConfidenceLevel, SignalType
from consilium.db.repository import HistoryRepository


class BacktestEngine:
    """Main backtest orchestrator."""

    def __init__(
        self,
        settings: Settings | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize backtest engine."""
        self._settings = settings or get_settings()
        self._progress = progress_callback or (lambda x: None)
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._repository = BacktestRepository(self._settings)
        self._history_repo = HistoryRepository(self._settings)
        self._metrics_calc = MetricsCalculator()

    async def run(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        benchmark: str = "SPY",
        strategy: BacktestStrategyType = BacktestStrategyType.SIGNAL,
        threshold: Decimal | None = None,
        initial_capital: Decimal = Decimal("100000"),
        agent_filter: list[str] | None = None,
        slippage_pct: Decimal = Decimal("0.1"),
    ) -> BacktestResult:
        """
        Run a complete backtest.

        Args:
            ticker: Stock ticker to backtest
            start_date: Start date for backtest
            end_date: End date for backtest
            benchmark: Benchmark ticker for comparison
            strategy: Trading strategy type
            threshold: Score threshold (for threshold strategy)
            initial_capital: Starting capital
            agent_filter: List of agent IDs to use (None = all)
            slippage_pct: Slippage percentage for trades

        Returns:
            BacktestResult with all metrics and trades
        """
        ticker = ticker.upper().strip()
        benchmark = benchmark.upper().strip()

        self._progress(f"Fetching historical prices for {ticker}...")
        prices = await self._fetch_historical_prices(ticker, start_date, end_date)

        self._progress(f"Fetching benchmark prices for {benchmark}...")
        benchmark_prices = await self._fetch_historical_prices(benchmark, start_date, end_date)

        self._progress("Generating trading signals...")
        signals = await self._generate_signals(
            ticker, start_date, end_date, agent_filter
        )

        self._progress("Running simulation...")
        trading_strategy = create_strategy(strategy, threshold)
        simulator = TradeSimulator(initial_capital, slippage_pct)
        state = simulator.simulate(prices, benchmark_prices, signals, trading_strategy)

        self._progress("Calculating metrics...")
        metrics = self._metrics_calc.calculate(
            initial_capital,
            state.snapshots,
            state.trades,
        )

        # Build result
        final_value = state.total_value if state.snapshots else initial_capital

        result = BacktestResult(
            ticker=ticker,
            benchmark=benchmark,
            start_date=start_date,
            end_date=end_date,
            strategy_type=strategy,
            threshold_value=threshold,
            initial_capital=initial_capital,
            final_value=final_value,
            agent_filter=agent_filter,
            metrics=metrics,
            trades=state.trades,
            daily_snapshots=state.snapshots,
            created_at=datetime.now(),
        )

        # Save to database
        self._progress("Saving results...")
        result_id = await self._repository.save_backtest(result)
        result.id = result_id

        return result

    async def _fetch_historical_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> dict[date, Decimal]:
        """
        Fetch historical adjusted close prices.

        Args:
            ticker: Stock ticker
            start_date: Start date
            end_date: End date

        Returns:
            Dict of date -> adjusted close price
        """
        loop = asyncio.get_event_loop()

        def fetch_sync():
            yf_ticker = yf.Ticker(ticker)
            # Add one day buffer to end_date to include it
            hist = yf_ticker.history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
            )
            return hist

        history = await loop.run_in_executor(self._executor, fetch_sync)

        if history.empty:
            raise ValueError(f"No historical data available for {ticker}")

        prices = {}
        for idx, row in history.iterrows():
            price_date = idx.date()
            # Use Close (which is adjusted by yfinance by default)
            close_price = row.get("Close")
            if close_price is not None:
                prices[price_date] = Decimal(str(close_price))

        return prices

    async def _generate_signals(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        agent_filter: list[str] | None,
    ) -> dict[date, HistoricalSignal]:
        """
        Generate trading signals for the backtest period.

        First tries to use historical analysis from database.
        Falls back to simulated signals if no history exists.

        Args:
            ticker: Stock ticker
            start_date: Start date
            end_date: End date
            agent_filter: List of agent IDs to use

        Returns:
            Dict of date -> HistoricalSignal
        """
        signals: dict[date, HistoricalSignal] = {}

        # Try to get historical analysis from database
        try:
            # Fetch with high limit and filter by date in Python
            history = await self._history_repo.get_ticker_history(
                ticker,
                limit=1000,  # Get enough records to cover the period
            )

            for record in history:
                # Filter by date range
                record_date = record.get("created_at")
                if isinstance(record_date, datetime):
                    record_date_only = record_date.date()
                    if record_date_only < start_date or record_date_only > end_date:
                        continue
                elif record_date is None:
                    continue
                else:
                    record_date_only = record_date
                    if record_date_only < start_date or record_date_only > end_date:
                        continue
                # Extract consensus signal from record
                signal_date = record_date_only  # Already converted above

                consensus_signal = record.get("consensus_signal")
                consensus_score = record.get("consensus_score")
                consensus_confidence = record.get("consensus_confidence")

                if consensus_signal:
                    try:
                        signal = SignalType(consensus_signal)
                        confidence = ConfidenceLevel(consensus_confidence) if consensus_confidence else ConfidenceLevel.MEDIUM
                        score = Decimal(str(consensus_score)) if consensus_score else Decimal(str(signal.score))

                        signals[signal_date] = HistoricalSignal(
                            date=signal_date,
                            signal=signal,
                            weighted_score=score,
                            confidence_multiplier=Decimal(str(confidence.multiplier)),
                            source="database",
                        )
                    except (ValueError, KeyError):
                        pass

        except Exception:
            # If database query fails, continue with simulation
            pass

        # If we don't have enough signals, simulate them
        # Generate signals at regular intervals (e.g., monthly)
        if len(signals) < 10:
            self._progress("Simulating trading signals (no historical data)...")
            signals = self._simulate_signals(start_date, end_date)

        return signals

    def _simulate_signals(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[date, HistoricalSignal]:
        """
        Simulate trading signals for backtesting when no historical data exists.

        Uses a simple pattern: alternating BUY/SELL signals at monthly intervals.
        This provides a baseline for testing the backtesting infrastructure.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dict of date -> HistoricalSignal
        """
        signals = {}
        current_date = start_date
        is_buy = True

        # Generate signals at monthly intervals
        while current_date <= end_date:
            if is_buy:
                signal = SignalType.BUY
                score = Decimal("50")
            else:
                signal = SignalType.SELL
                score = Decimal("-50")

            signals[current_date] = HistoricalSignal(
                date=current_date,
                signal=signal,
                weighted_score=score,
                confidence_multiplier=Decimal("0.7"),  # MEDIUM confidence
                source="simulated",
            )

            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)

            is_buy = not is_buy

        return signals


def parse_period(period: str) -> tuple[date, date]:
    """
    Parse a period string like '1y', '2y', '6m' into start and end dates.

    Args:
        period: Period string (e.g., '1y', '2y', '6m', '3m')

    Returns:
        Tuple of (start_date, end_date)
    """
    end_date = date.today()

    period = period.lower().strip()

    if period.endswith("y"):
        years = int(period[:-1])
        start_date = date(end_date.year - years, end_date.month, end_date.day)
    elif period.endswith("m"):
        months = int(period[:-1])
        # Calculate months ago
        year = end_date.year
        month = end_date.month - months
        while month <= 0:
            month += 12
            year -= 1
        start_date = date(year, month, end_date.day)
    elif period.endswith("d"):
        days = int(period[:-1])
        start_date = end_date - timedelta(days=days)
    else:
        raise ValueError(f"Invalid period format: {period}. Use format like '1y', '6m', '30d'")

    return start_date, end_date
