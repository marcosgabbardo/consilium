"""Pytest fixtures for Consilium tests."""

from decimal import Decimal
from datetime import datetime
import pytest

from consilium.core.enums import SignalType, ConfidenceLevel, AgentType, InvestmentStyle
from consilium.core.models import (
    AgentResponse,
    AgentProfile,
    SpecialistReport,
    Stock,
    StockPrice,
    Fundamentals,
    Technicals,
    CompanyInfo,
)


@pytest.fixture
def sample_agent_responses() -> list[AgentResponse]:
    """Create sample agent responses for testing."""
    return [
        AgentResponse(
            agent_id="buffett",
            agent_name="Warren Buffett",
            ticker="AAPL",
            signal=SignalType.BUY,
            confidence=ConfidenceLevel.HIGH,
            target_price=Decimal("200.00"),
            reasoning="Strong moat, quality management, reasonable valuation.",
            key_factors=["Strong brand", "Services growth", "Cash generation"],
            risks=["China exposure", "Regulatory risk"],
            time_horizon="3-5 years",
        ),
        AgentResponse(
            agent_id="munger",
            agent_name="Charlie Munger",
            ticker="AAPL",
            signal=SignalType.BUY,
            confidence=ConfidenceLevel.HIGH,
            target_price=Decimal("195.00"),
            reasoning="Wonderful business at a fair price.",
            key_factors=["Ecosystem lock-in", "Management quality", "Capital allocation"],
            risks=["Smartphone saturation", "Competition"],
            time_horizon="5+ years",
        ),
        AgentResponse(
            agent_id="graham",
            agent_name="Ben Graham",
            ticker="AAPL",
            signal=SignalType.HOLD,
            confidence=ConfidenceLevel.MEDIUM,
            target_price=Decimal("170.00"),
            reasoning="Valuation stretched by classic metrics.",
            key_factors=["P/E above historical average", "Strong balance sheet"],
            risks=["Multiple compression", "Growth slowdown"],
            time_horizon="1-2 years",
        ),
        AgentResponse(
            agent_id="burry",
            agent_name="Michael Burry",
            ticker="AAPL",
            signal=SignalType.SELL,
            confidence=ConfidenceLevel.MEDIUM,
            target_price=Decimal("140.00"),
            reasoning="Overvalued relative to growth. Market too optimistic.",
            key_factors=["Peak margins", "China risk"],
            risks=["Could stay overvalued longer", "Innovation catalyst"],
            time_horizon="6-12 months",
        ),
    ]


@pytest.fixture
def sample_specialist_reports() -> list[SpecialistReport]:
    """Create sample specialist reports for testing."""
    return [
        SpecialistReport(
            specialist_id="valuation",
            specialist_name="Valuation Specialist",
            ticker="AAPL",
            summary="Trading at premium to historical averages but justified by quality.",
            metrics={"pe_vs_sector": "Premium", "fair_value": 185},
            analysis="Detailed valuation analysis...",
            score=Decimal("65"),
        ),
        SpecialistReport(
            specialist_id="fundamentals",
            specialist_name="Fundamentals Specialist",
            ticker="AAPL",
            summary="Excellent business quality with strong moat.",
            metrics={"moat": "Wide", "quality_score": 90},
            analysis="Detailed fundamentals analysis...",
            score=Decimal("85"),
        ),
    ]


@pytest.fixture
def sample_stock() -> Stock:
    """Create a sample stock for testing."""
    return Stock(
        ticker="AAPL",
        company=CompanyInfo(
            name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            description="Apple designs and manufactures consumer electronics.",
            country="United States",
            exchange="NASDAQ",
        ),
        price=StockPrice(
            current=Decimal("180.00"),
            open=Decimal("178.00"),
            high=Decimal("182.00"),
            low=Decimal("177.50"),
            close=Decimal("179.00"),
            volume=50000000,
            change_percent=Decimal("0.56"),
            fifty_two_week_high=Decimal("199.00"),
            fifty_two_week_low=Decimal("140.00"),
        ),
        fundamentals=Fundamentals(
            market_cap=Decimal("2800000000000"),
            pe_ratio=Decimal("28.5"),
            forward_pe=Decimal("25.0"),
            profit_margin=Decimal("0.25"),
            roe=Decimal("0.50"),
            debt_to_equity=Decimal("1.5"),
        ),
        technicals=Technicals(
            sma_50=Decimal("175.00"),
            sma_200=Decimal("165.00"),
            rsi_14=Decimal("55"),
        ),
    )


@pytest.fixture
def sample_agent_profile() -> AgentProfile:
    """Create a sample agent profile for testing."""
    return AgentProfile(
        id="buffett",
        name="Warren Buffett",
        agent_type=AgentType.INVESTOR,
        investment_style=InvestmentStyle.VALUE,
        weight=Decimal("2.0"),
        description="The Oracle of Omaha",
        enabled=True,
    )
