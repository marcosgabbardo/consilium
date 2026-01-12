"""Models for Q&A functionality."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from consilium.core.enums import SignalType, ConfidenceLevel


class AskResponse(BaseModel):
    """Individual agent response to a question."""

    agent_id: str
    agent_name: str
    signal: SignalType
    confidence: ConfidenceLevel
    reasoning: str
    key_factors: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    time_horizon: Optional[str] = None
    target_price: Optional[Decimal] = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def weighted_score(self) -> Decimal:
        """Calculate weighted score."""
        return Decimal(str(self.signal.score)) * Decimal(str(self.confidence.multiplier))


class AskResult(BaseModel):
    """Complete result of a Q&A session."""

    id: Optional[int] = None
    question: str
    tickers: list[str] = Field(default_factory=list)
    agents_queried: list[str]
    responses: list[AskResponse] = Field(default_factory=list)
    include_market_data: bool = True
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: Decimal = Decimal("0")
    execution_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def consensus_signal(self) -> Optional[SignalType]:
        """Calculate consensus signal from responses."""
        if not self.responses:
            return None

        buy_votes = sum(1 for r in self.responses if r.signal.is_bullish)
        sell_votes = sum(1 for r in self.responses if r.signal.is_bearish)

        if buy_votes > sell_votes:
            return SignalType.BUY
        elif sell_votes > buy_votes:
            return SignalType.SELL
        return SignalType.HOLD

    @property
    def bullish_count(self) -> int:
        """Count of bullish responses."""
        return sum(1 for r in self.responses if r.signal.is_bullish)

    @property
    def bearish_count(self) -> int:
        """Count of bearish responses."""
        return sum(1 for r in self.responses if r.signal.is_bearish)

    @property
    def neutral_count(self) -> int:
        """Count of neutral (HOLD) responses."""
        return sum(1 for r in self.responses if r.signal == SignalType.HOLD)
