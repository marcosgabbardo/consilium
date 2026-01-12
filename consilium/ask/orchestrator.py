"""Orchestrates Q&A with investor agents."""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Callable

from consilium.config import Settings, get_settings
from consilium.core.models import Stock
from consilium.core.enums import SignalType, ConfidenceLevel
from consilium.core.exceptions import AgentError
from consilium.data.yahoo import YahooFinanceProvider
from consilium.data.cache import CachedDataProvider
from consilium.db.connection import get_pool
from consilium.agents.registry import AgentRegistry
from consilium.agents.base import InvestorAgent
from consilium.llm.ask_prompts import AskPromptBuilder, ASK_RESPONSE_SCHEMA
from consilium.ask.models import AskResponse, AskResult
from consilium.ask.ticker_extractor import TickerExtractor


class AskOrchestrator:
    """
    Orchestrates Q&A sessions with investor agents.

    Flow:
    1. Extract tickers from question (or use explicit)
    2. Fetch market data for tickers (optional)
    3. Build Q&A prompt
    4. Query each agent in parallel
    5. Return aggregated results
    """

    def __init__(
        self,
        settings: Settings | None = None,
        data_provider: CachedDataProvider | None = None,
        registry: AgentRegistry | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._data_provider = data_provider
        self._registry = registry or AgentRegistry(self._settings)
        self._progress_callback = progress_callback or (lambda x: None)
        self._ticker_extractor = TickerExtractor()
        self._prompt_builder = AskPromptBuilder()

    async def _ensure_data_provider(self) -> CachedDataProvider:
        """Ensure data provider is initialized."""
        if self._data_provider is None:
            pool = await get_pool()
            yahoo = YahooFinanceProvider()
            self._data_provider = CachedDataProvider(yahoo, pool)
        return self._data_provider

    def _report_progress(self, message: str) -> None:
        """Report progress if callback is configured."""
        self._progress_callback(message)

    async def ask(
        self,
        question: str,
        agent_ids: list[str],
        explicit_tickers: list[str] | None = None,
        include_market_data: bool = True,
    ) -> AskResult:
        """
        Ask a question to one or more investor agents.

        Args:
            question: The user's question
            agent_ids: List of agent IDs to query
            explicit_tickers: Explicitly specified tickers (override auto-detection)
            include_market_data: Whether to fetch and include market data

        Returns:
            AskResult with question, responses, and metadata
        """
        start_time = datetime.now()

        # 1. Extract tickers from question (or use explicit)
        if explicit_tickers:
            tickers = [t.upper().strip() for t in explicit_tickers]
        else:
            extraction = self._ticker_extractor.extract(question)
            tickers = extraction.tickers

        # 2. Fetch market data for tickers (if enabled)
        stock_data: dict[str, Stock] = {}
        if include_market_data and tickers:
            self._report_progress(f"Fetching market data for {len(tickers)} ticker(s)...")
            data_provider = await self._ensure_data_provider()

            for ticker in tickers:
                try:
                    stock = await data_provider.get_stock(ticker)
                    stock_data[ticker] = stock
                except Exception as e:
                    # Log but continue - ticker might be invalid
                    self._report_progress(f"Warning: Could not fetch data for {ticker}: {e}")

        # 3. Get agents
        agents: list[InvestorAgent] = []
        for agent_id in agent_ids:
            agent = self._registry.get_agent(agent_id)
            if agent and isinstance(agent, InvestorAgent):
                agents.append(agent)

        if not agents:
            raise AgentError(f"No valid investor agents found for IDs: {agent_ids}")

        # 4. Build Q&A prompt
        qa_prompt = self._prompt_builder.build_qa_prompt(
            question=question,
            stock_data=stock_data if stock_data else None,
        )

        # 5. Query each agent in parallel
        self._report_progress(f"Asking {len(agents)} investor(s)...")
        responses = await self._query_agents_parallel(agents, qa_prompt)

        # Filter out any failed responses (exceptions)
        valid_responses: list[AskResponse] = [
            r for r in responses if isinstance(r, AskResponse)
        ]

        # 6. Calculate totals
        total_input_tokens = sum(r.input_tokens for r in valid_responses)
        total_output_tokens = sum(r.output_tokens for r in valid_responses)
        total_cost = self._calculate_cost(total_input_tokens, total_output_tokens)

        execution_time = (datetime.now() - start_time).total_seconds()

        # 7. Build result
        result = AskResult(
            question=question,
            tickers=tickers,
            agents_queried=[a.agent_id for a in agents],
            responses=valid_responses,
            include_market_data=include_market_data,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_cost_usd=total_cost,
            execution_time_seconds=execution_time,
            created_at=datetime.now(),
        )

        return result

    async def _query_agents_parallel(
        self,
        agents: list[InvestorAgent],
        qa_prompt: str,
    ) -> list[AskResponse | Exception]:
        """Query multiple agents in parallel."""
        semaphore = asyncio.Semaphore(self._settings.max_concurrent_agents)

        async def query_single(agent: InvestorAgent) -> AskResponse | Exception:
            async with semaphore:
                try:
                    return await self._query_agent(agent, qa_prompt)
                except Exception as e:
                    return e

        tasks = [query_single(agent) for agent in agents]
        return await asyncio.gather(*tasks)

    async def _query_agent(
        self,
        agent: InvestorAgent,
        qa_prompt: str,
    ) -> AskResponse:
        """Query a single agent with the Q&A prompt."""
        # Build system prompt with Q&A suffix
        system_prompt = agent.system_prompt + self._prompt_builder.build_qa_system_prompt_suffix()

        # Get LLM client from agent
        llm_client = agent.llm_client

        # Make the API call
        response = await llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=qa_prompt,
            response_schema=ASK_RESPONSE_SCHEMA,
            max_tokens=1500,
            temperature=0.7,
        )

        # Parse response into AskResponse
        return AskResponse(
            agent_id=agent.agent_id,
            agent_name=agent.name,
            signal=SignalType(response.get("signal", "HOLD")),
            confidence=ConfidenceLevel(response.get("confidence", "MEDIUM")),
            reasoning=response.get("reasoning", ""),
            key_factors=response.get("key_factors", []),
            risks=response.get("risks", []),
            time_horizon=response.get("time_horizon"),
            target_price=(
                Decimal(str(response["target_price"]))
                if response.get("target_price")
                else None
            ),
            input_tokens=response.get("_input_tokens", 0),
            output_tokens=response.get("_output_tokens", 0),
        )

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Calculate cost based on model pricing."""
        # Use CostEstimator pricing
        from consilium.llm.cost_estimator import CostEstimator

        estimator = CostEstimator(self._settings.model)
        return estimator._calculate_cost(input_tokens, output_tokens)
