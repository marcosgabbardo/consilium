"""JSON schemas for structured LLM output."""

AGENT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "signal": {
            "type": "string",
            "enum": ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"],
            "description": "Investment recommendation signal",
        },
        "confidence": {
            "type": "string",
            "enum": ["VERY_HIGH", "HIGH", "MEDIUM", "LOW", "VERY_LOW"],
            "description": "Confidence level in the analysis",
        },
        "target_price": {
            "type": "number",
            "minimum": 0,
            "description": "Estimated fair value / target price (optional)",
        },
        "reasoning": {
            "type": "string",
            "minLength": 100,
            "description": "Detailed reasoning for the recommendation (2-3 paragraphs)",
        },
        "key_factors": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 5,
            "description": "Key factors driving the recommendation",
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 4,
            "description": "Primary risks identified",
        },
        "time_horizon": {
            "type": "string",
            "description": "Recommended time horizon (e.g., '6-12 months')",
        },
    },
    "required": ["signal", "confidence", "reasoning", "key_factors", "risks"],
}

SPECIALIST_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "One paragraph executive summary of the analysis",
        },
        "analysis": {
            "type": "string",
            "description": "Detailed analysis (2-3 paragraphs)",
        },
        "score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Overall score from 0-100 based on criteria",
        },
        "metrics": {
            "type": "object",
            "description": "Key metrics and their values/assessments",
            "additionalProperties": True,
        },
    },
    "required": ["summary", "analysis", "score"],
}

VALUATION_METRICS_SCHEMA = {
    "type": "object",
    "properties": {
        "fair_value_low": {"type": "number", "description": "Low end of fair value range"},
        "fair_value_high": {"type": "number", "description": "High end of fair value range"},
        "fair_value_mid": {"type": "number", "description": "Mid-point fair value estimate"},
        "upside_pct": {"type": "number", "description": "Upside potential percentage"},
        "pe_vs_sector": {"type": "string", "description": "P/E comparison to sector"},
        "valuation_grade": {
            "type": "string",
            "enum": ["A", "B", "C", "D", "F"],
            "description": "Overall valuation grade",
        },
    },
}

FUNDAMENTALS_METRICS_SCHEMA = {
    "type": "object",
    "properties": {
        "quality_score": {"type": "number", "description": "Business quality score 0-100"},
        "growth_score": {"type": "number", "description": "Growth quality score 0-100"},
        "financial_health_score": {"type": "number", "description": "Balance sheet score 0-100"},
        "moat_assessment": {
            "type": "string",
            "enum": ["Wide", "Narrow", "None"],
            "description": "Competitive moat assessment",
        },
        "earnings_quality": {
            "type": "string",
            "enum": ["High", "Medium", "Low"],
            "description": "Earnings quality assessment",
        },
    },
}

TECHNICALS_METRICS_SCHEMA = {
    "type": "object",
    "properties": {
        "trend_strength": {
            "type": "string",
            "enum": ["Strong Bullish", "Bullish", "Neutral", "Bearish", "Strong Bearish"],
            "description": "Overall trend assessment",
        },
        "momentum_signal": {
            "type": "string",
            "enum": ["Overbought", "Bullish", "Neutral", "Bearish", "Oversold"],
            "description": "Momentum indicator signal",
        },
        "support_level": {"type": "number", "description": "Key support price level"},
        "resistance_level": {"type": "number", "description": "Key resistance price level"},
        "volatility_assessment": {
            "type": "string",
            "enum": ["High", "Medium", "Low"],
            "description": "Volatility assessment",
        },
    },
}

SENTIMENT_METRICS_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_sentiment": {
            "type": "string",
            "enum": ["Very Bullish", "Bullish", "Neutral", "Bearish", "Very Bearish"],
            "description": "Overall market sentiment",
        },
        "contrarian_signal": {
            "type": "string",
            "enum": ["Buy", "Hold", "Sell"],
            "description": "Contrarian indicator signal",
        },
        "momentum_score": {"type": "number", "description": "Price momentum score 0-100"},
        "volume_trend": {
            "type": "string",
            "enum": ["Accumulation", "Neutral", "Distribution"],
            "description": "Volume trend assessment",
        },
    },
}
