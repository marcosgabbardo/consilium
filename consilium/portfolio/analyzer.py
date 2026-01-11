"""Portfolio analysis orchestration."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Callable

from consilium.config import Settings, get_settings
from consilium.core.enums import SignalType, ConfidenceLevel
from consilium.core.models import AnalysisResult, ConsensusResult
from consilium.core.portfolio_models import (
    Portfolio,
    PortfolioPosition,
    PortfolioSummary,
    PortfolioAnalysisResult,
    PositionWithAnalysis,
    PositionAction,
    SectorAllocation,
    ConcentrationRisk,
)
from consilium.data.yahoo import YahooFinanceProvider
from consilium.data.cache import CachedDataProvider
from consilium.db.connection import get_pool
from consilium.db.portfolio_repository import PortfolioRepository
from consilium.analysis.orchestrator import AnalysisOrchestrator


class PortfolioAnalyzer:
    """
    Analyzes portfolio holdings using the multi-agent system.

    Provides:
    - Current market values and P&L
    - Sector allocation analysis
    - Per-position signal recommendations
    - Portfolio-level consensus signal
    """

    def __init__(
        self,
        settings: Settings | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._progress_callback = progress_callback
        self._yahoo = YahooFinanceProvider()

    def _report_progress(self, message: str) -> None:
        """Report progress if callback is configured."""
        if self._progress_callback:
            self._progress_callback(message)

    async def get_portfolio_summary(
        self,
        portfolio: Portfolio,
        positions: list[PortfolioPosition],
        refresh_prices: bool = True,
    ) -> PortfolioSummary:
        """
        Get portfolio summary with current prices and P&L.

        Args:
            portfolio: Portfolio metadata
            positions: List of positions
            refresh_prices: Whether to fetch current prices

        Returns:
            PortfolioSummary with metrics
        """
        if refresh_prices:
            self._report_progress("Fetching current prices...")
            positions = await self._enrich_positions(positions)

        # Calculate totals
        total_value = Decimal("0")
        total_cost_basis = Decimal("0")

        for p in positions:
            total_cost_basis += p.cost_basis
            if p.current_value is not None:
                total_value += p.current_value

        total_pnl = total_value - total_cost_basis
        total_pnl_percent = (
            (total_pnl / total_cost_basis) * 100
            if total_cost_basis > 0
            else Decimal("0")
        )

        # Calculate sector allocation
        sector_allocations = self._calculate_sector_allocation(positions, total_value)

        return PortfolioSummary(
            portfolio=portfolio,
            positions=positions,
            total_value=total_value,
            total_cost_basis=total_cost_basis,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            position_count=len(positions),
            sector_allocations=sector_allocations,
        )

    async def analyze(
        self,
        portfolio: Portfolio,
        positions: list[PortfolioPosition],
        agent_filter: list[str] | None = None,
        include_specialists: bool = True,
    ) -> PortfolioAnalysisResult:
        """
        Perform full portfolio analysis with multi-agent system.

        Args:
            portfolio: Portfolio metadata
            positions: List of positions
            agent_filter: Optional list of agent IDs to use
            include_specialists: Whether to run specialist analysis

        Returns:
            PortfolioAnalysisResult with recommendations
        """
        self._report_progress("Enriching positions with market data...")
        positions = await self._enrich_positions(positions)

        # Get unique tickers
        tickers = list(set(p.ticker for p in positions))

        self._report_progress(f"Analyzing {len(tickers)} unique tickers...")

        # Run analysis on all tickers
        orchestrator = AnalysisOrchestrator(
            settings=self._settings,
            progress_callback=self._progress_callback,
            save_to_history=True,
        )

        analysis_result = await orchestrator.analyze(
            tickers=tickers,
            agent_filter=agent_filter,
            include_specialists=include_specialists,
        )

        # Map ticker to consensus result
        ticker_consensus: dict[str, ConsensusResult] = {
            c.ticker: c for c in analysis_result.results
        }

        # Build positions with analysis
        positions_with_analysis = self._build_positions_with_analysis(
            positions=positions,
            ticker_consensus=ticker_consensus,
        )

        # Calculate portfolio-level metrics
        total_value, total_cost_basis = self._calculate_totals(positions)
        total_pnl = total_value - total_cost_basis
        total_pnl_percent = (
            (total_pnl / total_cost_basis) * 100
            if total_cost_basis > 0
            else Decimal("0")
        )

        sector_allocations = self._calculate_sector_allocation(positions, total_value)

        # Calculate portfolio-level signal (value-weighted)
        portfolio_signal, portfolio_score, portfolio_confidence = (
            self._calculate_portfolio_consensus(positions_with_analysis, total_value)
        )

        # Generate recommendations and warnings
        recommendations, warnings = self._generate_insights(
            positions_with_analysis,
            sector_allocations,
            total_value,
        )

        # Calculate concentration risk
        concentration_risk = self._calculate_concentration_risk(positions, total_value)
        top_3_concentration = self._calculate_top_3_concentration(positions, total_value)

        return PortfolioAnalysisResult(
            portfolio=portfolio,
            positions_with_analysis=positions_with_analysis,
            portfolio_signal=portfolio_signal,
            portfolio_confidence=portfolio_confidence,
            portfolio_score=portfolio_score,
            total_value=total_value,
            total_cost_basis=total_cost_basis,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            sector_allocations=sector_allocations,
            concentration_risk=concentration_risk,
            top_3_concentration=top_3_concentration,
            key_recommendations=recommendations,
            risk_warnings=warnings,
            analysis_id=analysis_result.request_id,
        )

    async def _enrich_positions(
        self,
        positions: list[PortfolioPosition],
    ) -> list[PortfolioPosition]:
        """Enrich positions with current market data."""
        pool = await get_pool()
        data_provider = CachedDataProvider(self._yahoo, pool)

        for position in positions:
            try:
                stock = await data_provider.get_stock(position.ticker)
                position.current_price = stock.price.current
                position.company_name = stock.company.name
                position.sector = stock.company.sector
            except Exception as e:
                self._report_progress(f"Warning: Could not fetch data for {position.ticker}: {e}")
                # Keep position but without current price

        return positions

    def _calculate_totals(
        self,
        positions: list[PortfolioPosition],
    ) -> tuple[Decimal, Decimal]:
        """Calculate total value and cost basis."""
        total_value = Decimal("0")
        total_cost_basis = Decimal("0")

        for p in positions:
            total_cost_basis += p.cost_basis
            if p.current_value is not None:
                total_value += p.current_value

        return total_value, total_cost_basis

    def _calculate_sector_allocation(
        self,
        positions: list[PortfolioPosition],
        total_value: Decimal,
    ) -> list[SectorAllocation]:
        """Calculate sector allocation from positions."""
        sector_data: dict[str, dict] = defaultdict(
            lambda: {"value": Decimal("0"), "tickers": []}
        )

        for p in positions:
            sector = p.sector or "Unknown"
            if p.current_value is not None:
                sector_data[sector]["value"] += p.current_value
                if p.ticker not in sector_data[sector]["tickers"]:
                    sector_data[sector]["tickers"].append(p.ticker)

        allocations = []
        for sector, data in sector_data.items():
            weight = (
                (data["value"] / total_value) * 100
                if total_value > 0
                else Decimal("0")
            )
            allocations.append(
                SectorAllocation(
                    sector=sector,
                    value=data["value"],
                    weight=weight,
                    ticker_count=len(data["tickers"]),
                    tickers=data["tickers"],
                )
            )

        # Sort by weight descending
        allocations.sort(key=lambda x: x.weight, reverse=True)
        return allocations

    def _build_positions_with_analysis(
        self,
        positions: list[PortfolioPosition],
        ticker_consensus: dict[str, ConsensusResult],
    ) -> list[PositionWithAnalysis]:
        """Build positions with analysis data."""
        # Group positions by ticker and calculate weights
        ticker_value: dict[str, Decimal] = defaultdict(Decimal)
        for p in positions:
            if p.current_value is not None:
                ticker_value[p.ticker] += p.current_value

        total_value = sum(ticker_value.values())

        results = []
        for p in positions:
            consensus = ticker_consensus.get(p.ticker)

            weight = (
                (p.current_value / total_value) * 100
                if total_value > 0 and p.current_value is not None
                else Decimal("0")
            )

            signal = consensus.final_signal if consensus else None
            confidence = consensus.confidence if consensus else None

            # Get average target price from agents
            target_price = None
            if consensus:
                targets = [
                    r.target_price
                    for r in consensus.agent_responses
                    if r.target_price is not None
                ]
                if targets:
                    target_price = sum(targets) / len(targets)

            # Determine recommended action
            action, reasoning = self._determine_action(p, signal, confidence, weight)

            results.append(
                PositionWithAnalysis(
                    position=p,
                    signal=signal,
                    confidence=confidence,
                    target_price=target_price,
                    recommended_action=action,
                    action_reasoning=reasoning,
                    weight_in_portfolio=weight,
                )
            )

        # Sort by weight descending
        results.sort(key=lambda x: x.weight_in_portfolio, reverse=True)
        return results

    def _determine_action(
        self,
        position: PortfolioPosition,
        signal: SignalType | None,
        confidence: ConfidenceLevel | None,
        weight: Decimal,
    ) -> tuple[PositionAction, str]:
        """Determine recommended action for a position."""
        if signal is None:
            return PositionAction.HOLD, "No analysis available"

        # Strong signals with high confidence
        if signal == SignalType.STRONG_BUY:
            if weight < Decimal("5"):
                return PositionAction.BUY_MORE, "Strong buy signal with small position"
            return PositionAction.HOLD, "Strong buy signal, maintain position"

        if signal == SignalType.BUY:
            if weight < Decimal("3"):
                return PositionAction.BUY_MORE, "Buy signal with minimal exposure"
            return PositionAction.HOLD, "Buy signal, position appropriately sized"

        if signal == SignalType.HOLD:
            return PositionAction.HOLD, "Consensus is to hold current position"

        if signal == SignalType.SELL:
            if weight > Decimal("10"):
                return PositionAction.REDUCE, "Sell signal with large position"
            return PositionAction.REDUCE, "Sell signal, consider reducing"

        if signal == SignalType.STRONG_SELL:
            return PositionAction.SELL_ALL, "Strong sell signal, exit position"

        return PositionAction.HOLD, "Default to hold"

    def _calculate_portfolio_consensus(
        self,
        positions: list[PositionWithAnalysis],
        total_value: Decimal,
    ) -> tuple[SignalType, Decimal, ConfidenceLevel]:
        """Calculate value-weighted portfolio consensus."""
        if not positions or total_value == 0:
            return SignalType.HOLD, Decimal("0"), ConfidenceLevel.LOW

        weighted_score = Decimal("0")
        total_weighted = Decimal("0")
        confidence_scores = []

        for pa in positions:
            if pa.signal is None or pa.position.current_value is None:
                continue

            weight = pa.position.current_value / total_value
            signal_score = Decimal(str(pa.signal.score))
            weighted_score += signal_score * weight
            total_weighted += weight

            if pa.confidence:
                confidence_scores.append(pa.confidence.multiplier)

        if total_weighted == 0:
            return SignalType.HOLD, Decimal("0"), ConfidenceLevel.LOW

        final_score = weighted_score / total_weighted

        # Determine signal from score
        if final_score >= 75:
            signal = SignalType.STRONG_BUY
        elif final_score >= 55:
            signal = SignalType.BUY
        elif final_score >= 45:
            signal = SignalType.HOLD
        elif final_score >= 25:
            signal = SignalType.SELL
        else:
            signal = SignalType.STRONG_SELL

        # Average confidence
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            if avg_confidence >= 0.9:
                confidence = ConfidenceLevel.VERY_HIGH
            elif avg_confidence >= 0.75:
                confidence = ConfidenceLevel.HIGH
            elif avg_confidence >= 0.5:
                confidence = ConfidenceLevel.MEDIUM
            elif avg_confidence >= 0.25:
                confidence = ConfidenceLevel.LOW
            else:
                confidence = ConfidenceLevel.VERY_LOW
        else:
            confidence = ConfidenceLevel.LOW

        return signal, final_score, confidence

    def _calculate_concentration_risk(
        self,
        positions: list[PortfolioPosition],
        total_value: Decimal,
    ) -> ConcentrationRisk:
        """Calculate concentration risk level."""
        if not positions or total_value == 0:
            return ConcentrationRisk.LOW

        position_values = [
            p.current_value for p in positions if p.current_value is not None
        ]
        if not position_values:
            return ConcentrationRisk.LOW

        position_values.sort(reverse=True)
        top_3_value = sum(position_values[:3])
        top_3_weight = (top_3_value / total_value) * 100

        if top_3_weight >= 80:
            return ConcentrationRisk.CRITICAL
        elif top_3_weight >= 60:
            return ConcentrationRisk.HIGH
        elif top_3_weight >= 40:
            return ConcentrationRisk.MEDIUM
        return ConcentrationRisk.LOW

    def _calculate_top_3_concentration(
        self,
        positions: list[PortfolioPosition],
        total_value: Decimal,
    ) -> Decimal:
        """Calculate top 3 holdings concentration percentage."""
        if not positions or total_value == 0:
            return Decimal("0")

        position_values = [
            p.current_value for p in positions if p.current_value is not None
        ]
        if not position_values:
            return Decimal("0")

        position_values.sort(reverse=True)
        top_3_value = sum(position_values[:3])
        return (top_3_value / total_value) * 100

    def _generate_insights(
        self,
        positions: list[PositionWithAnalysis],
        sector_allocations: list[SectorAllocation],
        total_value: Decimal,
    ) -> tuple[list[str], list[str]]:
        """Generate recommendations and risk warnings."""
        recommendations = []
        warnings = []

        # Check for strong signals
        strong_buys = [p for p in positions if p.signal == SignalType.STRONG_BUY]
        strong_sells = [p for p in positions if p.signal == SignalType.STRONG_SELL]

        if strong_buys:
            tickers = ", ".join(p.position.ticker for p in strong_buys[:3])
            recommendations.append(f"Consider increasing positions in: {tickers}")

        if strong_sells:
            tickers = ", ".join(p.position.ticker for p in strong_sells[:3])
            recommendations.append(f"Consider exiting positions: {tickers}")

        # Check sector concentration
        if sector_allocations:
            top_sector = sector_allocations[0]
            if top_sector.weight >= Decimal("50"):
                warnings.append(
                    f"High sector concentration: {top_sector.sector} ({top_sector.weight:.1f}%)"
                )

        # Check position concentration
        if positions:
            top_position = positions[0]
            if top_position.weight_in_portfolio >= Decimal("25"):
                warnings.append(
                    f"Large single position: {top_position.position.ticker} ({top_position.weight_in_portfolio:.1f}%)"
                )

        # Check for negative P&L positions with sell signals
        losers_to_sell = [
            p for p in positions
            if p.signal in (SignalType.SELL, SignalType.STRONG_SELL)
            and p.position.unrealized_pnl is not None
            and p.position.unrealized_pnl < 0
        ]
        if losers_to_sell:
            recommendations.append(
                f"Consider tax-loss harvesting: {', '.join(p.position.ticker for p in losers_to_sell[:2])}"
            )

        # Check for highly profitable positions with hold/sell signals
        big_winners = [
            p for p in positions
            if p.signal in (SignalType.HOLD, SignalType.SELL)
            and p.position.unrealized_pnl_percent is not None
            and p.position.unrealized_pnl_percent > 100
        ]
        if big_winners:
            recommendations.append(
                f"Consider profit-taking on large gains: {', '.join(p.position.ticker for p in big_winners[:2])}"
            )

        return recommendations, warnings
