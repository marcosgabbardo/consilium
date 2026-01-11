"""Configuration management for Consilium using Pydantic Settings."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """MySQL database configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CONSILIUM_DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 3306
    user: str = "consilium"
    password: str = ""
    name: str = "consilium"
    pool_size: int = 5
    pool_recycle: int = 3600

    @property
    def connection_string(self) -> str:
        """Get MySQL connection string."""
        return f"mysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class CacheSettings(BaseSettings):
    """Cache TTL configuration (in minutes)."""

    model_config = SettingsConfigDict(
        env_prefix="CONSILIUM_CACHE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    price_ttl: int = 5
    fundamentals_ttl: int = 1440  # 24 hours
    technicals_ttl: int = 60
    info_ttl: int = 10080  # 1 week

    def get_ttl(self, data_type: str) -> int:
        """Get TTL for a specific data type."""
        ttls = {
            "price": self.price_ttl,
            "fundamentals": self.fundamentals_ttl,
            "technicals": self.technicals_ttl,
            "info": self.info_ttl,
        }
        return ttls.get(data_type, 60)


class AgentWeights(BaseSettings):
    """Configurable agent weights (0-10 scale)."""

    model_config = SettingsConfigDict(
        env_prefix="CONSILIUM_WEIGHT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Investor weights
    buffett: Decimal = Decimal("2.0")
    munger: Decimal = Decimal("1.8")
    graham: Decimal = Decimal("1.5")
    damodaran: Decimal = Decimal("1.5")
    ackman: Decimal = Decimal("1.2")
    wood: Decimal = Decimal("1.0")
    burry: Decimal = Decimal("1.3")
    pabrai: Decimal = Decimal("1.2")
    lynch: Decimal = Decimal("1.5")
    fisher: Decimal = Decimal("1.3")
    jhunjhunwala: Decimal = Decimal("1.0")
    druckenmiller: Decimal = Decimal("1.5")
    simons: Decimal = Decimal("1.8")

    # Specialist weights
    valuation: Decimal = Decimal("1.5")
    fundamentals: Decimal = Decimal("1.5")
    technicals: Decimal = Decimal("1.0")
    sentiment: Decimal = Decimal("0.8")
    risk: Decimal = Decimal("1.2")
    portfolio: Decimal = Decimal("1.0")
    political: Decimal = Decimal("1.1")

    def get_weight(self, agent_id: str) -> Decimal:
        """Get weight for a specific agent."""
        return getattr(self, agent_id.lower(), Decimal("1.0"))


class ConsensusThresholds(BaseSettings):
    """Thresholds for consensus signal determination."""

    model_config = SettingsConfigDict(
        env_prefix="CONSILIUM_THRESHOLD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    strong_buy: Decimal = Decimal("60")
    buy: Decimal = Decimal("20")
    sell: Decimal = Decimal("-20")
    strong_sell: Decimal = Decimal("-60")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # Model configuration
    model: str = Field(default="claude-opus-4-5-20251101", alias="CONSILIUM_MODEL")

    # Logging
    log_level: str = Field(default="INFO", alias="CONSILIUM_LOG_LEVEL")

    # Rate limiting
    max_concurrent_agents: int = Field(default=10, alias="CONSILIUM_MAX_CONCURRENT_AGENTS")
    api_retry_attempts: int = Field(default=3, alias="CONSILIUM_API_RETRY_ATTEMPTS")
    api_retry_delay: float = Field(default=1.0, alias="CONSILIUM_API_RETRY_DELAY")

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    weights: AgentWeights = Field(default_factory=AgentWeights)
    thresholds: ConsensusThresholds = Field(default_factory=ConsensusThresholds)

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v:
            return v
        if not v.startswith("sk-ant-"):
            raise ValueError("Invalid Anthropic API key format")
        return v

    @property
    def prompts_dir(self) -> Path:
        """Get the prompts directory path."""
        return Path(__file__).parent / "prompts"

    @property
    def is_configured(self) -> bool:
        """Check if essential settings are configured."""
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience function for direct access
def get_agent_weight(agent_id: str) -> Decimal:
    """Get weight for a specific agent."""
    return get_settings().weights.get_weight(agent_id)
