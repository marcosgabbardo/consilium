"""Prompt templates and YAML loader for agent personalities."""

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, BaseLoader

from consilium.config import get_settings
from consilium.core.models import Stock, SpecialistReport


class PromptLoader:
    """Loader for YAML-based agent prompts."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._prompts_dir = prompts_dir or get_settings().prompts_dir
        self._cache: dict[str, dict[str, Any]] = {}

    def load_investor_prompt(self, agent_id: str) -> dict[str, Any]:
        """Load investor agent prompt from YAML."""
        return self._load_prompt("investors", agent_id)

    def load_specialist_prompt(self, agent_id: str) -> dict[str, Any]:
        """Load specialist agent prompt from YAML."""
        return self._load_prompt("specialists", agent_id)

    def _load_prompt(self, category: str, agent_id: str) -> dict[str, Any]:
        """Load and cache prompt from YAML file."""
        cache_key = f"{category}/{agent_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        file_path = self._prompts_dir / category / f"{agent_id}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            prompt_data = yaml.safe_load(f)

        self._cache[cache_key] = prompt_data
        return prompt_data

    def list_available(self, category: str) -> list[str]:
        """List available prompts in a category."""
        category_dir = self._prompts_dir / category
        if not category_dir.exists():
            return []

        return [f.stem for f in category_dir.glob("*.yaml")]


class PromptBuilder:
    """Builder for constructing prompts from templates."""

    def __init__(self, loader: PromptLoader | None = None) -> None:
        self._loader = loader or PromptLoader()
        self._jinja = Environment(loader=BaseLoader())

    def build_system_prompt(
        self,
        persona: str,
        philosophy: str,
        principles: list[str],
        output_format: str = "structured_analysis",
    ) -> str:
        """Build system prompt for an investor agent."""
        principles_text = "\n".join(f"- {p}" for p in principles)

        return f"""{persona}

## Your Investment Philosophy
{philosophy}

## Key Principles You Apply
{principles_text}

## Analysis Framework
When analyzing a stock, you must:
1. Evaluate against your core principles
2. Consider the specialist analyses provided (if any)
3. Apply your unique perspective and experience
4. Provide clear reasoning for your recommendation
5. Be specific about metrics and numbers
6. Acknowledge uncertainty when data is limited
7. Consider both bull and bear cases

## Output Requirements
You must respond with a valid JSON object containing:
- signal: One of "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
- confidence: One of "VERY_HIGH", "HIGH", "MEDIUM", "LOW", "VERY_LOW"
- target_price: Your estimated fair value (number, optional)
- reasoning: 2-3 paragraphs explaining your analysis (string)
- key_factors: Array of 3-5 key factors driving your decision
- risks: Array of 2-4 primary risks you see
- time_horizon: Your recommended holding period (e.g., "12-24 months")

Respond ONLY with the JSON object, no additional text or markdown.
"""

    def build_specialist_system_prompt(
        self,
        name: str,
        focus: str,
        methodology: str,
    ) -> str:
        """Build system prompt for a specialist agent."""
        return f"""You are the {name}, a quantitative specialist focused on {focus}.

## Your Methodology
{methodology}

## Output Requirements
You must respond with a valid JSON object containing:
- summary: One paragraph executive summary of your analysis
- analysis: Detailed analysis (2-3 paragraphs)
- score: Overall score from 0-100 based on your criteria
- metrics: Object with key metrics and their values/assessments

Respond ONLY with the JSON object, no additional text or markdown.
"""

    def build_investor_analysis_prompt(
        self,
        stock: Stock,
        specialist_reports: list[SpecialistReport] | None = None,
    ) -> str:
        """Build analysis prompt for an investor agent."""
        prompt = f"""## Stock Under Analysis: {stock.ticker}

### Company Overview
Name: {stock.company.name}
Sector: {stock.company.sector or 'N/A'}
Industry: {stock.company.industry or 'N/A'}
Country: {stock.company.country or 'N/A'}
Exchange: {stock.company.exchange or 'N/A'}

### Current Price Data
Current Price: ${stock.price.current}
Change: {stock.price.change_percent}%
52-Week High: ${stock.price.fifty_two_week_high}
52-Week Low: ${stock.price.fifty_two_week_low}
Volume: {stock.price.volume:,}

### Fundamental Metrics
Market Cap: {self._format_market_cap(stock.fundamentals.market_cap)}
P/E Ratio: {stock.fundamentals.pe_ratio or 'N/A'}
Forward P/E: {stock.fundamentals.forward_pe or 'N/A'}
PEG Ratio: {stock.fundamentals.peg_ratio or 'N/A'}
P/B Ratio: {stock.fundamentals.price_to_book or 'N/A'}
P/S Ratio: {stock.fundamentals.price_to_sales or 'N/A'}
EV/EBITDA: {stock.fundamentals.ev_to_ebitda or 'N/A'}
Profit Margin: {self._format_pct(stock.fundamentals.profit_margin)}
Operating Margin: {self._format_pct(stock.fundamentals.operating_margin)}
ROE: {self._format_pct(stock.fundamentals.roe)}
ROA: {self._format_pct(stock.fundamentals.roa)}
Debt/Equity: {stock.fundamentals.debt_to_equity or 'N/A'}
Current Ratio: {stock.fundamentals.current_ratio or 'N/A'}
Revenue Growth: {self._format_pct(stock.fundamentals.revenue_growth)}
Earnings Growth: {self._format_pct(stock.fundamentals.earnings_growth)}
Dividend Yield: {self._format_pct(stock.fundamentals.dividend_yield)}
Beta: {stock.fundamentals.beta or 'N/A'}

### Technical Indicators
SMA 20: ${stock.technicals.sma_20 or 'N/A'}
SMA 50: ${stock.technicals.sma_50 or 'N/A'}
SMA 200: ${stock.technicals.sma_200 or 'N/A'}
RSI (14): {stock.technicals.rsi_14 or 'N/A'}
MACD: {stock.technicals.macd or 'N/A'}
Trend: {stock.technicals.trend or 'N/A'}
"""

        if specialist_reports:
            prompt += "\n### Specialist Analysis Reports\n"
            for report in specialist_reports:
                prompt += f"""
#### {report.specialist_name}
Score: {report.score}/100
Summary: {report.summary}

Analysis: {report.analysis}
"""

        prompt += f"""

---

Based on the above information and your investment philosophy, provide your analysis and recommendation for {stock.ticker}.
"""
        return prompt

    def build_specialist_analysis_prompt(
        self,
        stock: Stock,
        focus_area: str,
    ) -> str:
        """Build analysis prompt for a specialist agent."""
        if focus_area == "valuation":
            return self._build_valuation_prompt(stock)
        elif focus_area == "fundamentals":
            return self._build_fundamentals_prompt(stock)
        elif focus_area == "technicals":
            return self._build_technicals_prompt(stock)
        elif focus_area == "sentiment":
            return self._build_sentiment_prompt(stock)
        elif focus_area == "risk":
            return self._build_risk_prompt(stock)
        elif focus_area == "portfolio":
            return self._build_portfolio_prompt(stock)
        elif focus_area == "political":
            return self._build_political_prompt(stock)
        else:
            raise ValueError(f"Unknown focus area: {focus_area}")

    def _build_valuation_prompt(self, stock: Stock) -> str:
        """Build valuation-focused analysis prompt."""
        return f"""Analyze the valuation of {stock.ticker} ({stock.company.name}).

Current Price: ${stock.price.current}
Market Cap: {self._format_market_cap(stock.fundamentals.market_cap)}

Valuation Metrics:
- P/E Ratio: {stock.fundamentals.pe_ratio or 'N/A'}
- Forward P/E: {stock.fundamentals.forward_pe or 'N/A'}
- PEG Ratio: {stock.fundamentals.peg_ratio or 'N/A'}
- P/B Ratio: {stock.fundamentals.price_to_book or 'N/A'}
- P/S Ratio: {stock.fundamentals.price_to_sales or 'N/A'}
- EV/EBITDA: {stock.fundamentals.ev_to_ebitda or 'N/A'}
- EV/Revenue: {stock.fundamentals.ev_to_revenue or 'N/A'}

52-Week Range: ${stock.price.fifty_two_week_low} - ${stock.price.fifty_two_week_high}

Analyze:
1. Current valuation vs historical averages
2. Valuation vs sector peers
3. Implied growth expectations from multiples
4. Fair value estimate range
5. Margin of safety assessment
"""

    def _build_fundamentals_prompt(self, stock: Stock) -> str:
        """Build fundamentals-focused analysis prompt."""
        return f"""Analyze the fundamental quality of {stock.ticker} ({stock.company.name}).

Sector: {stock.company.sector or 'N/A'}
Industry: {stock.company.industry or 'N/A'}

Profitability:
- Profit Margin: {self._format_pct(stock.fundamentals.profit_margin)}
- Operating Margin: {self._format_pct(stock.fundamentals.operating_margin)}
- Gross Margin: {self._format_pct(stock.fundamentals.gross_margin)}
- ROE: {self._format_pct(stock.fundamentals.roe)}
- ROA: {self._format_pct(stock.fundamentals.roa)}

Growth:
- Revenue Growth: {self._format_pct(stock.fundamentals.revenue_growth)}
- Earnings Growth: {self._format_pct(stock.fundamentals.earnings_growth)}

Financial Health:
- Debt/Equity: {stock.fundamentals.debt_to_equity or 'N/A'}
- Current Ratio: {stock.fundamentals.current_ratio or 'N/A'}
- Quick Ratio: {stock.fundamentals.quick_ratio or 'N/A'}
- Free Cash Flow: {self._format_currency(stock.fundamentals.free_cash_flow)}

Analyze:
1. Business quality and competitive position
2. Profitability trends and sustainability
3. Balance sheet strength
4. Cash flow generation
5. Growth trajectory and quality
"""

    def _build_technicals_prompt(self, stock: Stock) -> str:
        """Build technicals-focused analysis prompt."""
        return f"""Analyze the technical picture for {stock.ticker} ({stock.company.name}).

Current Price: ${stock.price.current}
Change: {stock.price.change_percent}%
Volume: {stock.price.volume:,}

Moving Averages:
- SMA 20: ${stock.technicals.sma_20 or 'N/A'}
- SMA 50: ${stock.technicals.sma_50 or 'N/A'}
- SMA 200: ${stock.technicals.sma_200 or 'N/A'}
- EMA 12: ${stock.technicals.ema_12 or 'N/A'}
- EMA 26: ${stock.technicals.ema_26 or 'N/A'}

Momentum:
- RSI (14): {stock.technicals.rsi_14 or 'N/A'}
- MACD: {stock.technicals.macd or 'N/A'}
- MACD Signal: {stock.technicals.macd_signal or 'N/A'}

Volatility:
- Bollinger Upper: ${stock.technicals.bollinger_upper or 'N/A'}
- Bollinger Lower: ${stock.technicals.bollinger_lower or 'N/A'}
- ATR (14): ${stock.technicals.atr_14 or 'N/A'}
- Beta: {stock.fundamentals.beta or 'N/A'}

Price Range:
- 52-Week High: ${stock.price.fifty_two_week_high}
- 52-Week Low: ${stock.price.fifty_two_week_low}

Analyze:
1. Trend direction and strength
2. Momentum indicators
3. Support and resistance levels
4. Volume patterns
5. Risk/volatility assessment
"""

    def _build_sentiment_prompt(self, stock: Stock) -> str:
        """Build sentiment-focused analysis prompt."""
        return f"""Analyze market sentiment for {stock.ticker} ({stock.company.name}).

Current Price: ${stock.price.current}
Change: {stock.price.change_percent}%
Volume: {stock.price.volume:,}
Relative Volume: {stock.technicals.relative_volume or 'N/A'}

Price Position:
- From 52-Week High: {stock.price.from_52w_high_pct:.1f}% below
- From 52-Week Low: {stock.price.from_52w_low_pct:.1f}% above

Technical Sentiment:
- RSI (14): {stock.technicals.rsi_14 or 'N/A'} (>70 overbought, <30 oversold)
- Trend: {stock.technicals.trend or 'N/A'}

Based on available data, assess:
1. Current market sentiment (bullish/bearish/neutral)
2. Institutional positioning indicators
3. Price momentum and volume patterns
4. Contrarian indicators
5. Overall sentiment score
"""

    def _build_risk_prompt(self, stock: Stock) -> str:
        """Build risk-focused analysis prompt."""
        return f"""Analyze the risk profile of {stock.ticker} ({stock.company.name}).

Current Price: ${stock.price.current}
Market Cap: {self._format_market_cap(stock.fundamentals.market_cap)}

Volatility Metrics:
- Beta: {stock.fundamentals.beta or 'N/A'}
- ATR (14): ${stock.technicals.atr_14 or 'N/A'}
- RSI (14): {stock.technicals.rsi_14 or 'N/A'}

Financial Risk:
- Debt/Equity: {stock.fundamentals.debt_to_equity or 'N/A'}
- Current Ratio: {stock.fundamentals.current_ratio or 'N/A'}
- Quick Ratio: {stock.fundamentals.quick_ratio or 'N/A'}

Price Position:
- From 52-Week High: {stock.price.from_52w_high_pct:.1f}% below
- From 52-Week Low: {stock.price.from_52w_low_pct:.1f}% above
- 52-Week High: ${stock.price.fifty_two_week_high}
- 52-Week Low: ${stock.price.fifty_two_week_low}

Analyze:
1. Market/systematic risk exposure (beta analysis)
2. Company-specific/idiosyncratic risks
3. Financial leverage and liquidity risk
4. Volatility and drawdown potential
5. Overall risk score and risk-adjusted return potential
"""

    def _build_portfolio_prompt(self, stock: Stock) -> str:
        """Build portfolio-focused synthesis prompt."""
        return f"""Synthesize the investment case for {stock.ticker} ({stock.company.name}).

Company: {stock.company.name}
Sector: {stock.company.sector or 'N/A'}
Industry: {stock.company.industry or 'N/A'}

Current Price: ${stock.price.current}
Market Cap: {self._format_market_cap(stock.fundamentals.market_cap)}

Key Metrics Summary:
- P/E Ratio: {stock.fundamentals.pe_ratio or 'N/A'}
- Profit Margin: {self._format_pct(stock.fundamentals.profit_margin)}
- ROE: {self._format_pct(stock.fundamentals.roe)}
- Debt/Equity: {stock.fundamentals.debt_to_equity or 'N/A'}
- Beta: {stock.fundamentals.beta or 'N/A'}
- Dividend Yield: {self._format_pct(stock.fundamentals.dividend_yield)}

Technical Picture:
- Trend: {stock.technicals.trend or 'N/A'}
- RSI: {stock.technicals.rsi_14 or 'N/A'}
- Price vs 52W Range: {stock.price.from_52w_low_pct:.1f}% from low, {stock.price.from_52w_high_pct:.1f}% from high

As Portfolio Manager, synthesize:
1. Overall investment thesis (bull case vs bear case)
2. Position sizing recommendation (full, half, quarter position)
3. Entry strategy (buy now, scale in, wait for pullback)
4. Risk management approach (stop loss levels, position limits)
5. Portfolio fit (growth, value, income, speculative allocation)
"""

    def _build_political_prompt(self, stock: Stock) -> str:
        """Build political risk analysis prompt."""
        # Determine country from exchange or company info
        country = stock.company.country or "Unknown"
        exchange = stock.company.exchange or "Unknown"

        # Check if it's a state-owned or regulated company based on sector
        sector = stock.company.sector or "Unknown"
        industry = stock.company.industry or "Unknown"

        # Sectors with high political exposure
        high_political_sectors = [
            "energy", "utilities", "financial", "telecommunications",
            "defense", "healthcare", "transportation", "mining"
        ]
        is_high_exposure = any(
            s.lower() in (sector.lower() + " " + industry.lower())
            for s in high_political_sectors
        )

        exposure_note = ""
        if is_high_exposure:
            exposure_note = f"""
Note: {stock.company.name} operates in {sector}/{industry}, a sector typically subject to
significant government regulation and political influence.
"""

        return f"""Analyze the political risk profile of {stock.ticker} ({stock.company.name}).

## Company Context
Company: {stock.company.name}
Sector: {sector}
Industry: {industry}
Country: {country}
Exchange: {exchange}
{exposure_note}
## Current Price Context
Current Price: ${stock.price.current}
Market Cap: {self._format_market_cap(stock.fundamentals.market_cap)}
52-Week Range: ${stock.price.fifty_two_week_low} - ${stock.price.fifty_two_week_high}

## Key Financial Metrics (for context)
Dividend Yield: {self._format_pct(stock.fundamentals.dividend_yield)}
Debt/Equity: {stock.fundamentals.debt_to_equity or 'N/A'}
Beta: {stock.fundamentals.beta or 'N/A'}

## Political Analysis Required

Based on your knowledge of {country}'s political environment and {sector} sector dynamics:

1. ELECTORAL CYCLE ANALYSIS
   - Current political situation and government stability
   - Upcoming elections (national, regional) and potential market impact
   - Historical behavior of this company/sector during political transitions
   - Current government's stance toward this sector

2. GOVERNMENT INTERVENTION RISK
   - Likelihood of state ownership changes or nationalization risk
   - Price controls, subsidies, or market intervention history
   - Political appointments risk to company leadership
   - History of using company for political/social purposes (if any)

3. REGULATORY ENVIRONMENT
   - Pending regulatory changes that could impact the company
   - Tax policy changes risk for this sector
   - Licensing, concessions, or permits dependencies
   - Antitrust or competition policy exposure

4. GEOPOLITICAL FACTORS
   - International sanctions exposure or risk
   - Trade policy and tariff implications
   - Export market dependencies and geopolitical tensions
   - Supply chain geopolitical vulnerabilities

5. INSTITUTIONAL STABILITY
   - Rule of law and contract enforcement reliability
   - Regulatory independence and corruption risk
   - Currency and capital controls risk
   - Property rights and shareholder protection

## Output Requirements
Provide:
- summary: 1-2 sentence political risk assessment
- analysis: Detailed analysis of each risk category (2-3 paragraphs)
- score: From -100 (extreme political risk) to +100 (strong political tailwinds)
  - -100 to -50: High political risk (avoid or reduce)
  - -49 to -10: Elevated political risk
  - -10 to +10: Neutral political environment
  - +10 to +49: Favorable political environment
  - +50 to +100: Strong political tailwinds
- metrics: Key political risk factors with their individual assessments
"""

    def _format_pct(self, value: Any) -> str:
        """Format a value as percentage."""
        if value is None:
            return "N/A"
        try:
            return f"{float(value) * 100:.1f}%"
        except (ValueError, TypeError):
            return "N/A"

    def _format_market_cap(self, value: Any) -> str:
        """Format market cap with $ and commas."""
        if value is None:
            return "N/A"
        try:
            return f"${float(value):,.0f}"
        except (ValueError, TypeError):
            return "N/A"

    def _format_currency(self, value: Any) -> str:
        """Format a currency value."""
        if value is None:
            return "N/A"
        try:
            return f"${float(value):,.0f}"
        except (ValueError, TypeError):
            return "N/A"
