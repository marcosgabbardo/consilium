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
        # Extract consensus info from first result (for single ticker)
        # or aggregate for multi-ticker
        consensus_signal = None
        consensus_score = None
        consensus_confidence = None

        if result.results:
            first_consensus = result.results[0]
            consensus_signal = first_consensus.final_signal.value
            consensus_score = round(float(first_consensus.weighted_score), 2)
            consensus_confidence = first_consensus.confidence.value

        # Insert main analysis record with consensus fields
        _, analysis_id = await self._pool.execute(
            """
            INSERT INTO analysis_history
            (request_id, tickers, results_json, agents_used, execution_time_ms,
             consensus_signal, consensus_score, consensus_confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                result.request_id,
                json.dumps(result.tickers),
                result.model_dump_json(),
                result.agents_used,
                int(result.execution_time_seconds * 1000),
                consensus_signal,
                consensus_score,
                consensus_confidence,
            ),
        )

        # Save individual agent responses and specialist reports
        for consensus in result.results:
            # Save agent responses
            for response in consensus.agent_responses:
                await self._pool.execute(
                    """
                    INSERT INTO agent_responses
                    (analysis_id, agent_id, ticker, `signal`, confidence,
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

            # Save specialist reports
            for report in consensus.specialist_reports:
                await self._pool.execute(
                    """
                    INSERT INTO specialist_reports
                    (analysis_id, specialist_id, ticker, summary, analysis, score, metrics)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        analysis_id,
                        report.specialist_id,
                        report.ticker,
                        report.summary,
                        report.analysis,
                        float(report.score) if report.score else None,
                        json.dumps(report.metrics) if report.metrics else None,
                    ),
                )

        return analysis_id

    async def get_recent_analyses(
        self, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent analysis summaries."""
        results = await self._pool.fetch_all(
            """
            SELECT request_id, tickers, agents_used, execution_time_ms,
                   consensus_signal, consensus_score, consensus_confidence,
                   created_at
            FROM analysis_history
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        # Parse tickers JSON
        for r in results:
            if r.get("tickers"):
                r["tickers"] = json.loads(r["tickers"])
        return results

    async def get_history(
        self,
        ticker: str | None = None,
        days: int | None = None,
        limit: int = 50,
        signal: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get analysis history with filters."""
        conditions = []
        params = []

        if ticker:
            conditions.append("JSON_CONTAINS(tickers, %s)")
            params.append(json.dumps(ticker.upper()))

        if days:
            conditions.append("created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)")
            params.append(days)

        if signal:
            conditions.append("consensus_signal = %s")
            params.append(signal.upper())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        results = await self._pool.fetch_all(
            f"""
            SELECT request_id, tickers, agents_used, execution_time_ms,
                   consensus_signal, consensus_score, consensus_confidence,
                   created_at
            FROM analysis_history
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )
        # Parse tickers JSON
        for r in results:
            if r.get("tickers"):
                r["tickers"] = json.loads(r["tickers"])
        return results

    async def get_analysis_by_id(
        self, request_id: str
    ) -> dict[str, Any] | None:
        """Get full analysis by request ID."""
        result = await self._pool.fetch_one(
            """
            SELECT request_id, tickers, results_json, agents_used, execution_time_ms,
                   consensus_signal, consensus_score, consensus_confidence, created_at
            FROM analysis_history
            WHERE request_id = %s
            """,
            (request_id,),
        )
        if result and result.get("tickers"):
            result["tickers"] = json.loads(result["tickers"])
        if result and result.get("results_json"):
            result["results_json"] = json.loads(result["results_json"])
        return result

    async def get_ticker_history(
        self, ticker: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get analysis history for a specific ticker."""
        results = await self._pool.fetch_all(
            """
            SELECT ah.request_id, ah.consensus_signal, ah.consensus_score,
                   ah.consensus_confidence, ah.created_at
            FROM analysis_history ah
            WHERE JSON_CONTAINS(ah.tickers, %s)
            ORDER BY ah.created_at DESC
            LIMIT %s
            """,
            (json.dumps(ticker.upper()), limit),
        )
        return results

    async def get_signal_distribution(
        self, days: int = 30
    ) -> dict[str, int]:
        """Get distribution of signals over a period."""
        results = await self._pool.fetch_all(
            """
            SELECT consensus_signal, COUNT(*) as count
            FROM analysis_history
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            AND consensus_signal IS NOT NULL
            GROUP BY consensus_signal
            """,
            (days,),
        )
        return {r["consensus_signal"]: r["count"] for r in results}

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
            VALUES (%s, %s) AS new_values
            ON DUPLICATE KEY UPDATE weight = new_values.weight
            """,
            (agent_id, float(weight)),
        )

    async def set_enabled(self, agent_id: str, enabled: bool) -> None:
        """Enable or disable an agent."""
        await self._pool.execute(
            """
            INSERT INTO agent_config (agent_id, enabled)
            VALUES (%s, %s) AS new_values
            ON DUPLICATE KEY UPDATE enabled = new_values.enabled
            """,
            (agent_id, enabled),
        )

    async def get_all_overrides(self) -> list[dict[str, Any]]:
        """Get all agent configuration overrides."""
        return await self._pool.fetch_all("SELECT * FROM agent_config")


class PriceHistoryRepository:
    """Repository for historical price data."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def save_prices(
        self, ticker: str, prices: list[dict[str, Any]]
    ) -> int:
        """Save historical prices. Returns number of rows inserted."""
        if not prices:
            return 0

        inserted = 0
        for price in prices:
            try:
                await self._pool.execute(
                    """
                    INSERT INTO price_history
                    (ticker, date, open, high, low, close, adj_close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) AS new_values
                    ON DUPLICATE KEY UPDATE
                    close = new_values.close, adj_close = new_values.adj_close, volume = new_values.volume
                    """,
                    (
                        ticker.upper(),
                        price["date"],
                        price.get("open"),
                        price.get("high"),
                        price.get("low"),
                        price["close"],
                        price.get("adj_close"),
                        price.get("volume"),
                    ),
                )
                inserted += 1
            except Exception:
                continue
        return inserted

    async def get_prices(
        self,
        ticker: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 252,  # ~1 year of trading days
    ) -> list[dict[str, Any]]:
        """Get historical prices for a ticker."""
        conditions = ["ticker = %s"]
        params: list[Any] = [ticker.upper()]

        if start_date:
            conditions.append("date >= %s")
            params.append(start_date.date() if isinstance(start_date, datetime) else start_date)

        if end_date:
            conditions.append("date <= %s")
            params.append(end_date.date() if isinstance(end_date, datetime) else end_date)

        where_clause = " AND ".join(conditions)
        params.append(limit)

        return await self._pool.fetch_all(
            f"""
            SELECT ticker, date, open, high, low, close, adj_close, volume
            FROM price_history
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_latest_price(self, ticker: str) -> dict[str, Any] | None:
        """Get the most recent price for a ticker."""
        return await self._pool.fetch_one(
            """
            SELECT ticker, date, open, high, low, close, adj_close, volume
            FROM price_history
            WHERE ticker = %s
            ORDER BY date DESC
            LIMIT 1
            """,
            (ticker.upper(),),
        )

    async def has_data(self, ticker: str, days: int = 30) -> bool:
        """Check if we have recent price data for a ticker."""
        result = await self._pool.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM price_history
            WHERE ticker = %s AND date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            """,
            (ticker.upper(), days),
        )
        return result and result.get("count", 0) > 0


class UniverseRepository:
    """Repository for stock universe operations."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def get_universe(self, name: str) -> dict[str, Any] | None:
        """Get a stock universe by name."""
        result = await self._pool.fetch_one(
            "SELECT * FROM stock_universes WHERE name = %s",
            (name.lower(),),
        )
        if result and result.get("tickers"):
            result["tickers"] = json.loads(result["tickers"])
        return result

    async def save_universe(
        self,
        name: str,
        tickers: list[str],
        description: str | None = None,
        source_url: str | None = None,
    ) -> int:
        """Save or update a stock universe. Returns universe_id."""
        tickers_upper = [t.upper() for t in tickers]
        _, uid = await self._pool.execute(
            """
            INSERT INTO stock_universes (name, description, tickers, source_url, ticker_count)
            VALUES (%s, %s, %s, %s, %s) AS new_values
            ON DUPLICATE KEY UPDATE
            tickers = new_values.tickers, description = new_values.description,
            source_url = new_values.source_url, ticker_count = new_values.ticker_count
            """,
            (
                name.lower(),
                description,
                json.dumps(tickers_upper),
                source_url,
                len(tickers_upper),
            ),
        )
        return uid

    async def list_universes(self) -> list[dict[str, Any]]:
        """List all available universes."""
        return await self._pool.fetch_all(
            """
            SELECT name, description, ticker_count, last_updated
            FROM stock_universes
            ORDER BY name
            """
        )

    async def delete_universe(self, name: str) -> bool:
        """Delete a universe."""
        rows, _ = await self._pool.execute(
            "DELETE FROM stock_universes WHERE name = %s",
            (name.lower(),),
        )
        return rows > 0
