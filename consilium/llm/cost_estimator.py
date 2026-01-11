"""Cost estimation for Anthropic API calls."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class ModelPricing:
    """Pricing per million tokens (USD)."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal


@dataclass
class CostBreakdown:
    """Breakdown of estimated costs."""

    component: str  # "Specialists" or "Investors"
    api_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


@dataclass
class CostEstimate:
    """Complete cost estimate for an analysis."""

    model: str
    tickers: list[str] = field(default_factory=list)
    breakdowns: list[CostBreakdown] = field(default_factory=list)
    total_api_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: Decimal = Decimal("0")


class CostEstimator:
    """Estimates API costs before execution."""

    # Claude model pricing (USD per million tokens) - Jan 2026
    PRICING: dict[str, ModelPricing] = {
        "claude-opus-4-5-20251101": ModelPricing(
            input_per_mtok=Decimal("15.00"),
            output_per_mtok=Decimal("75.00"),
        ),
        "claude-sonnet-4-20250514": ModelPricing(
            input_per_mtok=Decimal("3.00"),
            output_per_mtok=Decimal("15.00"),
        ),
        "claude-3-5-haiku-20241022": ModelPricing(
            input_per_mtok=Decimal("0.25"),
            output_per_mtok=Decimal("1.25"),
        ),
    }

    # Average token estimates per call type (based on actual analysis)
    TOKEN_ESTIMATES: dict[str, dict[str, int]] = {
        "specialist": {
            "input": 600,  # system prompt + user prompt
            "output": 500,  # response
        },
        "investor": {
            "input": 2500,  # system prompt + user prompt + specialist reports
            "output": 700,  # response
        },
        "investor_no_specialists": {
            "input": 1300,  # system prompt + user prompt (no specialist reports)
            "output": 700,  # response
        },
    }

    # Default agent counts
    DEFAULT_INVESTORS = 13
    DEFAULT_SPECIALISTS = 7

    def __init__(self, model: str = "claude-opus-4-5-20251101") -> None:
        self.model = model
        self.pricing = self.PRICING.get(model, self.PRICING["claude-opus-4-5-20251101"])

    def estimate(
        self,
        num_tickers: int,
        num_investors: int | None = None,
        num_specialists: int | None = None,
        include_specialists: bool = True,
    ) -> CostEstimate:
        """
        Estimate total cost for analysis.

        Args:
            num_tickers: Number of tickers to analyze
            num_investors: Number of investor agents (default: 13)
            num_specialists: Number of specialist agents (default: 7)
            include_specialists: Whether specialists are included

        Returns:
            CostEstimate with detailed breakdown
        """
        if num_investors is None:
            num_investors = self.DEFAULT_INVESTORS
        if num_specialists is None:
            num_specialists = self.DEFAULT_SPECIALISTS

        breakdowns: list[CostBreakdown] = []

        # Specialist costs (if enabled)
        if include_specialists and num_specialists > 0:
            specialist_calls = num_tickers * num_specialists
            specialist_input = specialist_calls * self.TOKEN_ESTIMATES["specialist"]["input"]
            specialist_output = specialist_calls * self.TOKEN_ESTIMATES["specialist"]["output"]
            specialist_cost = self._calculate_cost(specialist_input, specialist_output)

            breakdowns.append(
                CostBreakdown(
                    component="Specialists",
                    api_calls=specialist_calls,
                    input_tokens=specialist_input,
                    output_tokens=specialist_output,
                    cost_usd=specialist_cost,
                )
            )

        # Investor costs
        investor_calls = num_tickers * num_investors

        # Choose token estimate based on whether specialists are included
        token_key = "investor" if include_specialists else "investor_no_specialists"
        investor_input_per_call = self.TOKEN_ESTIMATES[token_key]["input"]
        investor_output_per_call = self.TOKEN_ESTIMATES[token_key]["output"]

        investor_input = investor_calls * investor_input_per_call
        investor_output = investor_calls * investor_output_per_call
        investor_cost = self._calculate_cost(investor_input, investor_output)

        breakdowns.append(
            CostBreakdown(
                component="Investors",
                api_calls=investor_calls,
                input_tokens=investor_input,
                output_tokens=investor_output,
                cost_usd=investor_cost,
            )
        )

        # Calculate totals
        total_calls = sum(b.api_calls for b in breakdowns)
        total_input = sum(b.input_tokens for b in breakdowns)
        total_output = sum(b.output_tokens for b in breakdowns)
        total_cost = sum((b.cost_usd for b in breakdowns), Decimal("0"))

        return CostEstimate(
            model=self.model,
            tickers=[],  # Will be filled by caller
            breakdowns=breakdowns,
            total_api_calls=total_calls,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=total_cost,
        )

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Calculate cost from token counts."""
        input_cost = (Decimal(input_tokens) / Decimal("1000000")) * self.pricing.input_per_mtok
        output_cost = (Decimal(output_tokens) / Decimal("1000000")) * self.pricing.output_per_mtok
        return input_cost + output_cost

    @classmethod
    def get_model_name(cls, model_id: str) -> str:
        """Get human-readable model name."""
        names = {
            "claude-opus-4-5-20251101": "Claude Opus 4.5",
            "claude-sonnet-4-20250514": "Claude Sonnet 4",
            "claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
        }
        return names.get(model_id, model_id)
