"""Abstract data provider protocol."""

from abc import ABC, abstractmethod
from typing import Protocol

from consilium.core.models import Stock, StockPrice, Fundamentals, Technicals, CompanyInfo


class DataProvider(Protocol):
    """Protocol for market data providers."""

    async def get_stock(self, ticker: str) -> Stock:
        """Get complete stock data including price, fundamentals, and technicals."""
        ...

    async def get_price(self, ticker: str) -> StockPrice:
        """Get current price data for a ticker."""
        ...

    async def get_fundamentals(self, ticker: str) -> Fundamentals:
        """Get fundamental metrics for a ticker."""
        ...

    async def get_technicals(self, ticker: str) -> Technicals:
        """Get technical indicators for a ticker."""
        ...

    async def get_company_info(self, ticker: str) -> CompanyInfo:
        """Get company metadata for a ticker."""
        ...

    async def is_valid_ticker(self, ticker: str) -> bool:
        """Check if a ticker symbol is valid."""
        ...
