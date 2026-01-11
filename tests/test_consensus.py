"""Tests for the consensus algorithm."""

from decimal import Decimal
import pytest

from consilium.core.enums import SignalType, ConfidenceLevel
from consilium.core.models import AgentResponse
from consilium.analysis.consensus import ConsensusAlgorithm


class TestConsensusAlgorithm:
    """Test suite for ConsensusAlgorithm."""

    def test_calculate_consensus_bullish_majority(self, sample_agent_responses):
        """Test consensus with bullish majority."""
        consensus = ConsensusAlgorithm()
        result = consensus.calculate_consensus(
            ticker="AAPL",
            agent_responses=sample_agent_responses,
        )

        # With 2 BUYs, 1 HOLD, 1 SELL - should lean BUY
        assert result.ticker == "AAPL"
        assert result.buy_votes == 2
        assert result.hold_votes == 1
        assert result.sell_votes == 1
        assert result.final_signal in [SignalType.BUY, SignalType.HOLD]

    def test_calculate_consensus_unanimous_buy(self):
        """Test consensus with unanimous buy signals."""
        consensus = ConsensusAlgorithm()
        responses = [
            AgentResponse(
                agent_id=f"agent_{i}",
                agent_name=f"Agent {i}",
                ticker="TEST",
                signal=SignalType.BUY,
                confidence=ConfidenceLevel.HIGH,
                reasoning="Test reasoning",
                key_factors=["Factor 1"],
                risks=["Risk 1"],
            )
            for i in range(5)
        ]

        result = consensus.calculate_consensus(
            ticker="TEST",
            agent_responses=responses,
        )

        assert result.final_signal == SignalType.BUY
        assert result.buy_votes == 5
        assert result.sell_votes == 0
        assert result.hold_votes == 0
        assert result.confidence in [ConfidenceLevel.VERY_HIGH, ConfidenceLevel.HIGH]
        assert len(result.dissenters) == 0

    def test_calculate_consensus_unanimous_sell(self):
        """Test consensus with unanimous sell signals."""
        consensus = ConsensusAlgorithm()
        responses = [
            AgentResponse(
                agent_id=f"agent_{i}",
                agent_name=f"Agent {i}",
                ticker="TEST",
                signal=SignalType.STRONG_SELL,
                confidence=ConfidenceLevel.VERY_HIGH,
                reasoning="Test reasoning",
                key_factors=["Factor 1"],
                risks=["Risk 1"],
            )
            for i in range(5)
        ]

        result = consensus.calculate_consensus(
            ticker="TEST",
            agent_responses=responses,
        )

        assert result.final_signal == SignalType.STRONG_SELL
        assert result.sell_votes == 5
        assert result.weighted_score <= Decimal("-60")

    def test_calculate_consensus_identifies_dissenters(self, sample_agent_responses):
        """Test that dissenters are correctly identified."""
        consensus = ConsensusAlgorithm()
        result = consensus.calculate_consensus(
            ticker="AAPL",
            agent_responses=sample_agent_responses,
        )

        # Burry with SELL signal should be a dissenter if consensus is BUY
        if result.final_signal.is_bullish:
            assert "Michael Burry" in result.dissenters

    def test_calculate_consensus_extracts_themes(self, sample_agent_responses):
        """Test that key themes are extracted."""
        consensus = ConsensusAlgorithm()
        result = consensus.calculate_consensus(
            ticker="AAPL",
            agent_responses=sample_agent_responses,
        )

        assert len(result.key_themes) > 0

    def test_calculate_consensus_extracts_risks(self, sample_agent_responses):
        """Test that risks are extracted."""
        consensus = ConsensusAlgorithm()
        result = consensus.calculate_consensus(
            ticker="AAPL",
            agent_responses=sample_agent_responses,
        )

        assert len(result.primary_risks) > 0

    def test_calculate_consensus_no_responses_raises_error(self):
        """Test that empty responses raises an error."""
        consensus = ConsensusAlgorithm()

        with pytest.raises(Exception):
            consensus.calculate_consensus(
                ticker="TEST",
                agent_responses=[],
            )

    def test_weighted_score_calculation(self):
        """Test that weighted scores are calculated correctly."""
        consensus = ConsensusAlgorithm()

        # Create responses with known signals and confidences
        responses = [
            AgentResponse(
                agent_id="agent_1",
                agent_name="Agent 1",
                ticker="TEST",
                signal=SignalType.STRONG_BUY,  # +100
                confidence=ConfidenceLevel.VERY_HIGH,  # 1.0 multiplier
                reasoning="Test",
                key_factors=["Factor"],
                risks=["Risk"],
            ),
            AgentResponse(
                agent_id="agent_2",
                agent_name="Agent 2",
                ticker="TEST",
                signal=SignalType.STRONG_SELL,  # -100
                confidence=ConfidenceLevel.VERY_HIGH,  # 1.0 multiplier
                reasoning="Test",
                key_factors=["Factor"],
                risks=["Risk"],
            ),
        ]

        result = consensus.calculate_consensus(
            ticker="TEST",
            agent_responses=responses,
        )

        # With equal weights and opposite signals, should be near 0 (HOLD)
        assert result.final_signal == SignalType.HOLD
        assert abs(result.weighted_score) < Decimal("20")

    def test_confidence_affects_weight(self):
        """Test that confidence affects the weighted score."""
        consensus = ConsensusAlgorithm()

        # High confidence BUY vs low confidence SELL
        responses = [
            AgentResponse(
                agent_id="agent_1",
                agent_name="Agent 1",
                ticker="TEST",
                signal=SignalType.BUY,  # +50
                confidence=ConfidenceLevel.VERY_HIGH,  # 1.0 multiplier
                reasoning="Test",
                key_factors=["Factor"],
                risks=["Risk"],
            ),
            AgentResponse(
                agent_id="agent_2",
                agent_name="Agent 2",
                ticker="TEST",
                signal=SignalType.SELL,  # -50
                confidence=ConfidenceLevel.VERY_LOW,  # 0.3 multiplier
                reasoning="Test",
                key_factors=["Factor"],
                risks=["Risk"],
            ),
        ]

        result = consensus.calculate_consensus(
            ticker="TEST",
            agent_responses=responses,
        )

        # High confidence BUY should outweigh low confidence SELL
        assert result.weighted_score > Decimal("0")
