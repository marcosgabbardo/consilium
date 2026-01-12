"""Historical data provider for point-in-time analysis."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import yfinance as yf

from consilium.core.enums import AssetClass
from datetime import datetime as dt

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


class HistoricalDataProvider:
    """
    Provides stock data as of a specific historical date (point-in-time).

    This provider fetches historical price data and calculates technical
    indicators using only data available up to the specified date,
    avoiding look-ahead bias in backtesting.
    """

    def __init__(self, executor: ThreadPoolExecutor | None = None) -> None:
        self._executor = executor or ThreadPoolExecutor(max_workers=5)

    async def get_stock_as_of(self, ticker: str, as_of_date: date) -> Stock:
        """
        Get stock data as it would have appeared on a specific date.

        Uses only data available up to as_of_date to avoid look-ahead bias.

        Args:
            ticker: Stock ticker symbol
            as_of_date: The historical date to analyze as of

        Returns:
            Stock object with point-in-time data
        """
        ticker = ticker.upper().strip()
        loop = asyncio.get_event_loop()

        def fetch_historical():
            yf_ticker = yf.Ticker(ticker)

            # Fetch 1 year of history ending at as_of_date
            start = as_of_date - timedelta(days=400)  # Extra buffer for 200-day SMA
            end = as_of_date + timedelta(days=1)  # Include as_of_date

            history = yf_ticker.history(start=start.isoformat(), end=end.isoformat())
            info = yf_ticker.info  # Current info for company metadata

            return history, info

        history, info = await loop.run_in_executor(self._executor, fetch_historical)

        if history.empty:
            raise ValueError(f"No historical data for {ticker} as of {as_of_date}")

        # Get the last available row (on or before as_of_date)
        last_row = history.iloc[-1]
        actual_date = history.index[-1].date()

        # Build Stock with historical data
        price = self._parse_historical_price(last_row, history)
        technicals = self._calculate_historical_technicals(history)
        company = self._parse_company_info(info, ticker)
        fundamentals = self._parse_fundamentals(info)

        # Determine asset class
        quote_type = info.get("quoteType", "").upper()
        asset_class = AssetClass.EQUITY
        if quote_type == "ETF":
            asset_class = AssetClass.ETF
        elif quote_type == "INDEX":
            asset_class = AssetClass.INDEX

        return Stock(
            ticker=ticker,
            asset_class=asset_class,
            company=company,
            price=price,
            fundamentals=fundamentals,
            technicals=technicals,
            fetched_at=dt.combine(actual_date, dt.min.time()),
        )

    def _parse_historical_price(self, row: Any, history: Any) -> StockPrice:
        """Parse price data from historical row."""
        current = _safe_decimal(row["Close"], Decimal("0"))

        # Calculate 52-week high/low from available history
        if len(history) >= 252:
            last_252 = history.tail(252)
            high_52w = _safe_decimal(last_252["High"].max(), current)
            low_52w = _safe_decimal(last_252["Low"].min(), current)
        else:
            high_52w = _safe_decimal(history["High"].max(), current)
            low_52w = _safe_decimal(history["Low"].min(), current)

        # Calculate change percent from previous close
        if len(history) >= 2:
            prev_close = history.iloc[-2]["Close"]
            change_pct = ((row["Close"] - prev_close) / prev_close) * 100
        else:
            change_pct = Decimal("0")

        return StockPrice(
            current=current,
            open=_safe_decimal(row["Open"], current),
            high=_safe_decimal(row["High"], current),
            low=_safe_decimal(row["Low"], current),
            close=current,
            volume=_safe_int(row["Volume"], 0),
            change_percent=_safe_decimal(change_pct, Decimal("0")),
            fifty_two_week_high=high_52w,
            fifty_two_week_low=low_52w,
        )

    def _parse_company_info(self, info: dict[str, Any], ticker: str) -> CompanyInfo:
        """Parse company information from yfinance info dict."""
        return CompanyInfo(
            name=info.get("shortName") or info.get("longName") or ticker,
            sector=info.get("sector"),
            industry=info.get("industry"),
            description=info.get("longBusinessSummary"),
            website=info.get("website"),
            employees=_safe_int(info.get("fullTimeEmployees")),
            country=info.get("country"),
            exchange=info.get("exchange"),
            currency=info.get("currency", "USD"),
        )

    def _parse_fundamentals(self, info: dict[str, Any]) -> Fundamentals:
        """
        Parse fundamental metrics from yfinance info dict.

        Note: This uses current fundamentals as a limitation.
        Historical fundamentals would require paid data sources.
        """
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

    def _calculate_historical_technicals(self, history: Any) -> Technicals:
        """
        Calculate technical indicators from historical price data.

        Uses only data available in the history DataFrame to avoid
        look-ahead bias.
        """
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
