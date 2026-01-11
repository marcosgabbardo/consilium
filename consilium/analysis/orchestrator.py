"""Analysis orchestrator for coordinating multi-agent analysis pipeline."""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Callable

from consilium.config import Settings, get_settings
from consilium.core.models import (
    Stock,
    AnalysisRequest,
    AnalysisResult,
    ConsensusResult,
    AgentResponse,
    SpecialistReport,
)
from consilium.core.exceptions import AgentError, DataFetchError
from consilium.data.yahoo import YahooFinanceProvider
from consilium.data.cache import CachedDataProvider
from consilium.db.connection import DatabasePool, get_pool
from consilium.db.repository import HistoryRepository
from consilium.agents.registry import AgentRegistry
from consilium.agents.base import InvestorAgent, SpecialistAgent
from consilium.analysis.consensus import ConsensusAlgorithm


class AnalysisOrchestrator:
    """
    Orchestrates the multi-agent analysis pipeline.

    Pipeline:
    1. Fetch market data (with caching)
    2. Run specialist agents in parallel
    3. Run investor agents in parallel (with specialist reports as context)
    4. Calculate consensus
    5. Return results
    """

    def __init__(
        self,
        settings: Settings | None = None,
        data_provider: CachedDataProvider | None = None,
        registry: AgentRegistry | None = None,
        consensus: ConsensusAlgorithm | None = None,
        progress_callback: Callable[[str], None] | None = None,
        save_to_history: bool = True,
    ) -> None:
        self._settings = settings or get_settings()
        self._data_provider = data_provider
        self._registry = registry or AgentRegistry(self._settings)
        self._consensus = consensus or ConsensusAlgorithm(self._settings)
        self._progress_callback = progress_callback
        self._save_to_history = save_to_history

    async def _ensure_data_provider(self) -> CachedDataProvider:
        """Ensure data provider is initialized."""
        if self._data_provider is None:
            pool = await get_pool()
            yahoo = YahooFinanceProvider()
            self._data_provider = CachedDataProvider(yahoo, pool)
        return self._data_provider

    def _report_progress(self, message: str) -> None:
        """Report progress if callback is configured."""
        if self._progress_callback:
            self._progress_callback(message)

    async def analyze(
        self,
        tickers: list[str],
        agent_filter: list[str] | None = None,
        include_specialists: bool = True,
    ) -> AnalysisResult:
        """
        Perform complete analysis on a list of tickers.

        Args:
            tickers: List of ticker symbols to analyze
            agent_filter: Optional list of agent IDs to use (None = all)
            include_specialists: Whether to run specialist analysis first

        Returns:
            AnalysisResult with consensus results for each ticker
        """
        started_at = datetime.utcnow()
        data_provider = await self._ensure_data_provider()

        # Normalize tickers
        tickers = [t.upper().strip() for t in tickers]

        # Get agents
        investors = self._registry.get_investors(agent_filter)
        specialists = self._registry.get_specialists() if include_specialists else []

        if not investors:
            raise AgentError("No investor agents available for analysis")

        results: list[ConsensusResult] = []

        # Analyze each ticker
        for ticker in tickers:
            self._report_progress(f"Analyzing {ticker}...")

            try:
                consensus = await self._analyze_ticker(
                    ticker=ticker,
                    data_provider=data_provider,
                    investors=investors,
                    specialists=specialists,
                )
                results.append(consensus)
            except Exception as e:
                # Log error but continue with other tickers
                self._report_progress(f"Error analyzing {ticker}: {e}")
                continue

        completed_at = datetime.utcnow()
        execution_time = Decimal(str((completed_at - started_at).total_seconds()))

        analysis_result = AnalysisResult(
            tickers=tickers,
            results=results,
            execution_time_seconds=execution_time,
            agents_used=len(investors) + len(specialists),
            started_at=started_at,
            completed_at=completed_at,
        )

        # Auto-save to history if enabled
        if self._save_to_history and results:
            try:
                pool = await get_pool()
                history_repo = HistoryRepository(pool)
                analysis_id = await history_repo.save_analysis(analysis_result)
                self._report_progress(f"Analysis saved to history (ID: {analysis_id})")
            except Exception as e:
                self._report_progress(f"Warning: Failed to save analysis to history: {e}")

        return analysis_result

    async def _analyze_ticker(
        self,
        ticker: str,
        data_provider: CachedDataProvider,
        investors: list[InvestorAgent],
        specialists: list[SpecialistAgent],
    ) -> ConsensusResult:
        """Analyze a single ticker through the full pipeline."""
        # Step 1: Fetch market data
        self._report_progress(f"Fetching data for {ticker}...")
        stock = await data_provider.get_stock(ticker)

        # Step 2: Run specialist analysis (parallel)
        specialist_reports: list[SpecialistReport] = []
        if specialists:
            self._report_progress(f"Running specialist analysis for {ticker}...")
            specialist_reports = await self._run_specialists(stock, specialists)

        # Step 3: Run investor analysis (parallel)
        self._report_progress(f"Running investor analysis for {ticker}...")
        agent_responses = await self._run_investors(stock, investors, specialist_reports)

        # Step 4: Calculate consensus
        self._report_progress(f"Calculating consensus for {ticker}...")
        consensus = self._consensus.calculate_consensus(
            ticker=ticker,
            agent_responses=agent_responses,
            specialist_reports=specialist_reports,
        )

        return consensus

    def _is_billing_error(self, error: Exception) -> bool:
        """Check if the error is related to API billing/credits."""
        error_str = str(error).lower()
        billing_keywords = [
            "credit balance",
            "billing",
            "payment",
            "subscription",
            "quota exceeded",
            "rate limit",
            "insufficient funds",
        ]
        return any(keyword in error_str for keyword in billing_keywords)

    async def _run_specialists(
        self,
        stock: Stock,
        specialists: list[SpecialistAgent],
    ) -> list[SpecialistReport]:
        """Run all specialist agents in parallel."""
        semaphore = asyncio.Semaphore(self._settings.max_concurrent_agents)
        billing_error_shown = False

        async def run_with_semaphore(specialist: SpecialistAgent) -> SpecialistReport | None:
            nonlocal billing_error_shown
            async with semaphore:
                try:
                    return await specialist.generate_report(stock)
                except Exception as e:
                    if self._is_billing_error(e) and not billing_error_shown:
                        billing_error_shown = True
                        self._report_progress(
                            "[API BILLING ERROR] Your Anthropic API credit balance is too low. "
                            "Please add credits at: https://console.anthropic.com/settings/billing"
                        )
                    else:
                        self._report_progress(
                            f"Specialist {specialist.name} failed: {e}"
                        )
                    return None

        tasks = [run_with_semaphore(s) for s in specialists]
        results = await asyncio.gather(*tasks)

        return [r for r in results if r is not None]

    async def _run_investors(
        self,
        stock: Stock,
        investors: list[InvestorAgent],
        specialist_reports: list[SpecialistReport],
    ) -> list[AgentResponse]:
        """Run all investor agents in parallel."""
        semaphore = asyncio.Semaphore(self._settings.max_concurrent_agents)
        billing_error_shown = False

        async def run_with_semaphore(investor: InvestorAgent) -> AgentResponse | None:
            nonlocal billing_error_shown
            async with semaphore:
                try:
                    return await investor.analyze(stock, specialist_reports)
                except Exception as e:
                    if self._is_billing_error(e) and not billing_error_shown:
                        billing_error_shown = True
                        self._report_progress(
                            "[API BILLING ERROR] Your Anthropic API credit balance is too low. "
                            "Please add credits at: https://console.anthropic.com/settings/billing"
                        )
                    else:
                        self._report_progress(
                            f"Investor {investor.name} failed: {e}"
                        )
                    return None

        tasks = [run_with_semaphore(i) for i in investors]
        results = await asyncio.gather(*tasks)

        return [r for r in results if r is not None]

    async def analyze_single(
        self,
        ticker: str,
        agent_filter: list[str] | None = None,
        include_specialists: bool = True,
    ) -> ConsensusResult:
        """
        Convenience method to analyze a single ticker.

        Args:
            ticker: Ticker symbol to analyze
            agent_filter: Optional list of agent IDs to use
            include_specialists: Whether to run specialist analysis

        Returns:
            ConsensusResult for the ticker
        """
        result = await self.analyze(
            tickers=[ticker],
            agent_filter=agent_filter,
            include_specialists=include_specialists,
        )

        if not result.results:
            raise DataFetchError(
                f"Failed to analyze {ticker}",
                ticker=ticker,
            )

        return result.results[0]
