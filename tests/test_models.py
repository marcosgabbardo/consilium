"""Tests for core data models."""

from decimal import Decimal
from datetime import datetime
import pytest

from consilium.core.enums import SignalType, ConfidenceLevel, AssetClass
from consilium.core.models import (
    Stock,
    StockPrice,
    Fundamentals,
    Technicals,
    CompanyInfo,
    AgentResponse,
    ConsensusResult,
    AnalysisRequest,
)


class TestEnums:
    """Test suite for enums."""

    def test_signal_type_scores(self):
        """Test that signal types have correct scores."""
        assert SignalType.STRONG_BUY.score == 100
        assert SignalType.BUY.score == 50
        assert SignalType.HOLD.score == 0
        assert SignalType.SELL.score == -50
        assert SignalType.STRONG_SELL.score == -100

    def test_signal_type_is_bullish(self):
        """Test bullish signal detection."""
        assert SignalType.STRONG_BUY.is_bullish
        assert SignalType.BUY.is_bullish
        assert not SignalType.HOLD.is_bullish
        assert not SignalType.SELL.is_bullish
        assert not SignalType.STRONG_SELL.is_bullish

    def test_signal_type_is_bearish(self):
        """Test bearish signal detection."""
        assert not SignalType.STRONG_BUY.is_bearish
        assert not SignalType.BUY.is_bearish
        assert not SignalType.HOLD.is_bearish
        assert SignalType.SELL.is_bearish
        assert SignalType.STRONG_SELL.is_bearish

    def test_confidence_multipliers(self):
        """Test that confidence levels have correct multipliers."""
        assert ConfidenceLevel.VERY_HIGH.multiplier == 1.0
        assert ConfidenceLevel.HIGH.multiplier == 0.85
        assert ConfidenceLevel.MEDIUM.multiplier == 0.7
        assert ConfidenceLevel.LOW.multiplier == 0.5
        assert ConfidenceLevel.VERY_LOW.multiplier == 0.3


class TestStockModels:
    """Test suite for stock-related models."""

    def test_stock_ticker_uppercase(self):
        """Test that ticker is converted to uppercase."""
        stock = Stock(
            ticker="aapl",
            company=CompanyInfo(name="Apple"),
            price=StockPrice(
                current=Decimal("180"),
                open=Decimal("178"),
                high=Decimal("182"),
                low=Decimal("177"),
                close=Decimal("179"),
                volume=50000000,
                change_percent=Decimal("0.5"),
                fifty_two_week_high=Decimal("200"),
                fifty_two_week_low=Decimal("140"),
            ),
            fundamentals=Fundamentals(),
            technicals=Technicals(),
        )
        assert stock.ticker == "AAPL"

    def test_stock_price_52w_calculations(self):
        """Test 52-week price calculations."""
        price = StockPrice(
            current=Decimal("180"),
            open=Decimal("178"),
            high=Decimal("182"),
            low=Decimal("177"),
            close=Decimal("179"),
            volume=50000000,
            change_percent=Decimal("0.5"),
            fifty_two_week_high=Decimal("200"),
            fifty_two_week_low=Decimal("140"),
        )

        # 180 is 10% below 200
        assert price.from_52w_high_pct == Decimal("10")

        # 180 is ~28.57% above 140
        expected_from_low = ((Decimal("180") - Decimal("140")) / Decimal("140")) * 100
        assert price.from_52w_low_pct == expected_from_low

    def test_technicals_trend_bullish(self):
        """Test bullish trend detection."""
        tech = Technicals(
            sma_50=Decimal("180"),
            sma_200=Decimal("160"),
        )
        assert tech.trend == "BULLISH"

    def test_technicals_trend_bearish(self):
        """Test bearish trend detection."""
        tech = Technicals(
            sma_50=Decimal("160"),
            sma_200=Decimal("180"),
        )
        assert tech.trend == "BEARISH"


class TestAgentResponse:
    """Test suite for AgentResponse model."""

    def test_agent_response_weighted_score(self):
        """Test weighted score calculation."""
        response = AgentResponse(
            agent_id="test",
            agent_name="Test Agent",
            ticker="TEST",
            signal=SignalType.BUY,  # +50
            confidence=ConfidenceLevel.HIGH,  # 0.85
            reasoning="Test",
            key_factors=["Factor"],
            risks=["Risk"],
        )

        expected = Decimal("50") * Decimal("0.85")
        assert response.weighted_score == expected


class TestConsensusResult:
    """Test suite for ConsensusResult model."""

    def test_consensus_total_votes(self, sample_agent_responses):
        """Test total votes calculation."""
        result = ConsensusResult(
            ticker="AAPL",
            final_signal=SignalType.BUY,
            signal_score=Decimal("30"),
            confidence=ConfidenceLevel.MEDIUM,
            buy_votes=2,
            sell_votes=1,
            hold_votes=1,
            weighted_score=Decimal("30"),
            agent_responses=sample_agent_responses,
            consensus_reasoning="Test reasoning",
        )

        assert result.total_votes == 4

    def test_consensus_agreement_ratio(self, sample_agent_responses):
        """Test agreement ratio calculation."""
        result = ConsensusResult(
            ticker="AAPL",
            final_signal=SignalType.BUY,
            signal_score=Decimal("30"),
            confidence=ConfidenceLevel.MEDIUM,
            buy_votes=2,
            sell_votes=1,
            hold_votes=1,
            weighted_score=Decimal("30"),
            agent_responses=sample_agent_responses,
            dissenters=["Agent 1"],
            consensus_reasoning="Test reasoning",
        )

        # 4 total, 1 dissenter = 3/4 = 0.75
        assert result.agreement_ratio == Decimal("0.75")


class TestAnalysisRequest:
    """Test suite for AnalysisRequest model."""

    def test_tickers_normalized(self):
        """Test that tickers are normalized to uppercase."""
        request = AnalysisRequest(
            tickers=["aapl", "  nvda  ", "MSFT"],
        )
        assert request.tickers == ["AAPL", "NVDA", "MSFT"]

    def test_empty_tickers_filtered(self):
        """Test that empty tickers are filtered out."""
        request = AnalysisRequest(
            tickers=["AAPL", "", "  ", "NVDA"],
        )
        assert request.tickers == ["AAPL", "NVDA"]
