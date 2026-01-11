"""Data access layer (DAO pattern) for Consilium."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from consilium.config import get_settings
from consilium.core.models import AnalysisResult, ConsensusResult, AgentResponse
from consilium.db.connection import DatabasePool


class CacheRepository:
    """Repository for market data caching operations."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool
        self._settings = get_settings()

    async def get_cached(
        self, ticker: str, data_type: str
    ) -> dict[str, Any] | None:
        """Retrieve cached data if not expired."""
        result = await self._pool.fetch_one(
            """
            SELECT data_json, expires_at
            FROM market_data_cache
            WHERE ticker = %s AND data_type = %s
            AND expires_at > NOW()
            ORDER BY fetched_at DESC LIMIT 1
            """,
            (ticker.upper(), data_type),
        )
        if result:
            return json.loads(result["data_json"])
        return None

    async def set_cached(
        self,
        ticker: str,
        data_type: str,
        data: dict[str, Any],
        ttl_minutes: int | None = None,
    ) -> None:
        """Store data in cache with TTL."""
        ttl = ttl_minutes or self._settings.cache.get_ttl(data_type)
        expires_at = datetime.utcnow() + timedelta(minutes=ttl)

        await self._pool.execute(
            """
            INSERT INTO market_data_cache
            (ticker, data_type, data_json, fetched_at, expires_at)
            VALUES (%s, %s, %s, NOW(), %s)
            """,
            (ticker.upper(), data_type, json.dumps(data, default=str), expires_at),
        )

    async def invalidate(
        self, ticker: str, data_type: str | None = None
    ) -> int:
        """Invalidate cached data for a ticker. Returns rows deleted."""
        if data_type:
            rows, _ = await self._pool.execute(
                "DELETE FROM market_data_cache WHERE ticker = %s AND data_type = %s",
                (ticker.upper(), data_type),
            )
        else:
            rows, _ = await self._pool.execute(
                "DELETE FROM market_data_cache WHERE ticker = %s",
                (ticker.upper(),),
            )
        return rows

    async def cleanup_expired(self) -> int:
        """Remove all expired cache entries. Returns rows deleted."""
        rows, _ = await self._pool.execute(
            "DELETE FROM market_data_cache WHERE expires_at < NOW()"
        )
        return rows


class HistoryRepository:
    """Repository for analysis history operations."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def save_analysis(self, result: AnalysisResult) -> int:
        """Save complete analysis result to history. Returns analysis_id."""
        # Insert main analysis record
        _, analysis_id = await self._pool.execute(
            """
            INSERT INTO analysis_history
            (request_id, tickers, results_json, agents_used, execution_time_ms)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                result.request_id,
                json.dumps(result.tickers),
                result.model_dump_json(),
                result.agents_used,
                int(result.execution_time_seconds * 1000),
            ),
        )

        # Save individual agent responses
        for consensus in result.results:
            for response in consensus.agent_responses:
                await self._pool.execute(
                    """
                    INSERT INTO agent_responses
                    (analysis_id, agent_id, ticker, signal, confidence,
                     target_price, reasoning, key_factors, risks)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        analysis_id,
                        response.agent_id,
                        response.ticker,
                        response.signal.value,
                        response.confidence.value,
                        float(response.target_price) if response.target_price else None,
                        response.reasoning,
                        json.dumps(response.key_factors),
                        json.dumps(response.risks),
                    ),
                )

        return analysis_id

    async def get_recent_analyses(
        self, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent analysis summaries."""
        return await self._pool.fetch_all(
            """
            SELECT request_id, tickers, agents_used,
                   execution_time_ms, created_at
            FROM analysis_history
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )

    async def get_analysis_by_id(
        self, request_id: str
    ) -> dict[str, Any] | None:
        """Get full analysis by request ID."""
        return await self._pool.fetch_one(
            """
            SELECT request_id, tickers, results_json,
                   agents_used, execution_time_ms, created_at
            FROM analysis_history
            WHERE request_id = %s
            """,
            (request_id,),
        )

    async def get_agent_history(
        self, agent_id: str, ticker: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get historical responses for a specific agent."""
        if ticker:
            return await self._pool.fetch_all(
                """
                SELECT ar.*, ah.created_at as analysis_date
                FROM agent_responses ar
                JOIN analysis_history ah ON ar.analysis_id = ah.id
                WHERE ar.agent_id = %s AND ar.ticker = %s
                ORDER BY ah.created_at DESC
                LIMIT %s
                """,
                (agent_id, ticker.upper(), limit),
            )
        else:
            return await self._pool.fetch_all(
                """
                SELECT ar.*, ah.created_at as analysis_date
                FROM agent_responses ar
                JOIN analysis_history ah ON ar.analysis_id = ah.id
                WHERE ar.agent_id = %s
                ORDER BY ah.created_at DESC
                LIMIT %s
                """,
                (agent_id, limit),
            )


class WatchlistRepository:
    """Repository for watchlist operations."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def create(
        self, name: str, tickers: list[str], description: str | None = None
    ) -> int:
        """Create a new watchlist. Returns watchlist_id."""
        _, wl_id = await self._pool.execute(
            """
            INSERT INTO watchlists (name, description, tickers)
            VALUES (%s, %s, %s)
            """,
            (name, description, json.dumps([t.upper() for t in tickers])),
        )
        return wl_id

    async def get_by_name(self, name: str) -> dict[str, Any] | None:
        """Get watchlist by name."""
        result = await self._pool.fetch_one(
            "SELECT * FROM watchlists WHERE name = %s",
            (name,),
        )
        if result and result.get("tickers"):
            result["tickers"] = json.loads(result["tickers"])
        return result

    async def list_all(self) -> list[dict[str, Any]]:
        """List all watchlists."""
        results = await self._pool.fetch_all(
            "SELECT id, name, description, created_at, updated_at FROM watchlists ORDER BY name"
        )
        return results

    async def add_tickers(self, name: str, tickers: list[str]) -> bool:
        """Add tickers to an existing watchlist."""
        wl = await self.get_by_name(name)
        if not wl:
            return False

        existing = set(wl.get("tickers", []))
        new_tickers = existing | {t.upper() for t in tickers}

        await self._pool.execute(
            "UPDATE watchlists SET tickers = %s WHERE name = %s",
            (json.dumps(list(new_tickers)), name),
        )
        return True

    async def remove_tickers(self, name: str, tickers: list[str]) -> bool:
        """Remove tickers from a watchlist."""
        wl = await self.get_by_name(name)
        if not wl:
            return False

        existing = set(wl.get("tickers", []))
        remaining = existing - {t.upper() for t in tickers}

        await self._pool.execute(
            "UPDATE watchlists SET tickers = %s WHERE name = %s",
            (json.dumps(list(remaining)), name),
        )
        return True

    async def delete(self, name: str) -> bool:
        """Delete a watchlist."""
        rows, _ = await self._pool.execute(
            "DELETE FROM watchlists WHERE name = %s",
            (name,),
        )
        return rows > 0


class AgentConfigRepository:
    """Repository for agent configuration overrides."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def get_config(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent configuration override."""
        return await self._pool.fetch_one(
            "SELECT * FROM agent_config WHERE agent_id = %s",
            (agent_id,),
        )

    async def set_weight(self, agent_id: str, weight: Decimal) -> None:
        """Set agent weight override."""
        await self._pool.execute(
            """
            INSERT INTO agent_config (agent_id, weight)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE weight = VALUES(weight)
            """,
            (agent_id, float(weight)),
        )

    async def set_enabled(self, agent_id: str, enabled: bool) -> None:
        """Enable or disable an agent."""
        await self._pool.execute(
            """
            INSERT INTO agent_config (agent_id, enabled)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE enabled = VALUES(enabled)
            """,
            (agent_id, enabled),
        )

    async def get_all_overrides(self) -> list[dict[str, Any]]:
        """Get all agent configuration overrides."""
        return await self._pool.fetch_all("SELECT * FROM agent_config")
