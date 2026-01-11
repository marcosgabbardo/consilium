"""Async Anthropic Claude client wrapper with retry logic."""

import json
from typing import Any

from anthropic import AsyncAnthropic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from consilium.config import Settings, get_settings
from consilium.core.exceptions import LLMError


class ClaudeClient:
    """Async wrapper for Anthropic Claude API with retry logic."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        self._model = self._settings.model

    @property
    def model(self) -> str:
        """Get the current model name."""
        return self._model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """
        Send a completion request to Claude.

        Args:
            system_prompt: The system prompt defining agent behavior
            user_prompt: The user message with analysis request
            response_schema: Optional JSON schema for structured output
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Returns:
            Parsed JSON response as dict
        """
        try:
            # Build messages
            messages = [{"role": "user", "content": user_prompt}]

            # If schema provided, add instructions for JSON output
            if response_schema:
                schema_instruction = (
                    "\n\nYou MUST respond with a valid JSON object matching this schema:\n"
                    f"```json\n{json.dumps(response_schema, indent=2)}\n```\n"
                    "Respond ONLY with the JSON object, no additional text."
                )
                full_system = system_prompt + schema_instruction
            else:
                full_system = system_prompt

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=full_system,
                messages=messages,
            )

            # Extract text content
            content = response.content[0].text

            # Parse JSON response
            return self._parse_json_response(content)

        except json.JSONDecodeError as e:
            raise LLMError(
                f"Failed to parse JSON response: {e}",
                model=self._model,
                details={"raw_response": content[:500] if "content" in dir() else None},
            ) from e
        except Exception as e:
            raise LLMError(
                f"Claude API error: {e}",
                model=self._model,
            ) from e

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from response, handling markdown code blocks."""
        content = content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        return json.loads(content)

    async def complete_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a completion request and return raw text response.

        Args:
            system_prompt: The system prompt
            user_prompt: The user message
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Raw text response
        """
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            return response.content[0].text

        except Exception as e:
            raise LLMError(
                f"Claude API error: {e}",
                model=self._model,
            ) from e

    async def health_check(self) -> bool:
        """Check API connectivity."""
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'ok'"}],
            )
            return len(response.content) > 0
        except Exception:
            return False


# Response schemas for structured output

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
            "description": "One paragraph executive summary",
        },
        "analysis": {
            "type": "string",
            "description": "Detailed analysis (2-3 paragraphs)",
        },
        "score": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "Overall score from 0-100",
        },
        "metrics": {
            "type": "object",
            "description": "Key metrics and their values/assessments",
        },
    },
    "required": ["summary", "analysis", "score"],
}
