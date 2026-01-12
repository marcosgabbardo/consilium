"""Data access layer for portfolio operations."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from consilium.db.connection import DatabasePool
from consilium.core.portfolio_models import (
    Portfolio,
    PortfolioPosition,
    PortfolioTransaction,
    TransactionType,
    CSVImportResult,
    CSVImportError,
    CSVColumnMapping,
)


class PortfolioRepository:
    """Repository for portfolio and position operations."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    # ========== Portfolio CRUD ==========

    async def create_portfolio(
        self,
        name: str,
        description: str | None = None,
        currency: str = "USD",
    ) -> int:
        """Create a new portfolio. Returns portfolio_id."""
        _, portfolio_id = await self._pool.execute(
            """
            INSERT INTO portfolios (name, description, currency)
            VALUES (%s, %s, %s)
            """,
            (name.strip(), description, currency.upper()),
        )
        return portfolio_id

    async def get_portfolio(self, portfolio_id: int) -> Portfolio | None:
        """Get portfolio by ID."""
        result = await self._pool.fetch_one(
            "SELECT * FROM portfolios WHERE id = %s",
            (portfolio_id,),
        )
        if result:
            return Portfolio(**result)
        return None

    async def get_portfolio_by_name(self, name: str) -> Portfolio | None:
        """Get portfolio by name."""
        result = await self._pool.fetch_one(
            "SELECT * FROM portfolios WHERE name = %s",
            (name.strip(),),
        )
        if result:
            return Portfolio(**result)
        return None

    async def list_portfolios(self) -> list[Portfolio]:
        """List all portfolios."""
        results = await self._pool.fetch_all(
            "SELECT * FROM portfolios ORDER BY name"
        )
        return [Portfolio(**r) for r in results]

    async def update_portfolio(
        self,
        portfolio_id: int,
        name: str | None = None,
        description: str | None = None,
        currency: str | None = None,
    ) -> bool:
        """Update portfolio. Returns True if updated."""
        updates = []
        params = []

        if name is not None:
            updates.append("name = %s")
            params.append(name.strip())
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if currency is not None:
            updates.append("currency = %s")
            params.append(currency.upper())

        if not updates:
            return False

        params.append(portfolio_id)
        rows, _ = await self._pool.execute(
            f"UPDATE portfolios SET {', '.join(updates)} WHERE id = %s",
            tuple(params),
        )
        return rows > 0

    async def delete_portfolio(self, portfolio_id: int) -> bool:
        """Delete a portfolio and all its positions."""
        rows, _ = await self._pool.execute(
            "DELETE FROM portfolios WHERE id = %s",
            (portfolio_id,),
        )
        return rows > 0

    async def delete_portfolio_by_name(self, name: str) -> bool:
        """Delete a portfolio by name."""
        rows, _ = await self._pool.execute(
            "DELETE FROM portfolios WHERE name = %s",
            (name.strip(),),
        )
        return rows > 0

    # ========== Position CRUD ==========

    async def add_position(
        self,
        portfolio_id: int,
        ticker: str,
        quantity: Decimal,
        purchase_price: Decimal,
        purchase_date: date,
        notes: str | None = None,
    ) -> int:
        """Add a position to a portfolio. Returns position_id."""
        _, position_id = await self._pool.execute(
            """
            INSERT INTO portfolio_positions
            (portfolio_id, ticker, quantity, purchase_price, purchase_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                portfolio_id,
                ticker.upper().strip(),
                float(quantity),
                float(purchase_price),
                purchase_date,
                notes,
            ),
        )
        return position_id

    async def get_position(self, position_id: int) -> PortfolioPosition | None:
        """Get a position by ID."""
        result = await self._pool.fetch_one(
            "SELECT * FROM portfolio_positions WHERE id = %s",
            (position_id,),
        )
        if result:
            return self._map_position(result)
        return None

    async def get_positions(self, portfolio_id: int) -> list[PortfolioPosition]:
        """Get all positions in a portfolio."""
        results = await self._pool.fetch_all(
            """
            SELECT * FROM portfolio_positions
            WHERE portfolio_id = %s
            ORDER BY ticker, purchase_date
            """,
            (portfolio_id,),
        )
        return [self._map_position(r) for r in results]

    async def get_position_by_ticker(
        self,
        portfolio_id: int,
        ticker: str,
    ) -> list[PortfolioPosition]:
        """Get all positions for a specific ticker in a portfolio."""
        results = await self._pool.fetch_all(
            """
            SELECT * FROM portfolio_positions
            WHERE portfolio_id = %s AND ticker = %s
            ORDER BY purchase_date
            """,
            (portfolio_id, ticker.upper().strip()),
        )
        return [self._map_position(r) for r in results]

    async def update_position(
        self,
        position_id: int,
        quantity: Decimal | None = None,
        purchase_price: Decimal | None = None,
        purchase_date: date | None = None,
        notes: str | None = None,
    ) -> bool:
        """Update a position. Returns True if updated."""
        updates = []
        params = []

        if quantity is not None:
            updates.append("quantity = %s")
            params.append(float(quantity))
        if purchase_price is not None:
            updates.append("purchase_price = %s")
            params.append(float(purchase_price))
        if purchase_date is not None:
            updates.append("purchase_date = %s")
            params.append(purchase_date)
        if notes is not None:
            updates.append("notes = %s")
            params.append(notes)

        if not updates:
            return False

        params.append(position_id)
        rows, _ = await self._pool.execute(
            f"UPDATE portfolio_positions SET {', '.join(updates)} WHERE id = %s",
            tuple(params),
        )
        return rows > 0

    async def delete_position(self, position_id: int) -> bool:
        """Delete a single position."""
        rows, _ = await self._pool.execute(
            "DELETE FROM portfolio_positions WHERE id = %s",
            (position_id,),
        )
        return rows > 0

    async def delete_positions_by_ticker(
        self,
        portfolio_id: int,
        ticker: str,
    ) -> int:
        """Delete all positions for a ticker. Returns count deleted."""
        rows, _ = await self._pool.execute(
            """
            DELETE FROM portfolio_positions
            WHERE portfolio_id = %s AND ticker = %s
            """,
            (portfolio_id, ticker.upper().strip()),
        )
        return rows

    async def update_position_quantity(
        self,
        position_id: int,
        new_quantity: Decimal,
    ) -> bool:
        """Update the quantity of a position (used after partial sells)."""
        rows, _ = await self._pool.execute(
            """
            UPDATE portfolio_positions
            SET quantity = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (new_quantity, position_id),
        )
        return rows > 0

    async def get_unique_tickers(self, portfolio_id: int) -> list[str]:
        """Get list of unique tickers in a portfolio."""
        results = await self._pool.fetch_all(
            """
            SELECT DISTINCT ticker FROM portfolio_positions
            WHERE portfolio_id = %s
            ORDER BY ticker
            """,
            (portfolio_id,),
        )
        return [r["ticker"] for r in results]

    async def get_aggregated_positions(
        self,
        portfolio_id: int,
    ) -> list[dict[str, Any]]:
        """Get aggregated positions (sum quantities, average price per ticker)."""
        results = await self._pool.fetch_all(
            """
            SELECT
                ticker,
                SUM(quantity) as total_quantity,
                SUM(quantity * purchase_price) / SUM(quantity) as avg_price,
                MIN(purchase_date) as first_purchase,
                MAX(purchase_date) as last_purchase,
                COUNT(*) as lot_count
            FROM portfolio_positions
            WHERE portfolio_id = %s
            GROUP BY ticker
            ORDER BY ticker
            """,
            (portfolio_id,),
        )
        return results

    # ========== Import History ==========

    async def save_import(
        self,
        portfolio_id: int,
        file_name: str,
        records_total: int,
        records_success: int,
        records_failed: int,
        errors: list[CSVImportError] | None = None,
        column_mapping: CSVColumnMapping | None = None,
    ) -> int:
        """Save import history record. Returns import_id."""
        errors_json = None
        if errors:
            errors_json = json.dumps([e.model_dump() for e in errors])

        mapping_json = None
        if column_mapping:
            mapping_json = json.dumps(column_mapping.model_dump())

        _, import_id = await self._pool.execute(
            """
            INSERT INTO portfolio_imports
            (portfolio_id, file_name, records_total, records_success, records_failed, errors_json, column_mapping)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                portfolio_id,
                file_name,
                records_total,
                records_success,
                records_failed,
                errors_json,
                mapping_json,
            ),
        )
        return import_id

    async def get_import_history(
        self,
        portfolio_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get import history for a portfolio."""
        results = await self._pool.fetch_all(
            """
            SELECT id, file_name, records_total, records_success, records_failed, imported_at
            FROM portfolio_imports
            WHERE portfolio_id = %s
            ORDER BY imported_at DESC
            LIMIT %s
            """,
            (portfolio_id, limit),
        )
        return results

    async def get_import_details(self, import_id: int) -> dict[str, Any] | None:
        """Get details of a specific import including errors."""
        result = await self._pool.fetch_one(
            "SELECT * FROM portfolio_imports WHERE id = %s",
            (import_id,),
        )
        if result:
            if result.get("errors_json"):
                result["errors"] = json.loads(result["errors_json"])
            if result.get("column_mapping"):
                result["column_mapping"] = json.loads(result["column_mapping"])
        return result

    # ========== Portfolio Analysis History ==========

    async def save_portfolio_analysis(
        self,
        portfolio_id: int,
        analysis_id: int | None,
        total_value: Decimal,
        total_cost_basis: Decimal,
        total_pnl: Decimal,
        total_pnl_percent: Decimal,
        portfolio_signal: str,
        portfolio_score: Decimal,
        sector_allocation: list[dict[str, Any]] | None = None,
        position_recommendations: list[dict[str, Any]] | None = None,
    ) -> int:
        """Save portfolio analysis result. Returns analysis record ID."""
        _, record_id = await self._pool.execute(
            """
            INSERT INTO portfolio_analysis
            (portfolio_id, analysis_id, total_value, total_cost_basis, total_pnl, total_pnl_percent,
             portfolio_signal, portfolio_score, sector_allocation, position_recommendations)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                portfolio_id,
                analysis_id,
                float(total_value),
                float(total_cost_basis),
                float(total_pnl),
                float(total_pnl_percent),
                portfolio_signal,
                float(portfolio_score),
                json.dumps(sector_allocation) if sector_allocation else None,
                json.dumps(position_recommendations) if position_recommendations else None,
            ),
        )
        return record_id

    async def get_portfolio_analysis_history(
        self,
        portfolio_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get analysis history for a portfolio."""
        results = await self._pool.fetch_all(
            """
            SELECT id, total_value, total_cost_basis, total_pnl, total_pnl_percent,
                   portfolio_signal, portfolio_score, analyzed_at
            FROM portfolio_analysis
            WHERE portfolio_id = %s
            ORDER BY analyzed_at DESC
            LIMIT %s
            """,
            (portfolio_id, limit),
        )
        return results

    async def get_portfolio_analysis_details(
        self,
        record_id: int,
    ) -> dict[str, Any] | None:
        """Get detailed analysis record."""
        result = await self._pool.fetch_one(
            "SELECT * FROM portfolio_analysis WHERE id = %s",
            (record_id,),
        )
        if result:
            if result.get("sector_allocation"):
                result["sector_allocation"] = json.loads(result["sector_allocation"])
            if result.get("position_recommendations"):
                result["position_recommendations"] = json.loads(result["position_recommendations"])
        return result

    # ========== Transaction CRUD ==========

    async def add_transaction(
        self,
        portfolio_id: int,
        ticker: str,
        transaction_type: TransactionType,
        quantity: Decimal,
        price: Decimal,
        transaction_date: date,
        fees: Decimal = Decimal("0"),
        notes: str | None = None,
        realized_pnl: Decimal | None = None,
        holding_period_days: int | None = None,
        cost_basis_used: Decimal | None = None,
    ) -> int:
        """Add a transaction to a portfolio. Returns transaction_id."""
        _, transaction_id = await self._pool.execute(
            """
            INSERT INTO portfolio_transactions
            (portfolio_id, ticker, transaction_type, quantity, price, transaction_date,
             fees, notes, realized_pnl, holding_period_days, cost_basis_used)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                portfolio_id,
                ticker.upper().strip(),
                transaction_type.value,
                float(quantity),
                float(price),
                transaction_date,
                float(fees),
                notes,
                float(realized_pnl) if realized_pnl is not None else None,
                holding_period_days,
                float(cost_basis_used) if cost_basis_used is not None else None,
            ),
        )
        return transaction_id

    async def get_transaction(self, transaction_id: int) -> PortfolioTransaction | None:
        """Get a transaction by ID."""
        result = await self._pool.fetch_one(
            "SELECT * FROM portfolio_transactions WHERE id = %s",
            (transaction_id,),
        )
        if result:
            return self._map_transaction(result)
        return None

    async def get_transactions(
        self,
        portfolio_id: int,
        ticker: str | None = None,
        transaction_type: TransactionType | None = None,
        limit: int | None = None,
    ) -> list[PortfolioTransaction]:
        """Get transactions for a portfolio with optional filters."""
        query = "SELECT * FROM portfolio_transactions WHERE portfolio_id = %s"
        params: list[Any] = [portfolio_id]

        if ticker:
            query += " AND ticker = %s"
            params.append(ticker.upper().strip())

        if transaction_type:
            query += " AND transaction_type = %s"
            params.append(transaction_type.value)

        query += " ORDER BY transaction_date DESC, id DESC"

        if limit:
            query += " LIMIT %s"
            params.append(limit)

        results = await self._pool.fetch_all(query, tuple(params))
        return [self._map_transaction(r) for r in results]

    async def get_buy_transactions(
        self,
        portfolio_id: int,
        ticker: str,
    ) -> list[PortfolioTransaction]:
        """Get all buy transactions for a ticker (for P&L calculation)."""
        results = await self._pool.fetch_all(
            """
            SELECT * FROM portfolio_transactions
            WHERE portfolio_id = %s AND ticker = %s AND transaction_type = 'BUY'
            ORDER BY transaction_date ASC, id ASC
            """,
            (portfolio_id, ticker.upper().strip()),
        )
        return [self._map_transaction(r) for r in results]

    async def delete_transaction(self, transaction_id: int) -> bool:
        """Delete a single transaction."""
        rows, _ = await self._pool.execute(
            "DELETE FROM portfolio_transactions WHERE id = %s",
            (transaction_id,),
        )
        return rows > 0

    async def get_transaction_summary(
        self,
        portfolio_id: int,
    ) -> dict[str, Any]:
        """Get transaction summary statistics for a portfolio."""
        result = await self._pool.fetch_one(
            """
            SELECT
                COUNT(*) as total_transactions,
                SUM(CASE WHEN transaction_type = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN transaction_type = 'SELL' THEN 1 ELSE 0 END) as sell_count,
                SUM(CASE WHEN transaction_type = 'SELL' AND realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN transaction_type = 'SELL' AND realized_pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                COALESCE(SUM(CASE WHEN transaction_type = 'SELL' THEN realized_pnl ELSE 0 END), 0) as total_realized_pnl,
                COALESCE(SUM(fees), 0) as total_fees,
                AVG(CASE WHEN transaction_type = 'SELL' THEN holding_period_days ELSE NULL END) as avg_holding_days
            FROM portfolio_transactions
            WHERE portfolio_id = %s
            """,
            (portfolio_id,),
        )
        return result or {}

    async def get_realized_pnl_by_ticker(
        self,
        portfolio_id: int,
    ) -> list[dict[str, Any]]:
        """Get realized P&L breakdown by ticker."""
        results = await self._pool.fetch_all(
            """
            SELECT
                ticker,
                SUM(CASE WHEN realized_pnl IS NOT NULL THEN realized_pnl ELSE 0 END) as realized_pnl,
                SUM(fees) as total_fees,
                COUNT(CASE WHEN transaction_type = 'SELL' THEN 1 END) as sell_count,
                SUM(CASE WHEN transaction_type = 'SELL' AND realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN transaction_type = 'SELL' AND realized_pnl < 0 THEN 1 ELSE 0 END) as losses
            FROM portfolio_transactions
            WHERE portfolio_id = %s
            GROUP BY ticker
            ORDER BY realized_pnl DESC
            """,
            (portfolio_id,),
        )
        return results

    async def get_net_positions_from_transactions(
        self,
        portfolio_id: int,
    ) -> list[dict[str, Any]]:
        """
        Calculate net positions from transactions (buys - sells).
        Returns aggregated position data per ticker.
        """
        results = await self._pool.fetch_all(
            """
            SELECT
                ticker,
                SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE -quantity END) as net_quantity,
                SUM(CASE WHEN transaction_type = 'BUY' THEN quantity * price ELSE 0 END) as total_buy_cost,
                SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE 0 END) as total_bought,
                SUM(CASE WHEN transaction_type = 'SELL' THEN quantity ELSE 0 END) as total_sold,
                MIN(CASE WHEN transaction_type = 'BUY' THEN transaction_date END) as first_buy_date,
                MAX(transaction_date) as last_transaction_date
            FROM portfolio_transactions
            WHERE portfolio_id = %s
            GROUP BY ticker
            HAVING net_quantity > 0
            ORDER BY ticker
            """,
            (portfolio_id,),
        )

        # Calculate average cost per share for remaining positions
        processed = []
        for r in results:
            net_qty = Decimal(str(r["net_quantity"]))
            if net_qty > 0:
                # Need to calculate average cost of remaining shares
                avg_cost = await self._calculate_avg_cost_remaining(
                    portfolio_id, r["ticker"], net_qty
                )
                processed.append({
                    "ticker": r["ticker"],
                    "net_quantity": net_qty,
                    "avg_cost": avg_cost,
                    "cost_basis": net_qty * avg_cost,
                    "first_buy_date": r["first_buy_date"],
                    "last_transaction_date": r["last_transaction_date"],
                    "total_bought": Decimal(str(r["total_bought"])),
                    "total_sold": Decimal(str(r["total_sold"])),
                })

        return processed

    async def _calculate_avg_cost_remaining(
        self,
        portfolio_id: int,
        ticker: str,
        remaining_qty: Decimal,
    ) -> Decimal:
        """
        Calculate average cost of remaining shares using weighted average method.
        """
        # Get all buy transactions
        buys = await self.get_buy_transactions(portfolio_id, ticker)
        if not buys:
            return Decimal("0")

        # Total bought and total cost
        total_qty = sum(b.quantity for b in buys)
        total_cost = sum(b.quantity * b.price for b in buys)

        if total_qty == 0:
            return Decimal("0")

        # Weighted average price
        return total_cost / total_qty

    async def calculate_realized_pnl_for_sell(
        self,
        portfolio_id: int,
        ticker: str,
        sell_quantity: Decimal,
        sell_price: Decimal,
        sell_date: date,
    ) -> tuple[Decimal, int, Decimal]:
        """
        Calculate realized P&L for a sell transaction using weighted average method.

        Returns:
            tuple of (realized_pnl, holding_period_days, cost_basis_used)
        """
        # Get buy transactions
        buys = await self.get_buy_transactions(portfolio_id, ticker)
        if not buys:
            return Decimal("0"), 0, Decimal("0")

        # Calculate weighted average cost
        total_qty = sum(b.quantity for b in buys)
        total_cost = sum(b.quantity * b.price for b in buys)

        if total_qty == 0:
            return Decimal("0"), 0, Decimal("0")

        avg_cost = total_cost / total_qty

        # Calculate realized P&L
        realized_pnl = (sell_price - avg_cost) * sell_quantity

        # Calculate average holding period
        total_weighted_days = Decimal("0")
        for buy in buys:
            days_held = (sell_date - buy.transaction_date).days
            weight = buy.quantity / total_qty
            total_weighted_days += Decimal(str(days_held)) * weight

        holding_period_days = int(total_weighted_days)

        return realized_pnl, holding_period_days, avg_cost

    # ========== Helpers ==========

    def _map_position(self, row: dict[str, Any]) -> PortfolioPosition:
        """Map database row to PortfolioPosition model."""
        return PortfolioPosition(
            id=row["id"],
            portfolio_id=row["portfolio_id"],
            ticker=row["ticker"],
            quantity=Decimal(str(row["quantity"])),
            purchase_price=Decimal(str(row["purchase_price"])),
            purchase_date=row["purchase_date"],
            notes=row.get("notes"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def _map_transaction(self, row: dict[str, Any]) -> PortfolioTransaction:
        """Map database row to PortfolioTransaction model."""
        return PortfolioTransaction(
            id=row["id"],
            portfolio_id=row["portfolio_id"],
            ticker=row["ticker"],
            transaction_type=TransactionType(row["transaction_type"]),
            quantity=Decimal(str(row["quantity"])),
            price=Decimal(str(row["price"])),
            transaction_date=row["transaction_date"],
            fees=Decimal(str(row["fees"])) if row.get("fees") else Decimal("0"),
            notes=row.get("notes"),
            realized_pnl=Decimal(str(row["realized_pnl"])) if row.get("realized_pnl") else None,
            holding_period_days=row.get("holding_period_days"),
            cost_basis_used=Decimal(str(row["cost_basis_used"])) if row.get("cost_basis_used") else None,
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
