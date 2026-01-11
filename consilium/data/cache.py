"""Cached data provider using cache-aside pattern."""

from typing import Any

from consilium.core.models import Stock, StockPrice, Fundamentals, Technicals, CompanyInfo
from consilium.data.yahoo import YahooFinanceProvider
from consilium.db.connection import DatabasePool
from consilium.db.repository import CacheRepository


class CachedDataProvider:
    """
    Data provider wrapper with MySQL caching using cache-aside pattern.

    Cache-aside pattern:
    1. Check cache first
    2. On miss, fetch from provider
    3. Store in cache with TTL
    4. Return data
    """

    def __init__(
        self,
        provider: YahooFinanceProvider,
        pool: DatabasePool,
    ) -> None:
        self._provider = provider
        self._cache = CacheRepository(pool)

    async def get_stock(self, ticker: str, bypass_cache: bool = False) -> Stock:
        """Get complete stock data with caching."""
        ticker = ticker.upper().strip()

        if not bypass_cache:
            # Try to get all components from cache
            cached_info = await self._cache.get_cached(ticker, "info")
            cached_price = await self._cache.get_cached(ticker, "price")
            cached_fundamentals = await self._cache.get_cached(ticker, "fundamentals")
            cached_technicals = await self._cache.get_cached(ticker, "technicals")

            if all([cached_info, cached_price, cached_fundamentals, cached_technicals]):
                # Reconstruct Stock from cached data
                return Stock(
                    ticker=ticker,
                    asset_class=cached_info.get("asset_class", "EQUITY"),
                    company=CompanyInfo(**cached_info["company"]),
                    price=StockPrice(**cached_price),
                    fundamentals=Fundamentals(**cached_fundamentals),
                    technicals=Technicals(**cached_technicals),
                )

        # Cache miss or bypass - fetch fresh data
        stock = await self._provider.get_stock(ticker)

        # Cache all components
        await self._cache_stock(stock)

        return stock

    async def _cache_stock(self, stock: Stock) -> None:
        """Cache all components of a stock."""
        ticker = stock.ticker

        # Cache company info (longest TTL)
        await self._cache.set_cached(
            ticker,
            "info",
            {
                "asset_class": stock.asset_class.value,
                "company": stock.company.model_dump(),
            },
        )

        # Cache price data (shortest TTL)
        await self._cache.set_cached(
            ticker,
            "price",
            stock.price.model_dump(),
        )

        # Cache fundamentals
        await self._cache.set_cached(
            ticker,
            "fundamentals",
            stock.fundamentals.model_dump(),
        )

        # Cache technicals
        await self._cache.set_cached(
            ticker,
            "technicals",
            stock.technicals.model_dump(),
        )

    async def get_price(self, ticker: str, bypass_cache: bool = False) -> StockPrice:
        """Get price data with caching."""
        ticker = ticker.upper().strip()

        if not bypass_cache:
            cached = await self._cache.get_cached(ticker, "price")
            if cached:
                return StockPrice(**cached)

        price = await self._provider.get_price(ticker)
        await self._cache.set_cached(ticker, "price", price.model_dump())
        return price

    async def get_fundamentals(
        self, ticker: str, bypass_cache: bool = False
    ) -> Fundamentals:
        """Get fundamentals with caching."""
        ticker = ticker.upper().strip()

        if not bypass_cache:
            cached = await self._cache.get_cached(ticker, "fundamentals")
            if cached:
                return Fundamentals(**cached)

        fundamentals = await self._provider.get_fundamentals(ticker)
        await self._cache.set_cached(ticker, "fundamentals", fundamentals.model_dump())
        return fundamentals

    async def get_technicals(
        self, ticker: str, bypass_cache: bool = False
    ) -> Technicals:
        """Get technicals with caching."""
        ticker = ticker.upper().strip()

        if not bypass_cache:
            cached = await self._cache.get_cached(ticker, "technicals")
            if cached:
                return Technicals(**cached)

        technicals = await self._provider.get_technicals(ticker)
        await self._cache.set_cached(ticker, "technicals", technicals.model_dump())
        return technicals

    async def get_company_info(
        self, ticker: str, bypass_cache: bool = False
    ) -> CompanyInfo:
        """Get company info with caching."""
        ticker = ticker.upper().strip()

        if not bypass_cache:
            cached = await self._cache.get_cached(ticker, "info")
            if cached and "company" in cached:
                return CompanyInfo(**cached["company"])

        info = await self._provider.get_company_info(ticker)
        await self._cache.set_cached(ticker, "info", {"company": info.model_dump()})
        return info

    async def invalidate(self, ticker: str) -> None:
        """Invalidate all cached data for a ticker."""
        await self._cache.invalidate(ticker)

    async def is_valid_ticker(self, ticker: str) -> bool:
        """Check if a ticker is valid."""
        return await self._provider.is_valid_ticker(ticker)
