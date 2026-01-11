"""Weighted voting consensus algorithm for agent opinions."""

from collections import Counter
from decimal import Decimal

from consilium.config import Settings, get_settings
from consilium.core.enums import SignalType, ConfidenceLevel
from consilium.core.models import AgentResponse, SpecialistReport, ConsensusResult
from consilium.core.exceptions import ConsensusError


class ConsensusAlgorithm:
    """
    Weighted voting consensus algorithm for aggregating agent opinions.

    The algorithm:
    1. Collects all agent responses
    2. Applies agent weights
    3. Applies confidence multipliers
    4. Calculates weighted score (-100 to +100)
    5. Maps score to final signal
    6. Identifies dissenters and key themes
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._thresholds = self._settings.thresholds

    def calculate_consensus(
        self,
        ticker: str,
        agent_responses: list[AgentResponse],
        specialist_reports: list[SpecialistReport] | None = None,
    ) -> ConsensusResult:
        """
        Calculate weighted consensus from agent responses.

        Args:
            ticker: Stock ticker symbol
            agent_responses: List of investor agent responses
            specialist_reports: List of specialist analysis reports

        Returns:
            ConsensusResult with aggregated recommendation
        """
        if not agent_responses:
            raise ConsensusError(
                "No agent responses to calculate consensus",
                ticker=ticker,
                agent_count=0,
            )

        # Calculate weighted score
        total_weight = Decimal("0")
        weighted_sum = Decimal("0")

        for response in agent_responses:
            agent_weight = self._get_agent_weight(response.agent_id)
            confidence_mult = Decimal(str(response.confidence.multiplier))
            signal_score = Decimal(str(response.signal.score))

            effective_weight = agent_weight * confidence_mult
            weighted_sum += signal_score * effective_weight
            total_weight += effective_weight

        weighted_score = weighted_sum / total_weight if total_weight > 0 else Decimal("0")

        # Map score to signal
        final_signal = self._score_to_signal(weighted_score)

        # Count votes by category
        vote_counts = Counter(r.signal for r in agent_responses)
        buy_votes = (
            vote_counts.get(SignalType.STRONG_BUY, 0) +
            vote_counts.get(SignalType.BUY, 0)
        )
        sell_votes = (
            vote_counts.get(SignalType.STRONG_SELL, 0) +
            vote_counts.get(SignalType.SELL, 0)
        )
        hold_votes = vote_counts.get(SignalType.HOLD, 0)

        # Identify dissenters
        dissenters = self._find_dissenters(agent_responses, final_signal)

        # Extract common themes and risks
        key_themes = self._extract_themes(agent_responses)
        primary_risks = self._extract_risks(agent_responses)

        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(
            agent_responses, final_signal
        )

        # Generate consensus reasoning
        consensus_reasoning = self._generate_reasoning(
            ticker, final_signal, weighted_score, agent_responses, dissenters
        )

        return ConsensusResult(
            ticker=ticker,
            final_signal=final_signal,
            signal_score=weighted_score,
            confidence=overall_confidence,
            buy_votes=buy_votes,
            sell_votes=sell_votes,
            hold_votes=hold_votes,
            weighted_score=weighted_score,
            agent_responses=agent_responses,
            specialist_reports=specialist_reports or [],
            dissenters=dissenters,
            key_themes=key_themes,
            primary_risks=primary_risks,
            consensus_reasoning=consensus_reasoning,
        )

    def _get_agent_weight(self, agent_id: str) -> Decimal:
        """Get agent weight from settings."""
        return self._settings.weights.get_weight(agent_id)

    def _score_to_signal(self, score: Decimal) -> SignalType:
        """Map weighted score to signal type."""
        if score >= self._thresholds.strong_buy:
            return SignalType.STRONG_BUY
        elif score >= self._thresholds.buy:
            return SignalType.BUY
        elif score > self._thresholds.sell:
            return SignalType.HOLD
        elif score > self._thresholds.strong_sell:
            return SignalType.SELL
        else:
            return SignalType.STRONG_SELL

    def _find_dissenters(
        self,
        responses: list[AgentResponse],
        final_signal: SignalType,
    ) -> list[str]:
        """Find agents whose signal significantly differs from consensus."""
        dissenters = []
        final_score = final_signal.score

        for response in responses:
            response_score = response.signal.score
            # Dissenter if score difference > 50 points (e.g., BUY vs SELL)
            if abs(response_score - final_score) > 50:
                dissenters.append(response.agent_name)

        return dissenters

    def _extract_themes(self, responses: list[AgentResponse]) -> list[str]:
        """Extract common themes from agent key factors."""
        all_factors = []
        for r in responses:
            all_factors.extend(r.key_factors)

        if not all_factors:
            return []

        # Count frequency and return top themes
        factor_counts = Counter(all_factors)
        return [f for f, _ in factor_counts.most_common(5)]

    def _extract_risks(self, responses: list[AgentResponse]) -> list[str]:
        """Extract commonly cited risks."""
        all_risks = []
        for r in responses:
            all_risks.extend(r.risks)

        if not all_risks:
            return []

        risk_counts = Counter(all_risks)
        return [r for r, _ in risk_counts.most_common(5)]

    def _calculate_overall_confidence(
        self,
        responses: list[AgentResponse],
        final_signal: SignalType,
    ) -> ConfidenceLevel:
        """Calculate overall confidence based on agreement and individual confidences."""
        if not responses:
            return ConfidenceLevel.LOW

        # Agreement ratio
        agreeing = sum(
            1 for r in responses
            if self._signals_agree(r.signal, final_signal)
        )
        agreement_ratio = agreeing / len(responses)

        # Average confidence of agreeing agents
        agreeing_confidences = [
            r.confidence.multiplier
            for r in responses
            if self._signals_agree(r.signal, final_signal)
        ]
        avg_confidence = (
            sum(agreeing_confidences) / len(agreeing_confidences)
            if agreeing_confidences
            else 0.5
        )

        # Combined score
        combined = agreement_ratio * avg_confidence

        if combined >= 0.8:
            return ConfidenceLevel.VERY_HIGH
        elif combined >= 0.65:
            return ConfidenceLevel.HIGH
        elif combined >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif combined >= 0.35:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def _signals_agree(self, s1: SignalType, s2: SignalType) -> bool:
        """Check if two signals are in agreement (same direction)."""
        bullish = {SignalType.STRONG_BUY, SignalType.BUY}
        bearish = {SignalType.STRONG_SELL, SignalType.SELL}

        if s1 in bullish and s2 in bullish:
            return True
        if s1 in bearish and s2 in bearish:
            return True
        if s1 == SignalType.HOLD and s2 == SignalType.HOLD:
            return True
        return False

    def _generate_reasoning(
        self,
        ticker: str,
        final_signal: SignalType,
        score: Decimal,
        responses: list[AgentResponse],
        dissenters: list[str],
    ) -> str:
        """Generate human-readable consensus reasoning."""
        total = len(responses)
        agreement = total - len(dissenters)

        reasoning = f"Consensus for {ticker}: {final_signal.value} "
        reasoning += f"(weighted score: {score:.1f}). "
        reasoning += f"{agreement}/{total} agents agree with this assessment. "

        if dissenters:
            reasoning += f"Dissenters: {', '.join(dissenters)}. "

        return reasoning
