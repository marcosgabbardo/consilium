"""Q&A-specific prompts for investor agents."""

from typing import Any

from consilium.core.models import Stock


# Q&A response schema - similar to analysis but optimized for Q&A context
ASK_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "signal": {
            "type": "string",
            "enum": ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"],
            "description": "Your investment recommendation based on the question",
        },
        "confidence": {
            "type": "string",
            "enum": ["VERY_HIGH", "HIGH", "MEDIUM", "LOW", "VERY_LOW"],
            "description": "Confidence level in your recommendation",
        },
        "target_price": {
            "type": "number",
            "minimum": 0,
            "description": "Estimated fair value / target price (optional)",
        },
        "reasoning": {
            "type": "string",
            "minLength": 100,
            "description": "Your response to the question with detailed reasoning (2-3 paragraphs)",
        },
        "key_factors": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 5,
            "description": "Key factors supporting your view",
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 4,
            "description": "Primary risks or concerns",
        },
        "time_horizon": {
            "type": "string",
            "description": "Relevant time horizon for your view (e.g., '6-12 months')",
        },
    },
    "required": ["signal", "confidence", "reasoning", "key_factors", "risks"],
}


class AskPromptBuilder:
    """Builds prompts for Q&A interactions with investor agents."""

    def build_qa_prompt(
        self,
        question: str,
        stock_data: dict[str, Stock] | None = None,
    ) -> str:
        """
        Build the user prompt for a Q&A interaction.

        Args:
            question: The user's question
            stock_data: Optional dict of ticker -> Stock with market data

        Returns:
            Formatted prompt string
        """
        parts = []

        # Add the question
        parts.append("## Question from Investor\n")
        parts.append(f'"{question}"\n')

        # Add stock data if available
        if stock_data:
            parts.append("\n## Market Data for Referenced Stocks\n")
            for ticker, stock in stock_data.items():
                parts.append(self._format_stock_data(stock))
                parts.append("\n")

        # Add response instructions
        parts.append("\n## Instructions\n")
        parts.append(
            "Please answer the question above from your perspective as an investor. "
            "Draw on your investment philosophy and principles. "
            "If the question involves specific stocks, use the market data provided to inform your response. "
            "Be direct and substantive in your answer.\n"
        )

        return "\n".join(parts)

    def build_qa_system_prompt_suffix(self) -> str:
        """
        Return additional system prompt for Q&A mode.

        This is appended to the investor's standard system prompt.
        """
        return """

## Q&A Mode Instructions
You are answering a direct question from an investor seeking your perspective.

Guidelines:
- Be conversational but substantive - this is a dialogue, not a formal report
- Reference your investment philosophy and principles when relevant
- If the question involves specific stocks, provide concrete analysis using the data
- Be honest about uncertainties, limitations of your analysis, and areas outside your expertise
- If the question asks about a strategy (e.g., long/short pairs), evaluate both sides
- If asked about future projections, be clear about assumptions and timeframes
- Maintain your character's voice and perspective throughout

Remember: You are answering as this investor would, based on their known philosophy and track record.
"""

    def _format_stock_data(self, stock: Stock) -> str:
        """Format stock data for inclusion in prompt."""
        parts = []

        parts.append(f"### {stock.ticker} - {stock.name}")
        parts.append(f"**Sector:** {stock.sector} | **Industry:** {stock.industry}")

        # Price data
        if stock.current_price:
            parts.append(f"\n**Current Price:** ${stock.current_price:.2f}")
            if stock.change_percent:
                sign = "+" if stock.change_percent >= 0 else ""
                parts.append(f" ({sign}{stock.change_percent:.2f}%)")

        if stock.week_52_high and stock.week_52_low:
            parts.append(
                f"\n**52-Week Range:** ${stock.week_52_low:.2f} - ${stock.week_52_high:.2f}"
            )

        # Key fundamentals
        fundamentals = []
        if stock.pe_ratio:
            fundamentals.append(f"P/E: {stock.pe_ratio:.1f}")
        if stock.forward_pe:
            fundamentals.append(f"Fwd P/E: {stock.forward_pe:.1f}")
        if stock.peg_ratio:
            fundamentals.append(f"PEG: {stock.peg_ratio:.2f}")
        if stock.price_to_book:
            fundamentals.append(f"P/B: {stock.price_to_book:.2f}")
        if stock.market_cap:
            cap_b = stock.market_cap / 1_000_000_000
            fundamentals.append(f"Market Cap: ${cap_b:.1f}B")

        if fundamentals:
            parts.append(f"\n**Fundamentals:** {' | '.join(fundamentals)}")

        # Performance
        performance = []
        if stock.roe:
            performance.append(f"ROE: {stock.roe:.1f}%")
        if stock.profit_margin:
            performance.append(f"Profit Margin: {stock.profit_margin:.1f}%")
        if stock.revenue_growth:
            performance.append(f"Rev Growth: {stock.revenue_growth:.1f}%")
        if stock.earnings_growth:
            performance.append(f"Earnings Growth: {stock.earnings_growth:.1f}%")

        if performance:
            parts.append(f"\n**Performance:** {' | '.join(performance)}")

        # Dividend
        if stock.dividend_yield and stock.dividend_yield > 0:
            parts.append(f"\n**Dividend Yield:** {stock.dividend_yield:.2f}%")

        # Technical indicators (brief)
        technicals = []
        if stock.rsi:
            technicals.append(f"RSI: {stock.rsi:.0f}")
        if stock.beta:
            technicals.append(f"Beta: {stock.beta:.2f}")
        if stock.trend:
            technicals.append(f"Trend: {stock.trend}")

        if technicals:
            parts.append(f"\n**Technicals:** {' | '.join(technicals)}")

        return "\n".join(parts)

    def build_comparison_prompt(
        self,
        question: str,
        stock_data: dict[str, Stock] | None = None,
    ) -> str:
        """
        Build prompt for comparing multiple stocks.

        Similar to qa_prompt but emphasizes comparison.
        """
        parts = []

        parts.append("## Comparison Question from Investor\n")
        parts.append(f'"{question}"\n')

        if stock_data and len(stock_data) > 1:
            parts.append("\n## Stocks to Compare\n")
            for ticker, stock in stock_data.items():
                parts.append(self._format_stock_data(stock))
                parts.append("\n---\n")

        parts.append("\n## Instructions\n")
        parts.append(
            "Please compare the stocks mentioned and provide your recommendation. "
            "Consider relative valuation, quality, and risk/reward for each. "
            "State your preference and reasoning clearly.\n"
        )

        return "\n".join(parts)
