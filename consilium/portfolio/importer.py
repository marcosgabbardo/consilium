"""CSV import functionality for portfolios."""

import csv
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from consilium.core.portfolio_models import (
    PortfolioPosition,
    CSVColumnMapping,
    CSVImportResult,
    CSVImportError,
)
from consilium.core.exceptions import PortfolioImportError


class CSVImporter:
    """Imports portfolio positions from CSV files."""

    # Column name aliases for auto-detection
    TICKER_ALIASES = {
        "ticker", "symbol", "stock", "security", "code", "asset",
        "instrument", "name", "share", "equity",
    }
    QUANTITY_ALIASES = {
        "quantity", "qty", "shares", "units", "amount", "position",
        "holding", "volume", "count", "num_shares",
    }
    PRICE_ALIASES = {
        "purchase_price", "price", "cost", "avg_cost", "buy_price",
        "cost_basis", "avg_price", "average_cost", "entry_price", "unit_cost",
    }
    DATE_ALIASES = {
        "purchase_date", "date", "buy_date", "trade_date", "acquired",
        "acquisition_date", "entry_date", "transaction_date",
    }
    NOTES_ALIASES = {
        "notes", "note", "comment", "comments", "description", "memo",
        "remarks", "info",
    }

    # Supported date formats
    DATE_FORMATS = [
        "%Y-%m-%d",       # 2024-01-15
        "%m/%d/%Y",       # 01/15/2024
        "%d/%m/%Y",       # 15/01/2024
        "%Y/%m/%d",       # 2024/01/15
        "%m-%d-%Y",       # 01-15-2024
        "%d-%m-%Y",       # 15-01-2024
        "%Y.%m.%d",       # 2024.01.15
        "%d.%m.%Y",       # 15.01.2024
        "%B %d, %Y",      # January 15, 2024
        "%b %d, %Y",      # Jan 15, 2024
        "%d %B %Y",       # 15 January 2024
        "%d %b %Y",       # 15 Jan 2024
    ]

    def __init__(self) -> None:
        self._detected_mapping: CSVColumnMapping | None = None

    def detect_columns(self, headers: list[str]) -> CSVColumnMapping:
        """Auto-detect column mapping from headers."""
        # Normalize headers
        normalized = {h.lower().strip().replace(" ", "_"): h for h in headers}

        ticker_col = self._find_column(normalized, self.TICKER_ALIASES)
        quantity_col = self._find_column(normalized, self.QUANTITY_ALIASES)
        price_col = self._find_column(normalized, self.PRICE_ALIASES)
        date_col = self._find_column(normalized, self.DATE_ALIASES)
        notes_col = self._find_column(normalized, self.NOTES_ALIASES)

        if not ticker_col:
            raise PortfolioImportError(
                "Cannot detect ticker column",
                field="ticker",
                details={"headers": headers},
            )
        if not quantity_col:
            raise PortfolioImportError(
                "Cannot detect quantity column",
                field="quantity",
                details={"headers": headers},
            )
        if not price_col:
            raise PortfolioImportError(
                "Cannot detect price column",
                field="price",
                details={"headers": headers},
            )
        if not date_col:
            raise PortfolioImportError(
                "Cannot detect date column",
                field="date",
                details={"headers": headers},
            )

        self._detected_mapping = CSVColumnMapping(
            ticker=ticker_col,
            quantity=quantity_col,
            purchase_price=price_col,
            purchase_date=date_col,
            notes=notes_col,
        )
        return self._detected_mapping

    def preview(
        self,
        file_path: Path,
        mapping: CSVColumnMapping | None = None,
        limit: int = 5,
    ) -> tuple[CSVColumnMapping, list[dict[str, Any]]]:
        """Preview CSV file with detected mapping and sample rows."""
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            if mapping:
                detected = mapping
            else:
                detected = self.detect_columns(headers)

            rows = []
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                rows.append(self._parse_row(row, detected, i + 2))

        return detected, rows

    def parse_file(
        self,
        file_path: Path,
        portfolio_id: int,
        mapping: CSVColumnMapping | None = None,
    ) -> CSVImportResult:
        """Parse entire CSV file and return import result."""
        positions: list[PortfolioPosition] = []
        errors: list[CSVImportError] = []
        total_rows = 0

        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            if mapping:
                column_mapping = mapping
            else:
                column_mapping = self.detect_columns(headers)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                total_rows += 1
                try:
                    parsed = self._parse_row(row, column_mapping, row_num)
                    position = PortfolioPosition(
                        portfolio_id=portfolio_id,
                        ticker=parsed["ticker"],
                        quantity=parsed["quantity"],
                        purchase_price=parsed["price"],
                        purchase_date=parsed["date"],
                        notes=parsed.get("notes"),
                    )
                    positions.append(position)
                except ValueError as e:
                    # Extract field info from error if available
                    error_str = str(e)
                    field = "unknown"
                    value = ""

                    if "ticker" in error_str.lower():
                        field = "ticker"
                        value = row.get(column_mapping.ticker, "")
                    elif "quantity" in error_str.lower():
                        field = "quantity"
                        value = row.get(column_mapping.quantity, "")
                    elif "price" in error_str.lower():
                        field = "price"
                        value = row.get(column_mapping.purchase_price, "")
                    elif "date" in error_str.lower():
                        field = "date"
                        value = row.get(column_mapping.purchase_date, "")

                    errors.append(CSVImportError(
                        row_number=row_num,
                        field=field,
                        value=str(value),
                        error=str(e),
                    ))

        return CSVImportResult(
            portfolio_id=portfolio_id,
            file_name=file_path.name,
            records_total=total_rows,
            records_success=len(positions),
            records_failed=len(errors),
            positions_created=positions,
            errors=errors,
            column_mapping=column_mapping,
        )

    def _find_column(
        self,
        normalized_headers: dict[str, str],
        aliases: set[str],
    ) -> str | None:
        """Find column by matching against aliases."""
        for alias in aliases:
            if alias in normalized_headers:
                return normalized_headers[alias]
        return None

    def _parse_row(
        self,
        row: dict[str, str],
        mapping: CSVColumnMapping,
        row_num: int,
    ) -> dict[str, Any]:
        """Parse a single row using the column mapping."""
        result: dict[str, Any] = {}

        # Parse ticker (required)
        ticker = row.get(mapping.ticker, "").strip().upper()
        if not ticker:
            raise ValueError(f"Row {row_num}: Empty ticker value")
        result["ticker"] = ticker

        # Parse quantity (required)
        qty_str = row.get(mapping.quantity, "").strip()
        qty_str = self._clean_number(qty_str)
        if not qty_str:
            raise ValueError(f"Row {row_num}: Empty quantity value")
        try:
            quantity = Decimal(qty_str)
            if quantity <= 0:
                raise ValueError(f"Row {row_num}: Quantity must be positive")
            result["quantity"] = quantity
        except InvalidOperation:
            raise ValueError(f"Row {row_num}: Invalid quantity '{qty_str}'")

        # Parse price (required)
        price_str = row.get(mapping.purchase_price, "").strip()
        price_str = self._clean_number(price_str)
        if not price_str:
            raise ValueError(f"Row {row_num}: Empty price value")
        try:
            price = Decimal(price_str)
            if price <= 0:
                raise ValueError(f"Row {row_num}: Price must be positive")
            result["price"] = price
        except InvalidOperation:
            raise ValueError(f"Row {row_num}: Invalid price '{price_str}'")

        # Parse date (required)
        date_str = row.get(mapping.purchase_date, "").strip()
        if not date_str:
            raise ValueError(f"Row {row_num}: Empty date value")
        parsed_date = self._parse_date(date_str)
        if not parsed_date:
            raise ValueError(f"Row {row_num}: Cannot parse date '{date_str}'")
        result["date"] = parsed_date

        # Parse notes (optional)
        if mapping.notes:
            notes = row.get(mapping.notes, "").strip()
            if notes:
                result["notes"] = notes

        return result

    def _clean_number(self, value: str) -> str:
        """Clean number string (remove currency symbols, commas)."""
        # Remove currency symbols and spaces
        value = re.sub(r"[$£€¥R\s]", "", value)
        # Remove thousand separators (but keep decimal point)
        # Handle both , and . as thousand separators
        if "," in value and "." in value:
            # Assume format like 1,234.56
            value = value.replace(",", "")
        elif "," in value and len(value.split(",")[-1]) == 2:
            # European format: 1.234,56 -> 1234.56
            value = value.replace(".", "").replace(",", ".")
        elif "," in value:
            # Might be thousand separator only: 1,234
            value = value.replace(",", "")
        return value

    def _parse_date(self, date_str: str) -> date | None:
        """Try to parse date string using multiple formats."""
        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.date()
            except ValueError:
                continue
        return None
