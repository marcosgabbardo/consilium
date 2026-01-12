"""Database schema migrations for Consilium."""

from consilium.db.connection import DatabasePool


SCHEMA_VERSION = 4

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
    2: """
-- Migration v2: Historical Tracking & Extended Analysis
-- Adds price history, expands analysis_history, and enhances watchlists

-- Add consensus columns to analysis_history
ALTER TABLE analysis_history
ADD COLUMN consensus_signal VARCHAR(20) NULL AFTER execution_time_ms,
ADD COLUMN consensus_score DECIMAL(6, 2) NULL AFTER consensus_signal,
ADD COLUMN consensus_confidence VARCHAR(20) NULL AFTER consensus_score;

-- Add index for ticker-based queries on analysis
ALTER TABLE analysis_history ADD INDEX idx_tickers ((CAST(tickers AS CHAR(255))));

-- Price history for backtesting
CREATE TABLE IF NOT EXISTS price_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(15, 4) NULL,
    high DECIMAL(15, 4) NULL,
    low DECIMAL(15, 4) NULL,
    close DECIMAL(15, 4) NOT NULL,
    adj_close DECIMAL(15, 4) NULL,
    volume BIGINT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY idx_ticker_date (ticker, date),
    INDEX idx_ticker (ticker),
    INDEX idx_date (date)
);

-- Enhance watchlists with analysis tracking
ALTER TABLE watchlists
ADD COLUMN last_analyzed_at TIMESTAMP NULL AFTER updated_at,
ADD COLUMN analysis_schedule VARCHAR(20) NULL AFTER last_analyzed_at;

-- Stock universes (S&P 500, NASDAQ 100, etc.)
CREATE TABLE IF NOT EXISTS stock_universes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255) NULL,
    tickers JSON NOT NULL,
    source_url VARCHAR(500) NULL,
    ticker_count INT NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_name (name)
);

-- Specialist reports storage (for historical reference)
CREATE TABLE IF NOT EXISTS specialist_reports (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    analysis_id BIGINT NOT NULL,
    specialist_id VARCHAR(50) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    summary TEXT NOT NULL,
    analysis TEXT NOT NULL,
    score DECIMAL(5, 2) NULL,
    metrics JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (analysis_id) REFERENCES analysis_history(id) ON DELETE CASCADE,
    INDEX idx_ticker_specialist (ticker, specialist_id),
    INDEX idx_analysis (analysis_id)
);

-- Record version 2
INSERT INTO schema_versions (version, description) VALUES (2, 'Historical tracking and extended analysis');
""",
    3: """
-- Migration v3: Portfolio Management
-- Adds portfolios, positions, import history, and portfolio analysis tables

-- Portfolios table
CREATE TABLE IF NOT EXISTS portfolios (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    currency VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_name (name)
);

-- Portfolio positions (holdings)
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id BIGINT NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    purchase_price DECIMAL(15, 4) NOT NULL,
    purchase_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    INDEX idx_portfolio_ticker (portfolio_id, ticker),
    UNIQUE KEY idx_portfolio_position (portfolio_id, ticker, purchase_date, purchase_price)
);

-- Portfolio import history
CREATE TABLE IF NOT EXISTS portfolio_imports (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id BIGINT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    records_total INT DEFAULT 0,
    records_success INT DEFAULT 0,
    records_failed INT DEFAULT 0,
    errors_json JSON,
    column_mapping JSON,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    INDEX idx_portfolio (portfolio_id)
);

-- Portfolio analysis history
CREATE TABLE IF NOT EXISTS portfolio_analysis (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id BIGINT NOT NULL,
    analysis_id BIGINT NULL,
    total_value DECIMAL(18, 2),
    total_cost_basis DECIMAL(18, 2),
    total_pnl DECIMAL(18, 2),
    total_pnl_percent DECIMAL(8, 4),
    portfolio_signal VARCHAR(20),
    portfolio_score DECIMAL(6, 2),
    sector_allocation JSON,
    position_recommendations JSON,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES analysis_history(id) ON DELETE SET NULL,
    INDEX idx_portfolio (portfolio_id),
    INDEX idx_analyzed (analyzed_at)
);

-- Record version 3
INSERT INTO schema_versions (version, description) VALUES (3, 'Portfolio management');
""",
    4: """
-- Migration v4: Transaction Tracking (BUY/SELL)
-- Adds portfolio_transactions table for full buy/sell history and realized P&L tracking

-- Portfolio transactions (full audit trail of buy/sell operations)
CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id BIGINT NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    transaction_type ENUM('BUY', 'SELL') NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    price DECIMAL(15, 4) NOT NULL,
    transaction_date DATE NOT NULL,
    fees DECIMAL(10, 2) DEFAULT 0,
    notes TEXT,

    -- P&L fields (populated for SELL transactions)
    realized_pnl DECIMAL(18, 2) NULL,
    holding_period_days INT NULL,
    cost_basis_used DECIMAL(15, 4) NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    INDEX idx_portfolio_ticker (portfolio_id, ticker),
    INDEX idx_transaction_date (transaction_date),
    INDEX idx_type (transaction_type)
);

-- Portfolio snapshots for historical performance tracking
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id BIGINT NOT NULL,
    snapshot_date DATE NOT NULL,
    total_value DECIMAL(18, 2),
    total_cost_basis DECIMAL(18, 2),
    total_unrealized_pnl DECIMAL(18, 2),
    cumulative_realized_pnl DECIMAL(18, 2),
    cash_balance DECIMAL(18, 2) DEFAULT 0,
    position_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    UNIQUE KEY idx_portfolio_date (portfolio_id, snapshot_date)
);

-- Add realized P&L columns to portfolio_analysis
ALTER TABLE portfolio_analysis
ADD COLUMN total_realized_pnl DECIMAL(18, 2) NULL AFTER total_pnl_percent,
ADD COLUMN total_fees DECIMAL(10, 2) NULL AFTER total_realized_pnl;

-- Migrate existing portfolio_positions to portfolio_transactions as BUY
INSERT INTO portfolio_transactions (
    portfolio_id,
    ticker,
    transaction_type,
    quantity,
    price,
    transaction_date,
    notes,
    created_at
)
SELECT
    portfolio_id,
    ticker,
    'BUY',
    quantity,
    purchase_price,
    purchase_date,
    notes,
    created_at
FROM portfolio_positions;

-- Record version 4
INSERT INTO schema_versions (version, description) VALUES (4, 'Transaction tracking (BUY/SELL)');
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
        "portfolio_snapshots",
        "portfolio_transactions",
        "portfolio_analysis",
        "portfolio_imports",
        "portfolio_positions",
        "portfolios",
        "api_usage",
        "agent_config",
        "specialist_reports",
        "agent_responses",
        "analysis_history",
        "watchlists",
        "stock_universes",
        "price_history",
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
