"""Retroactive signal generator for backtesting with real agents."""

from datetime import date, datetime
from decimal import Decimal
from typing import Callable

from consilium.backtesting.models import SignalGranularity, HistoricalSignal
from consilium.config import Settings, get_settings
from consilium.core.enums import ConfidenceLevel
from consilium.data.historical import HistoricalDataProvider


def _add_months(source_date: date, months: int) -> date:
    """Add months to a date, handling month overflow."""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    # Handle day overflow (e.g., Jan 31 + 1 month)
    day = min(source_date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                                  31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


class RetroactiveSignalGenerator:
    """
    Generates retroactive trading signals using real AI agents.

    This class runs actual analysis on historical data points to generate
    meaningful signals for backtesting. It uses point-in-time data to avoid
    look-ahead bias.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialize the retroactive signal generator.

        Args:
            settings: Application settings
            progress_callback: Callback for progress updates
        """
        self._settings = settings or get_settings()
        self._progress = progress_callback or (lambda x: None)
        self._historical_provider = HistoricalDataProvider()

    def generate_date_schedule(
        self,
        start_date: date,
        end_date: date,
        granularity: SignalGranularity,
    ) -> list[date]:
        """
        Generate list of dates for signal generation.

        Args:
            start_date: Start of period
            end_date: End of period
            granularity: Signal frequency (monthly, quarterly, etc.)

        Returns:
            List of dates when signals should be generated
        """
        dates = []
        current = start_date

        while current <= end_date:
            dates.append(current)
            current = _add_months(current, granularity.months_interval)

        return dates

    def estimate_cost(
        self,
        num_dates: int,
        num_investors: int = 13,
        num_specialists: int = 7,
        include_specialists: bool = True,
    ) -> Decimal:
        """
        Estimate total cost for signal generation.

        Args:
            num_dates: Number of signal dates
            num_investors: Number of investor agents
            num_specialists: Number of specialist agents
            include_specialists: Whether specialists are included

        Returns:
            Estimated cost in USD
        """
        # Cost per full analysis ~$1.50
        cost_per_analysis = Decimal("1.50")

        # Adjust for agent selection
        if not include_specialists:
            # Without specialists, cost is roughly 60% (no specialist tokens)
            cost_per_analysis = Decimal("0.90")

        # Adjust for fewer investors
        if num_investors < 13:
            ratio = Decimal(str(num_investors)) / Decimal("13")
            cost_per_analysis = cost_per_analysis * ratio

        return num_dates * cost_per_analysis

    async def generate_signals(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        granularity: SignalGranularity,
        agent_filter: list[str] | None = None,
        include_specialists: bool = True,
    ) -> list[HistoricalSignal]:
        """
        Generate retroactive signals for a ticker using real agents.

        This method runs actual LLM analysis for each date in the schedule,
        using historical data available as of that date.

        Args:
            ticker: Stock ticker symbol
            start_date: Start of period
            end_date: End of period
            granularity: Signal frequency
            agent_filter: Optional list of agent IDs to use
            include_specialists: Whether to include specialist analysis

        Returns:
            List of generated historical signals
        """
        # Import here to avoid circular imports
        from consilium.analysis.orchestrator import AnalysisOrchestrator
        from consilium.db.connection import close_pool

        dates = self.generate_date_schedule(start_date, end_date, granularity)
        signals: list[HistoricalSignal] = []

        self._progress(f"Generating {len(dates)} signals for {ticker}...")

        for i, signal_date in enumerate(dates):
            self._progress(f"Signal {i+1}/{len(dates)}: {signal_date}...")

            try:
                # Get historical data as of this date
                stock = await self._historical_provider.get_stock_as_of(ticker, signal_date)

                # Create orchestrator for this analysis
                orchestrator = AnalysisOrchestrator(
                    settings=self._settings,
                    save_to_history=True,
                    progress_callback=None,  # Suppress inner progress
                )

                # Run analysis with historical data
                result = await orchestrator.analyze_with_stock_data(
                    ticker=ticker,
                    stock_data=stock,
                    agent_filter=agent_filter,
                    include_specialists=include_specialists,
                    analysis_date=datetime.combine(signal_date, datetime.min.time()),
                )

                # Extract consensus signal
                if result.results:
                    consensus = result.results[0]
                    signal = HistoricalSignal(
                        date=signal_date,
                        signal=consensus.final_signal,
                        weighted_score=consensus.weighted_score,
                        confidence_multiplier=Decimal(str(consensus.confidence.multiplier)),
                        source="retroactive",
                    )
                    signals.append(signal)
                    self._progress(
                        f"  -> {signal.signal.value} (score: {signal.weighted_score:.1f})"
                    )

                    # Report individual agent responses
                    for resp in consensus.agent_responses:
                        self._progress(
                            f"     {resp.agent_name}: {resp.signal.value} "
                            f"({resp.confidence.value})"
                        )

            except Exception as e:
                self._progress(f"  -> Error: {e}")
                continue

        self._progress(f"Generated {len(signals)} signals for {ticker}")
        return signals

    async def check_existing_signals(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> list[HistoricalSignal]:
        """
        Check for existing signals in the database.

        Args:
            ticker: Stock ticker symbol
            start_date: Start of period
            end_date: End of period

        Returns:
            List of existing historical signals
        """
        from consilium.db.repository import HistoryRepository

        repo = HistoryRepository(self._settings)
        signals: list[HistoricalSignal] = []

        try:
            history = await repo.get_ticker_history(ticker, limit=1000)

            for record in history:
                record_date = record.get("created_at")
                if isinstance(record_date, datetime):
                    record_date = record_date.date()

                if record_date is None:
                    continue

                if record_date < start_date or record_date > end_date:
                    continue

                consensus_signal = record.get("consensus_signal")
                consensus_score = record.get("consensus_score")
                consensus_confidence = record.get("consensus_confidence")

                if consensus_signal:
                    from consilium.core.enums import SignalType

                    try:
                        signal_type = SignalType(consensus_signal)
                        confidence = (
                            ConfidenceLevel(consensus_confidence)
                            if consensus_confidence
                            else ConfidenceLevel.MEDIUM
                        )
                        score = (
                            Decimal(str(consensus_score))
                            if consensus_score
                            else Decimal(str(signal_type.score))
                        )

                        signals.append(
                            HistoricalSignal(
                                date=record_date,
                                signal=signal_type,
                                weighted_score=score,
                                confidence_multiplier=Decimal(str(confidence.multiplier)),
                                source="database",
                            )
                        )
                    except (ValueError, KeyError):
                        continue

        except Exception:
            pass

        return sorted(signals, key=lambda s: s.date)
