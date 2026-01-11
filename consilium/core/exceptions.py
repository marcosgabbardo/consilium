"""Custom exceptions for Consilium."""

from typing import Any


class ConsiliumError(Exception):
    """Base exception for all Consilium errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ConfigurationError(ConsiliumError):
    """Raised when there's a configuration problem."""

    pass


class DataFetchError(ConsiliumError):
    """Raised when market data cannot be fetched."""

    def __init__(
        self,
        message: str,
        ticker: str | None = None,
        source: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.ticker = ticker
        self.source = source
        super().__init__(
            message,
            details={
                **(details or {}),
                "ticker": ticker,
                "source": source,
            },
        )


class AgentError(ConsiliumError):
    """Raised when an agent fails to analyze."""

    def __init__(
        self,
        message: str,
        agent_id: str | None = None,
        ticker: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.ticker = ticker
        super().__init__(
            message,
            details={
                **(details or {}),
                "agent_id": agent_id,
                "ticker": ticker,
            },
        )


class LLMError(ConsiliumError):
    """Raised when LLM API call fails."""

    def __init__(
        self,
        message: str,
        model: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.status_code = status_code
        super().__init__(
            message,
            details={
                **(details or {}),
                "model": model,
                "status_code": status_code,
            },
        )


class DatabaseError(ConsiliumError):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.operation = operation
        super().__init__(
            message,
            details={
                **(details or {}),
                "operation": operation,
            },
        )


class CacheError(ConsiliumError):
    """Raised when cache operations fail."""

    pass


class ValidationError(ConsiliumError):
    """Raised when data validation fails."""

    pass


class ConsensusError(ConsiliumError):
    """Raised when consensus calculation fails."""

    def __init__(
        self,
        message: str,
        ticker: str | None = None,
        agent_count: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.ticker = ticker
        self.agent_count = agent_count
        super().__init__(
            message,
            details={
                **(details or {}),
                "ticker": ticker,
                "agent_count": agent_count,
            },
        )


class PortfolioError(ConsiliumError):
    """Raised when portfolio operations fail."""

    def __init__(
        self,
        message: str,
        portfolio_name: str | None = None,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.portfolio_name = portfolio_name
        self.operation = operation
        super().__init__(
            message,
            details={
                **(details or {}),
                "portfolio_name": portfolio_name,
                "operation": operation,
            },
        )


class PortfolioImportError(ConsiliumError):
    """Raised when portfolio import fails."""

    def __init__(
        self,
        message: str,
        file_name: str | None = None,
        row_number: int | None = None,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.file_name = file_name
        self.row_number = row_number
        self.field = field
        super().__init__(
            message,
            details={
                **(details or {}),
                "file_name": file_name,
                "row_number": row_number,
                "field": field,
            },
        )
