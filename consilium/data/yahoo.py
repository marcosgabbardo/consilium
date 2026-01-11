"""Yahoo Finance data provider implementation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from functools import partial
from typing import Any

import yfinance as yf

from consilium.core.enums import AssetClass
from consilium.core.exceptions import DataFetchError
from consilium.core.models import (
    Stock,
    StockPrice,
    Fundamentals,
    Technicals,
    CompanyInfo,
)


def _safe_decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    """Safely convert value to Decimal."""
    if value is None:
        return default
    try:
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        return Decimal(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    """Safely convert value to int."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class YahooFinanceProvider:
    """Yahoo Finance data provider using yfinance library."""

    def __init__(self, executor: ThreadPoolExecutor | None = None) -> None:
        self._executor = executor or ThreadPoolExecutor(max_workers=5)

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous yfinance calls in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, partial(func, *args, **kwargs)
        )

    def _fetch_ticker_data(self, ticker: str) -> tuple[dict[str, Any], Any]:
        """Synchronous fetch of ticker data."""
        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info
            history = yf_ticker.history(period="1y")
            return info, history
        except Exception as e:
            raise DataFetchError(
                f"Failed to fetch data for {ticker}: {e}",
                ticker=ticker,
                source="yahoo_finance",
            ) from e

    async def get_stock(self, ticker: str) -> Stock:
        """Get complete stock data including price, fundamentals, and technicals."""
        ticker = ticker.upper().strip()

        # Fetch data in background thread
        info, history = await self._run_sync(self._fetch_ticker_data, ticker)

        if not info or info.get("regularMarketPrice") is None:
            raise DataFetchError(
                f"No data available for ticker {ticker}",
                ticker=ticker,
                source="yahoo_finance",
            )

        # Parse all components
        company = self._parse_company_info(info)
        price = self._parse_price(info)
        fundamentals = self._parse_fundamentals(info)
        technicals = self._calculate_technicals(history, info)

        # Determine asset class
        quote_type = info.get("quoteType", "").upper()
        asset_class = AssetClass.EQUITY
        if quote_type == "ETF":
            asset_class = AssetClass.ETF
        elif quote_type == "INDEX":
            asset_class = AssetClass.INDEX
        elif quote_type == "CRYPTOCURRENCY":
            asset_class = AssetClass.CRYPTO

        return Stock(
            ticker=ticker,
            asset_class=asset_class,
            company=company,
            price=price,
            fundamentals=fundamentals,
            technicals=technicals,
        )

    async def get_price(self, ticker: str) -> StockPrice:
        """Get current price data for a ticker."""
        info, _ = await self._run_sync(self._fetch_ticker_data, ticker)
        return self._parse_price(info)

    async def get_fundamentals(self, ticker: str) -> Fundamentals:
        """Get fundamental metrics for a ticker."""
        info, _ = await self._run_sync(self._fetch_ticker_data, ticker)
        return self._parse_fundamentals(info)

    async def get_technicals(self, ticker: str) -> Technicals:
        """Get technical indicators for a ticker."""
        info, history = await self._run_sync(self._fetch_ticker_data, ticker)
        return self._calculate_technicals(history, info)

    async def get_company_info(self, ticker: str) -> CompanyInfo:
        """Get company metadata for a ticker."""
        info, _ = await self._run_sync(self._fetch_ticker_data, ticker)
        return self._parse_company_info(info)

    async def is_valid_ticker(self, ticker: str) -> bool:
        """Check if a ticker symbol is valid."""
        try:
            info, _ = await self._run_sync(self._fetch_ticker_data, ticker)
            return info.get("regularMarketPrice") is not None
        except DataFetchError:
            return False

    def _parse_company_info(self, info: dict[str, Any]) -> CompanyInfo:
        """Parse company information from yfinance info dict."""
        return CompanyInfo(
            name=info.get("shortName") or info.get("longName") or "Unknown",
            sector=info.get("sector"),
            industry=info.get("industry"),
            description=info.get("longBusinessSummary"),
            website=info.get("website"),
            employees=_safe_int(info.get("fullTimeEmployees")),
            country=info.get("country"),
            exchange=info.get("exchange"),
            currency=info.get("currency", "USD"),
        )

    def _parse_price(self, info: dict[str, Any]) -> StockPrice:
        """Parse price data from yfinance info dict."""
        current = _safe_decimal(info.get("regularMarketPrice"), Decimal("0"))

        return StockPrice(
            current=current,
            open=_safe_decimal(info.get("regularMarketOpen"), current),
            high=_safe_decimal(info.get("regularMarketDayHigh"), current),
            low=_safe_decimal(info.get("regularMarketDayLow"), current),
            close=_safe_decimal(info.get("previousClose"), current),
            volume=_safe_int(info.get("regularMarketVolume"), 0),
            change_percent=_safe_decimal(
                info.get("regularMarketChangePercent"), Decimal("0")
            ),
            fifty_two_week_high=_safe_decimal(
                info.get("fiftyTwoWeekHigh"), current
            ),
            fifty_two_week_low=_safe_decimal(
                info.get("fiftyTwoWeekLow"), current
            ),
        )

    def _parse_fundamentals(self, info: dict[str, Any]) -> Fundamentals:
        """Parse fundamental metrics from yfinance info dict."""
        return Fundamentals(
            market_cap=_safe_decimal(info.get("marketCap")),
            pe_ratio=_safe_decimal(info.get("trailingPE")),
            forward_pe=_safe_decimal(info.get("forwardPE")),
            peg_ratio=_safe_decimal(info.get("pegRatio")),
            price_to_book=_safe_decimal(info.get("priceToBook")),
            price_to_sales=_safe_decimal(info.get("priceToSalesTrailing12Months")),
            enterprise_value=_safe_decimal(info.get("enterpriseValue")),
            ev_to_ebitda=_safe_decimal(info.get("enterpriseToEbitda")),
            ev_to_revenue=_safe_decimal(info.get("enterpriseToRevenue")),
            profit_margin=_safe_decimal(info.get("profitMargins")),
            operating_margin=_safe_decimal(info.get("operatingMargins")),
            gross_margin=_safe_decimal(info.get("grossMargins")),
            roe=_safe_decimal(info.get("returnOnEquity")),
            roa=_safe_decimal(info.get("returnOnAssets")),
            debt_to_equity=_safe_decimal(info.get("debtToEquity")),
            current_ratio=_safe_decimal(info.get("currentRatio")),
            quick_ratio=_safe_decimal(info.get("quickRatio")),
            revenue=_safe_decimal(info.get("totalRevenue")),
            revenue_growth=_safe_decimal(info.get("revenueGrowth")),
            earnings_growth=_safe_decimal(info.get("earningsGrowth")),
            free_cash_flow=_safe_decimal(info.get("freeCashflow")),
            operating_cash_flow=_safe_decimal(info.get("operatingCashflow")),
            dividend_yield=_safe_decimal(info.get("dividendYield")),
            payout_ratio=_safe_decimal(info.get("payoutRatio")),
            beta=_safe_decimal(info.get("beta")),
            shares_outstanding=_safe_int(info.get("sharesOutstanding")),
        )

    def _calculate_technicals(
        self, history: Any, info: dict[str, Any]
    ) -> Technicals:
        """Calculate technical indicators from price history."""
        if history is None or history.empty:
            return Technicals()

        close = history["Close"]
        volume = history["Volume"]
        high = history["High"]
        low = history["Low"]

        # Simple Moving Averages
        sma_20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
        sma_50 = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else None
        sma_200 = close.rolling(window=200).mean().iloc[-1] if len(close) >= 200 else None

        # Exponential Moving Averages
        ema_12 = close.ewm(span=12, adjust=False).mean().iloc[-1] if len(close) >= 12 else None
        ema_26 = close.ewm(span=26, adjust=False).mean().iloc[-1] if len(close) >= 26 else None

        # RSI (14-day)
        rsi_14 = None
        if len(close) >= 15:
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_14 = rsi.iloc[-1] if not rsi.empty else None

        # MACD
        macd = None
        macd_signal = None
        macd_histogram = None
        if ema_12 is not None and ema_26 is not None:
            macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd = macd_line.iloc[-1]
            macd_signal = signal_line.iloc[-1]
            macd_histogram = macd - macd_signal

        # Bollinger Bands
        bollinger_middle = sma_20
        bollinger_upper = None
        bollinger_lower = None
        if sma_20 is not None and len(close) >= 20:
            std_20 = close.rolling(window=20).std().iloc[-1]
            bollinger_upper = sma_20 + (2 * std_20)
            bollinger_lower = sma_20 - (2 * std_20)

        # ATR (14-day)
        atr_14 = None
        if len(close) >= 15:
            tr = high - low
            tr = tr.combine(abs(high - close.shift()), max)
            tr = tr.combine(abs(low - close.shift()), max)
            atr_14 = tr.rolling(window=14).mean().iloc[-1]

        # Volume SMA
        volume_sma_20 = None
        relative_volume = None
        if len(volume) >= 20:
            volume_sma_20 = int(volume.rolling(window=20).mean().iloc[-1])
            if volume_sma_20 > 0:
                relative_volume = Decimal(str(volume.iloc[-1] / volume_sma_20))

        return Technicals(
            sma_20=_safe_decimal(sma_20),
            sma_50=_safe_decimal(sma_50),
            sma_200=_safe_decimal(sma_200),
            ema_12=_safe_decimal(ema_12),
            ema_26=_safe_decimal(ema_26),
            rsi_14=_safe_decimal(rsi_14),
            macd=_safe_decimal(macd),
            macd_signal=_safe_decimal(macd_signal),
            macd_histogram=_safe_decimal(macd_histogram),
            bollinger_upper=_safe_decimal(bollinger_upper),
            bollinger_middle=_safe_decimal(bollinger_middle),
            bollinger_lower=_safe_decimal(bollinger_lower),
            atr_14=_safe_decimal(atr_14),
            volume_sma_20=volume_sma_20,
            relative_volume=relative_volume,
        )
