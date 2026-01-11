"""Stock universe data providers.

Provides access to predefined stock universes like S&P 500, NASDAQ 100, etc.
Uses PyTickerSymbols for fetching index constituents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pytickersymbols import PyTickerSymbols


@dataclass
class UniverseData:
    """Represents a stock universe with tickers and metadata."""

    name: str
    tickers: list[str]
    description: str
    source_url: str | None = None


class UniverseDataProvider:
    """Fetches stock universe data from external sources."""

    # Built-in universes that don't need external API
    BUILTIN_UNIVERSES: dict[str, dict[str, Any]] = {
        "mag7": {
            "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
            "description": "Magnificent 7 - Tech megacaps",
            "source_url": None,
        },
        "brazilian": {
            "tickers": [
                "PETR3.SA", "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA",
                "B3SA3.SA", "ABEV3.SA", "WEGE3.SA", "RENT3.SA", "SUZB3.SA",
                "JBSS3.SA", "RADL3.SA", "RAIL3.SA", "BBAS3.SA", "ELET3.SA",
                "LREN3.SA", "HAPV3.SA", "BBSE3.SA", "CSAN3.SA", "VIVT3.SA",
            ],
            "description": "Top Brazilian stocks (B3 exchange)",
            "source_url": "https://www.b3.com.br",
        },
    }

    # Mapping of universe names to PyTickerSymbols index names
    INDEX_MAPPING: dict[str, str] = {
        "sp500": "S&P 500",
        "sp100": "S&P 100",
        "nasdaq100": "NASDAQ 100",
        "dow30": "DOW JONES",
        "dax": "DAX",
        "ftse100": "FTSE 100",
        "nikkei225": "NIKKEI 225",
        "eurostoxx50": "EURO STOXX 50",
    }

    # Descriptions for each universe
    UNIVERSE_DESCRIPTIONS: dict[str, str] = {
        "sp500": "S&P 500 - Large Cap US equities",
        "sp100": "S&P 100 - Top 100 US Blue Chips",
        "nasdaq100": "NASDAQ 100 - Top tech-heavy US stocks",
        "dow30": "Dow Jones Industrial Average - 30 US Blue Chips",
        "dax": "DAX - 40 German Blue Chips",
        "ftse100": "FTSE 100 - UK largest companies",
        "nikkei225": "NIKKEI 225 - Japanese Blue Chips",
        "eurostoxx50": "Euro Stoxx 50 - Eurozone Blue Chips",
        "mag7": "Magnificent 7 - Tech megacaps",
        "brazilian": "Top Brazilian stocks (B3 exchange)",
    }

    def __init__(self) -> None:
        """Initialize the provider with PyTickerSymbols."""
        self._pts: PyTickerSymbols | None = None

    @property
    def pts(self) -> PyTickerSymbols:
        """Lazy-load PyTickerSymbols instance."""
        if self._pts is None:
            self._pts = PyTickerSymbols()
        return self._pts

    def get_available_universes(self) -> list[str]:
        """Return list of all available universe names."""
        builtin = list(self.BUILTIN_UNIVERSES.keys())
        external = list(self.INDEX_MAPPING.keys())
        return sorted(set(builtin + external))

    def _extract_yahoo_tickers(self, stocks: list[dict[str, Any]]) -> list[str]:
        """Extract Yahoo Finance tickers from stock data.

        Prefers USD-denominated tickers when available.
        """
        tickers = []
        for stock in stocks:
            symbols = stock.get("symbols", [])
            # First try to find USD ticker
            yahoo_ticker = None
            for sym in symbols:
                if sym.get("yahoo") and sym.get("currency") == "USD":
                    yahoo_ticker = sym["yahoo"]
                    break
            # Fallback to any Yahoo ticker
            if not yahoo_ticker:
                for sym in symbols:
                    if sym.get("yahoo"):
                        yahoo_ticker = sym["yahoo"]
                        break
            if yahoo_ticker:
                tickers.append(yahoo_ticker)
        return sorted(set(tickers))

    def fetch_universe(self, name: str) -> UniverseData | None:
        """Fetch universe data by name.

        Args:
            name: Universe name (e.g., 'sp500', 'nasdaq100', 'mag7')

        Returns:
            UniverseData with tickers and metadata, or None if not found
        """
        name_lower = name.lower()

        # Check built-in universes first
        if name_lower in self.BUILTIN_UNIVERSES:
            data = self.BUILTIN_UNIVERSES[name_lower]
            return UniverseData(
                name=name_lower,
                tickers=data["tickers"],
                description=data["description"],
                source_url=data.get("source_url"),
            )

        # Check external index mapping
        if name_lower in self.INDEX_MAPPING:
            index_name = self.INDEX_MAPPING[name_lower]
            description = self.UNIVERSE_DESCRIPTIONS.get(
                name_lower, f"{index_name} index constituents"
            )

            try:
                stocks = list(self.pts.get_stocks_by_index(index_name))
                tickers = self._extract_yahoo_tickers(stocks)

                if not tickers:
                    return None

                return UniverseData(
                    name=name_lower,
                    tickers=tickers,
                    description=description,
                    source_url=f"https://en.wikipedia.org/wiki/{index_name.replace(' ', '_')}",
                )
            except Exception:
                return None

        return None

    def fetch_all_universes(self) -> list[UniverseData]:
        """Fetch all available universes.

        Returns:
            List of UniverseData for all available universes
        """
        universes = []
        for name in self.get_available_universes():
            data = self.fetch_universe(name)
            if data:
                universes.append(data)
        return universes
