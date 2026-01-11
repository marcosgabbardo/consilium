"""Database schema migrations for Consilium."""

from consilium.db.connection import DatabasePool


SCHEMA_VERSION = 1

MIGRATIONS = {
    1: """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_versions (
    version INT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR(255)
);

-- Market data cache
CREATE TABLE IF NOT EXISTS market_data_cache (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    data_type ENUM('price', 'fundamentals', 'technicals', 'info') NOT NULL,
    data_json JSON NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ticker_type (ticker, data_type),
    INDEX idx_expires (expires_at)
);

-- Analysis history
CREATE TABLE IF NOT EXISTS analysis_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL UNIQUE,
    tickers JSON NOT NULL,
    results_json JSON NOT NULL,
    agents_used INT NOT NULL,
    execution_time_ms INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_request_id (request_id),
    INDEX idx_created (created_at)
);

-- Individual agent responses
CREATE TABLE IF NOT EXISTS agent_responses (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    analysis_id BIGINT NOT NULL,
    agent_id VARCHAR(50) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    `signal` ENUM('STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL') NOT NULL,
    confidence ENUM('VERY_HIGH', 'HIGH', 'MEDIUM', 'LOW', 'VERY_LOW') NOT NULL,
    target_price DECIMAL(15, 2) NULL,
    reasoning TEXT NOT NULL,
    key_factors JSON,
    risks JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (analysis_id) REFERENCES analysis_history(id) ON DELETE CASCADE,
    INDEX idx_ticker_agent (ticker, agent_id),
    INDEX idx_analysis (analysis_id)
);

-- Watchlists
CREATE TABLE IF NOT EXISTS watchlists (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    tickers JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_name (name)
);

-- Agent configuration overrides
CREATE TABLE IF NOT EXISTS agent_config (
    agent_id VARCHAR(50) PRIMARY KEY,
    weight DECIMAL(4, 2) NOT NULL DEFAULT 1.00,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    custom_config JSON,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- API usage tracking
CREATE TABLE IF NOT EXISTS api_usage (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    api_name ENUM('anthropic', 'yahoo') NOT NULL,
    tokens_used INT DEFAULT 0,
    requests_made INT DEFAULT 0,
    cost_usd DECIMAL(10, 4) DEFAULT 0,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,

    INDEX idx_period (period_start, period_end)
);

-- Record initial version
INSERT INTO schema_versions (version, description) VALUES (1, 'Initial schema');
""",
}


async def get_current_version(pool: DatabasePool) -> int:
    """Get the current schema version."""
    try:
        result = await pool.fetch_one(
            "SELECT MAX(version) as version FROM schema_versions"
        )
        return result["version"] if result and result["version"] else 0
    except Exception:
        return 0


async def apply_migration(pool: DatabasePool, version: int) -> None:
    """Apply a specific migration."""
    if version not in MIGRATIONS:
        raise ValueError(f"Unknown migration version: {version}")

    sql = MIGRATIONS[version]

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Split by semicolons and execute each statement
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            for statement in statements:
                if statement:
                    await cur.execute(statement)


async def run_migrations(pool: DatabasePool) -> list[int]:
    """Run all pending migrations."""
    applied = []

    # First check if schema_versions table exists
    try:
        current_version = await get_current_version(pool)
    except Exception:
        # Table doesn't exist, start from 0
        current_version = 0

    for version in sorted(MIGRATIONS.keys()):
        if version > current_version:
            await apply_migration(pool, version)
            applied.append(version)

    return applied


async def reset_database(pool: DatabasePool) -> None:
    """Drop all tables and recreate schema. USE WITH CAUTION."""
    tables = [
        "api_usage",
        "agent_config",
        "watchlists",
        "agent_responses",
        "analysis_history",
        "market_data_cache",
        "schema_versions",
    ]

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Disable foreign key checks temporarily
            await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table in tables:
                await cur.execute(f"DROP TABLE IF EXISTS {table}")
            await cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    # Rerun all migrations
    await run_migrations(pool)
