"""Repository for backtesting persistence."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from consilium.config import Settings, get_settings
from consilium.db.connection import DatabasePool, get_pool
from consilium.backtesting.models import (
    BacktestMetrics,
    BacktestResult,
    BacktestStrategyType,
    BacktestTrade,
    DailySnapshot,
    TradeAction,
)
from consilium.core.enums import SignalType


def _r(val: Any, decimals: int = 4) -> float | None:
    """Round value for database storage to avoid truncation warnings."""
    if val is None:
        return None
    return round(float(val), decimals)


class BacktestRepository:
    """Repository for storing and retrieving backtest results."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._pool: DatabasePool | None = None

    async def _ensure_pool(self) -> DatabasePool:
        """Ensure database pool is available."""
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def save_backtest(self, result: BacktestResult) -> int:
        """
        Save a backtest result to the database.

        Args:
            result: The BacktestResult to save

        Returns:
            The ID of the saved backtest
        """
        pool = await self._ensure_pool()

        # Insert backtest run
        run_query = """
            INSERT INTO backtest_runs
                (ticker, benchmark, start_date, end_date, strategy_type,
                 threshold_value, initial_capital, agent_filter,
                 final_value, total_return, cagr, alpha, beta,
                 sharpe_ratio, sortino_ratio, calmar_ratio,
                 max_drawdown, max_drawdown_days, var_95,
                 total_trades, winning_trades, losing_trades,
                 profit_factor, win_rate, avg_holding_days,
                 avg_win, avg_loss, benchmark_return, excess_return,
                 created_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        m = result.metrics
        _, backtest_id = await pool.execute(
            run_query,
            (
                result.ticker,
                result.benchmark,
                result.start_date,
                result.end_date,
                result.strategy_type.value,
                _r(result.threshold_value, 2),
                _r(result.initial_capital, 2),
                json.dumps(result.agent_filter) if result.agent_filter else None,
                _r(result.final_value, 2),
                _r(m.total_return_pct, 4),
                _r(m.cagr, 4),
                _r(m.alpha, 4),
                _r(m.beta, 4),
                _r(m.sharpe_ratio, 4),
                _r(m.sortino_ratio, 4),
                _r(m.calmar_ratio, 4),
                _r(m.max_drawdown, 4),
                m.max_drawdown_duration_days,
                _r(m.var_95, 4),
                m.total_trades,
                m.winning_trades,
                m.losing_trades,
                _r(m.profit_factor, 4),
                min(_r(m.win_rate, 4) or 0, 99.9999),
                m.avg_holding_days,
                _r(m.avg_win, 2),
                _r(m.avg_loss, 2),
                _r(m.benchmark_return, 4),
                _r(m.excess_return, 4),
                result.created_at,
            ),
        )

        # Insert trades
        if result.trades:
            trade_query = """
                INSERT INTO backtest_trades
                    (backtest_id, trade_date, trade_type, price,
                     quantity, `signal`, score, realized_pnl)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            for trade in result.trades:
                await pool.execute(
                    trade_query,
                    (
                        backtest_id,
                        trade.trade_date,
                        trade.trade_type.value,
                        _r(trade.price, 4),
                        _r(trade.quantity, 8),
                        trade.signal.value if trade.signal else None,
                        _r(trade.score, 2),
                        _r(trade.realized_pnl, 2),
                    ),
                )

        # Insert snapshots (sample to avoid too many rows)
        if result.daily_snapshots:
            snapshot_query = """
                INSERT INTO backtest_snapshots
                    (backtest_id, snapshot_date, portfolio_value, cash,
                     position_value, position_qty, benchmark_value, drawdown)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            # Sample snapshots: keep first, last, and every Nth day
            sample_interval = max(1, len(result.daily_snapshots) // 100)
            sampled = []
            for i, snap in enumerate(result.daily_snapshots):
                if i == 0 or i == len(result.daily_snapshots) - 1 or i % sample_interval == 0:
                    sampled.append(snap)

            for snapshot in sampled:
                await pool.execute(
                    snapshot_query,
                    (
                        backtest_id,
                        snapshot.date,
                        _r(snapshot.portfolio_value, 2),
                        _r(snapshot.cash, 2),
                        _r(snapshot.position_value, 2),
                        _r(snapshot.position_qty, 8),
                        _r(snapshot.benchmark_value, 2),
                        _r(snapshot.drawdown, 4),
                    ),
                )

        return backtest_id

    async def get_backtest(self, backtest_id: int) -> BacktestResult | None:
        """
        Retrieve a backtest by ID.

        Args:
            backtest_id: The backtest ID

        Returns:
            BacktestResult if found, None otherwise
        """
        pool = await self._ensure_pool()

        run_query = """
            SELECT id, ticker, benchmark, start_date, end_date,
                   strategy_type, threshold_value, initial_capital, agent_filter,
                   final_value, total_return, cagr, alpha, beta,
                   sharpe_ratio, sortino_ratio, calmar_ratio,
                   max_drawdown, max_drawdown_days, var_95,
                   total_trades, winning_trades, losing_trades,
                   profit_factor, win_rate, avg_holding_days,
                   avg_win, avg_loss, benchmark_return, excess_return,
                   created_at
            FROM backtest_runs
            WHERE id = %s
        """

        trade_query = """
            SELECT trade_date, trade_type, price, quantity,
                   `signal`, score, realized_pnl
            FROM backtest_trades
            WHERE backtest_id = %s
            ORDER BY trade_date
        """

        snapshot_query = """
            SELECT snapshot_date, portfolio_value, cash, position_value,
                   position_qty, benchmark_value, drawdown
            FROM backtest_snapshots
            WHERE backtest_id = %s
            ORDER BY snapshot_date
        """

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(run_query, (backtest_id,))
                row = await cursor.fetchone()

                if not row:
                    return None

                # Get trades
                await cursor.execute(trade_query, (backtest_id,))
                trade_rows = await cursor.fetchall()

                trades = []
                for t_row in trade_rows:
                    trades.append(
                        BacktestTrade(
                            trade_date=t_row[0],
                            trade_type=TradeAction(t_row[1]),
                            price=Decimal(str(t_row[2])),
                            quantity=Decimal(str(t_row[3])),
                            signal=SignalType(t_row[4]) if t_row[4] else None,
                            score=Decimal(str(t_row[5])) if t_row[5] else None,
                            realized_pnl=Decimal(str(t_row[6])) if t_row[6] else None,
                        )
                    )

                # Get snapshots
                await cursor.execute(snapshot_query, (backtest_id,))
                snap_rows = await cursor.fetchall()

                snapshots = []
                for s_row in snap_rows:
                    snapshots.append(
                        DailySnapshot(
                            date=s_row[0],
                            portfolio_value=Decimal(str(s_row[1])),
                            cash=Decimal(str(s_row[2])),
                            position_value=Decimal(str(s_row[3])),
                            position_qty=Decimal(str(s_row[4])),
                            benchmark_value=Decimal(str(s_row[5])),
                            drawdown=Decimal(str(s_row[6])),
                        )
                    )

                # Build metrics from row
                metrics = BacktestMetrics(
                    total_return=Decimal(str(row[9])) - Decimal(str(row[7])),  # final - initial
                    total_return_pct=Decimal(str(row[10])) if row[10] else Decimal("0"),
                    cagr=Decimal(str(row[11])) if row[11] else Decimal("0"),
                    alpha=Decimal(str(row[12])) if row[12] else Decimal("0"),
                    beta=Decimal(str(row[13])) if row[13] else Decimal("1"),
                    sharpe_ratio=Decimal(str(row[14])) if row[14] else Decimal("0"),
                    sortino_ratio=Decimal(str(row[15])) if row[15] else Decimal("0"),
                    calmar_ratio=Decimal(str(row[16])) if row[16] else Decimal("0"),
                    max_drawdown=Decimal(str(row[17])) if row[17] else Decimal("0"),
                    max_drawdown_duration_days=row[18] or 0,
                    var_95=Decimal(str(row[19])) if row[19] else Decimal("0"),
                    total_trades=row[20] or 0,
                    winning_trades=row[21] or 0,
                    losing_trades=row[22] or 0,
                    profit_factor=Decimal(str(row[23])) if row[23] else Decimal("0"),
                    win_rate=Decimal(str(row[24])) if row[24] else Decimal("0"),
                    avg_holding_days=row[25] or 0,
                    avg_win=Decimal(str(row[26])) if row[26] else Decimal("0"),
                    avg_loss=Decimal(str(row[27])) if row[27] else Decimal("0"),
                    benchmark_return=Decimal(str(row[28])) if row[28] else Decimal("0"),
                    excess_return=Decimal(str(row[29])) if row[29] else Decimal("0"),
                )

                return BacktestResult(
                    id=row[0],
                    ticker=row[1],
                    benchmark=row[2],
                    start_date=row[3],
                    end_date=row[4],
                    strategy_type=BacktestStrategyType(row[5]),
                    threshold_value=Decimal(str(row[6])) if row[6] else None,
                    initial_capital=Decimal(str(row[7])),
                    final_value=Decimal(str(row[9])),
                    agent_filter=json.loads(row[8]) if row[8] else None,
                    metrics=metrics,
                    trades=trades,
                    daily_snapshots=snapshots,
                    created_at=row[30] or datetime.now(),
                )

    async def list_backtests(
        self,
        ticker: str | None = None,
        strategy: BacktestStrategyType | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List backtest runs with optional filtering.

        Args:
            ticker: Filter by ticker
            strategy: Filter by strategy type
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of backtest summaries
        """
        pool = await self._ensure_pool()

        conditions = []
        params: list[Any] = []

        if ticker:
            conditions.append("ticker = %s")
            params.append(ticker.upper())

        if strategy:
            conditions.append("strategy_type = %s")
            params.append(strategy.value)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT id, ticker, benchmark, start_date, end_date,
                   strategy_type, initial_capital, final_value,
                   total_return, sharpe_ratio, max_drawdown,
                   total_trades, win_rate, created_at
            FROM backtest_runs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        rows = await pool.fetch_all(query, tuple(params))

        return [
            {
                "id": row["id"],
                "ticker": row["ticker"],
                "benchmark": row["benchmark"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "strategy_type": row["strategy_type"],
                "initial_capital": Decimal(str(row["initial_capital"])) if row["initial_capital"] else Decimal("0"),
                "final_value": Decimal(str(row["final_value"])) if row["final_value"] else Decimal("0"),
                "total_return": Decimal(str(row["total_return"])) if row["total_return"] else Decimal("0"),
                "sharpe_ratio": Decimal(str(row["sharpe_ratio"])) if row["sharpe_ratio"] else Decimal("0"),
                "max_drawdown": Decimal(str(row["max_drawdown"])) if row["max_drawdown"] else Decimal("0"),
                "total_trades": row["total_trades"] or 0,
                "win_rate": Decimal(str(row["win_rate"])) if row["win_rate"] else Decimal("0"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def delete_backtest(self, backtest_id: int) -> bool:
        """
        Delete a backtest run.

        Args:
            backtest_id: The backtest ID to delete

        Returns:
            True if deleted, False if not found
        """
        pool = await self._ensure_pool()

        query = "DELETE FROM backtest_runs WHERE id = %s"

        affected_rows, _ = await pool.execute(query, (backtest_id,))
        return affected_rows > 0
