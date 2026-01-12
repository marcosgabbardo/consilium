"""Extract ticker symbols from natural language questions."""

import re
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """Result of ticker extraction."""

    tickers: list[str]
    cleaned_question: str


class TickerExtractor:
    """Extracts stock ticker symbols from text."""

    # Common US stock patterns: 1-5 uppercase letters
    TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5})\b")

    # Brazilian stocks: XXXX3, XXXX4, XXXX11, etc.
    BR_TICKER_PATTERN = re.compile(
        r"\b([A-Z]{4}[0-9]{1,2}(?:\.SA)?)\b", re.IGNORECASE
    )

    # Common false positives to filter out
    FALSE_POSITIVES = {
        # Common English words
        "I",
        "A",
        "THE",
        "AND",
        "OR",
        "FOR",
        "TO",
        "IN",
        "ON",
        "AT",
        "OF",
        "IS",
        "IT",
        "BE",
        "AS",
        "BY",
        "AN",
        "IF",
        "NO",
        "SO",
        "UP",
        "DO",
        "MY",
        "ME",
        "WE",
        "HE",
        "HIS",
        "HER",
        "ITS",
        "OUR",
        "YOU",
        "YOUR",
        # Financial terms
        "AI",
        "US",
        "UK",
        "EU",
        "IPO",
        "ETF",
        "CEO",
        "CFO",
        "COO",
        "CTO",
        "P",
        "E",
        "B",
        "S",
        "EV",
        "PE",
        "PB",
        "PS",
        "ROE",
        "ROA",
        "ROI",
        "YOY",
        "QOQ",
        "MOM",
        "EPS",
        "DPS",
        "NAV",
        "AUM",
        "GDP",
        "CPI",
        "FED",
        "SEC",
        "NYSE",
        "NASDAQ",
        "SP",
        "DOW",
        "USD",
        "EUR",
        "BRL",
        "GBP",
        "JPY",
        "CNY",
        # Common verbs/adjectives
        "BUY",
        "SELL",
        "HOLD",
        "LONG",
        "SHORT",
        "PUT",
        "CALL",
        "HIGH",
        "LOW",
        "NEW",
        "OLD",
        "BIG",
        "TOP",
        "BEST",
        "GOOD",
        "BAD",
        "YEAR",
        "NEXT",
        "LAST",
        # Question words
        "WHAT",
        "WHEN",
        "WHERE",
        "WHY",
        "HOW",
        "WHO",
        "WHICH",
        # Portuguese words (common in questions)
        "O",
        "QUE",
        "PARA",
        "COM",
        "POR",
        "COMO",
        "MAIS",
        "ANOS",
        "ANO",
        "DA",
        "DE",
        "DO",
        "NA",
        "NO",
        "UM",
        "UMA",
        "ESSA",
        "ESSE",
        "ISSO",
        "QUAL",
        "QUAIS",
    }

    # Known valid tickers that might look like words
    KNOWN_TICKERS = {
        # Tech giants
        "META",
        "UBER",
        "LYFT",
        "COIN",
        "HOOD",
        "SOFI",
        "PLTR",
        "SNOW",
        "DDOG",
        "NET",
        "PATH",
        "DASH",
        "ABNB",
        "RBLX",
        "SHOP",
        "SQ",
        "NOW",
        "TEAM",
        "ZOOM",
        "SPOT",
        "PINS",
        "SNAP",
        "ROKU",
        "OPEN",
        "RIOT",
        "MARA",
        # ETFs
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "VTI",
        "VOO",
        "IBIT",
        "GBTC",
        "ARKK",
        "ARKW",
        # Popular stocks
        "AAPL",
        "MSFT",
        "GOOGL",
        "GOOG",
        "AMZN",
        "NVDA",
        "TSLA",
        "AMD",
        "INTC",
        "NFLX",
        "DIS",
        "BABA",
        "COST",
        "WMT",
        "TGT",
        "JPM",
        "BAC",
        "GS",
        "MS",
        "C",
        "V",
        "MA",
        "PYPL",
        "SQ",
        # Crypto-related
        "MSTR",
        "COIN",
        "RIOT",
        "MARA",
    }

    def extract(self, text: str) -> ExtractionResult:
        """Extract ticker symbols from text."""
        tickers: set[str] = set()

        # Extract Brazilian tickers first (more specific pattern)
        for match in self.BR_TICKER_PATTERN.finditer(text):
            ticker = match.group(1).upper()
            if not ticker.endswith(".SA"):
                ticker += ".SA"
            tickers.add(ticker)

        # Extract US tickers
        for match in self.TICKER_PATTERN.finditer(text):
            ticker = match.group(1)

            # Skip false positives unless they're known tickers
            if ticker in self.FALSE_POSITIVES and ticker not in self.KNOWN_TICKERS:
                continue

            # Skip if already captured as Brazilian ticker
            if f"{ticker}.SA" in tickers:
                continue

            # Only add if it's a known ticker or looks plausible
            # (avoids adding random uppercase words)
            if ticker in self.KNOWN_TICKERS or len(ticker) >= 2:
                # Additional check: if it's 2 chars, only add if known
                if len(ticker) == 2 and ticker not in self.KNOWN_TICKERS:
                    continue
                tickers.add(ticker)

        return ExtractionResult(
            tickers=sorted(list(tickers)),
            cleaned_question=text,
        )

    def extract_with_context(self, text: str) -> ExtractionResult:
        """
        Extract tickers with context awareness.

        Looks for patterns like "buy AAPL", "TSLA stock", "$NVDA"
        """
        tickers: set[str] = set()

        # Pattern for $TICKER format
        dollar_pattern = re.compile(r"\$([A-Z]{1,5})\b")
        for match in dollar_pattern.finditer(text):
            tickers.add(match.group(1))

        # Pattern for "TICKER stock/shares/action"
        stock_context = re.compile(
            r"\b([A-Z]{1,5})\s+(?:stock|shares|action|ação|papel)\b", re.IGNORECASE
        )
        for match in stock_context.finditer(text):
            ticker = match.group(1).upper()
            if ticker not in self.FALSE_POSITIVES:
                tickers.add(ticker)

        # Also run regular extraction
        regular_result = self.extract(text)
        tickers.update(regular_result.tickers)

        return ExtractionResult(
            tickers=sorted(list(tickers)),
            cleaned_question=text,
        )
