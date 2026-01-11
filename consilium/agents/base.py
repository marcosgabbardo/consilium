"""Base agent classes for Consilium."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from consilium.core.enums import SignalType, ConfidenceLevel
from consilium.core.models import (
    Stock,
    AgentResponse,
    AgentProfile,
    SpecialistReport,
)
from consilium.core.exceptions import AgentError
from consilium.llm.client import ClaudeClient
from consilium.llm.prompts import PromptBuilder
from consilium.llm.schemas import AGENT_RESPONSE_SCHEMA, SPECIALIST_REPORT_SCHEMA


class BaseAgent(ABC):
    """
    Abstract base class for all Consilium agents.

    Provides common functionality for LLM interaction, prompt construction,
    and response parsing. Subclasses implement specific analysis logic.
    """

    def __init__(
        self,
        profile: AgentProfile,
        llm_client: ClaudeClient,
        prompt_builder: PromptBuilder,
    ) -> None:
        self.profile = profile
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self._system_prompt: str | None = None

    @property
    def agent_id(self) -> str:
        """Agent identifier."""
        return self.profile.id

    @property
    def name(self) -> str:
        """Agent display name."""
        return self.profile.name

    @property
    def weight(self) -> Decimal:
        """Agent weight for consensus calculation."""
        return self.profile.weight

    @property
    def is_enabled(self) -> bool:
        """Check if agent is enabled."""
        return self.profile.enabled

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the agent-specific system prompt."""
        pass

    @abstractmethod
    def build_analysis_prompt(
        self,
        stock: Stock,
        specialist_reports: list[SpecialistReport] | None = None,
    ) -> str:
        """Build the user prompt for analysis."""
        pass

    async def analyze(
        self,
        stock: Stock,
        specialist_reports: list[SpecialistReport] | None = None,
    ) -> AgentResponse:
        """
        Perform async analysis of a stock.

        Args:
            stock: Stock data to analyze
            specialist_reports: Optional specialist analysis context

        Returns:
            AgentResponse with signal, confidence, and reasoning
        """
        try:
            user_prompt = self.build_analysis_prompt(stock, specialist_reports)

            response = await self.llm_client.complete(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                response_schema=AGENT_RESPONSE_SCHEMA,
            )

            return self._parse_response(response, stock.ticker)

        except Exception as e:
            raise AgentError(
                f"Agent {self.name} failed to analyze {stock.ticker}: {e}",
                agent_id=self.agent_id,
                ticker=stock.ticker,
            ) from e

    def _parse_response(self, raw_response: dict[str, Any], ticker: str) -> AgentResponse:
        """Parse LLM response into structured AgentResponse."""
        return AgentResponse(
            agent_id=self.agent_id,
            agent_name=self.name,
            ticker=ticker,
            signal=SignalType(raw_response["signal"]),
            confidence=ConfidenceLevel(raw_response["confidence"]),
            target_price=Decimal(str(raw_response["target_price"]))
            if raw_response.get("target_price")
            else None,
            reasoning=raw_response["reasoning"],
            key_factors=raw_response.get("key_factors", []),
            risks=raw_response.get("risks", []),
            time_horizon=raw_response.get("time_horizon"),
        )


class InvestorAgent(BaseAgent):
    """
    Base class for investor personality agents.

    Investor agents receive specialist reports as context and apply
    their unique investment philosophy to generate recommendations.
    """

    def __init__(
        self,
        profile: AgentProfile,
        llm_client: ClaudeClient,
        prompt_builder: PromptBuilder,
        persona: str,
        philosophy: str,
        principles: list[str],
        famous_quotes: list[str] | None = None,
    ) -> None:
        super().__init__(profile, llm_client, prompt_builder)
        self.persona = persona
        self.philosophy = philosophy
        self.principles = principles
        self.famous_quotes = famous_quotes or []

    @property
    def system_prompt(self) -> str:
        """Build system prompt from persona and philosophy."""
        return self.prompt_builder.build_system_prompt(
            persona=self.persona,
            philosophy=self.philosophy,
            principles=self.principles,
        )

    def build_analysis_prompt(
        self,
        stock: Stock,
        specialist_reports: list[SpecialistReport] | None = None,
    ) -> str:
        """Build investor-style analysis prompt with specialist context."""
        return self.prompt_builder.build_investor_analysis_prompt(
            stock=stock,
            specialist_reports=specialist_reports,
        )


class SpecialistAgent(BaseAgent):
    """
    Base class for specialist analysis agents.

    Specialist agents focus on specific analysis domains (valuation,
    technicals, etc.) and provide reports consumed by investor agents.
    """

    def __init__(
        self,
        profile: AgentProfile,
        llm_client: ClaudeClient,
        prompt_builder: PromptBuilder,
        focus_area: str,
        methodology: str,
    ) -> None:
        super().__init__(profile, llm_client, prompt_builder)
        self.focus_area = focus_area
        self.methodology = methodology

    @property
    def system_prompt(self) -> str:
        """Build system prompt for specialist."""
        return self.prompt_builder.build_specialist_system_prompt(
            name=self.name,
            focus=self.focus_area,
            methodology=self.methodology,
        )

    def build_analysis_prompt(
        self,
        stock: Stock,
        specialist_reports: list[SpecialistReport] | None = None,
    ) -> str:
        """Build specialist analysis prompt."""
        return self.prompt_builder.build_specialist_analysis_prompt(
            stock=stock,
            focus_area=self.focus_area,
        )

    async def generate_report(self, stock: Stock) -> SpecialistReport:
        """Generate specialized analysis report."""
        try:
            user_prompt = self.build_analysis_prompt(stock)

            response = await self.llm_client.complete(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                response_schema=SPECIALIST_REPORT_SCHEMA,
            )

            return SpecialistReport(
                specialist_id=self.agent_id,
                specialist_name=self.name,
                ticker=stock.ticker,
                summary=response["summary"],
                metrics=response.get("metrics", {}),
                analysis=response["analysis"],
                score=Decimal(str(response["score"])) if response.get("score") else None,
            )

        except Exception as e:
            raise AgentError(
                f"Specialist {self.name} failed to analyze {stock.ticker}: {e}",
                agent_id=self.agent_id,
                ticker=stock.ticker,
            ) from e

    async def analyze(
        self,
        stock: Stock,
        specialist_reports: list[SpecialistReport] | None = None,
    ) -> AgentResponse:
        """Specialists should use generate_report() instead."""
        raise NotImplementedError(
            "Specialists should use generate_report() instead of analyze()"
        )
