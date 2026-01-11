"""Core enumerations for Consilium."""

from enum import Enum


class SignalType(str, Enum):
    """Investment signal recommendation."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"

    def __str__(self) -> str:
        return self.value

    @property
    def is_bullish(self) -> bool:
        """Check if signal is bullish."""
        return self in (SignalType.STRONG_BUY, SignalType.BUY)

    @property
    def is_bearish(self) -> bool:
        """Check if signal is bearish."""
        return self in (SignalType.STRONG_SELL, SignalType.SELL)

    @property
    def score(self) -> int:
        """Numeric score for the signal."""
        scores = {
            SignalType.STRONG_BUY: 100,
            SignalType.BUY: 50,
            SignalType.HOLD: 0,
            SignalType.SELL: -50,
            SignalType.STRONG_SELL: -100,
        }
        return scores[self]


class ConfidenceLevel(str, Enum):
    """Confidence in analysis."""

    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"

    def __str__(self) -> str:
        return self.value

    @property
    def multiplier(self) -> float:
        """Confidence multiplier for weighted calculations."""
        multipliers = {
            ConfidenceLevel.VERY_HIGH: 1.0,
            ConfidenceLevel.HIGH: 0.85,
            ConfidenceLevel.MEDIUM: 0.7,
            ConfidenceLevel.LOW: 0.5,
            ConfidenceLevel.VERY_LOW: 0.3,
        }
        return multipliers[self]


class AssetClass(str, Enum):
    """Asset classification."""

    EQUITY = "EQUITY"
    ETF = "ETF"
    INDEX = "INDEX"
    CRYPTO = "CRYPTO"
    COMMODITY = "COMMODITY"

    def __str__(self) -> str:
        return self.value


class AgentType(str, Enum):
    """Agent classification."""

    INVESTOR = "INVESTOR"
    SPECIALIST = "SPECIALIST"

    def __str__(self) -> str:
        return self.value


class InvestmentStyle(str, Enum):
    """Investor's primary investment style."""

    VALUE = "VALUE"
    GROWTH = "GROWTH"
    MOMENTUM = "MOMENTUM"
    CONTRARIAN = "CONTRARIAN"
    MACRO = "MACRO"
    QUALITY = "QUALITY"
    ACTIVIST = "ACTIVIST"
    QUANTITATIVE = "QUANTITATIVE"

    def __str__(self) -> str:
        return self.value


class DataType(str, Enum):
    """Types of market data for caching."""

    PRICE = "price"
    FUNDAMENTALS = "fundamentals"
    TECHNICALS = "technicals"
    INFO = "info"

    def __str__(self) -> str:
        return self.value
