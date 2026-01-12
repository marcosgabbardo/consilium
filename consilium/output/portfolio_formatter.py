"""Rich console formatters for portfolio display."""

from decimal import Decimal

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.progress import Progress, BarColumn, TextColumn

from consilium.core.enums import SignalType, ConfidenceLevel
from consilium.core.portfolio_models import (
    Portfolio,
    PortfolioPosition,
    PortfolioTransaction,
    TransactionType,
    PortfolioSummary,
    PortfolioAnalysisResult,
    PortfolioPerformance,
    PositionWithAnalysis,
    PositionAction,
    SectorAllocation,
    ConcentrationRisk,
    CSVImportResult,
)


class PortfolioFormatter:
    """Formats portfolio data for Rich console output."""

    SIGNAL_COLORS = {
        SignalType.STRONG_BUY: "bold green",
        SignalType.BUY: "green",
        SignalType.HOLD: "yellow",
        SignalType.SELL: "red",
        SignalType.STRONG_SELL: "bold red",
    }

    CONFIDENCE_COLORS = {
        ConfidenceLevel.VERY_HIGH: "bold green",
        ConfidenceLevel.HIGH: "green",
        ConfidenceLevel.MEDIUM: "yellow",
        ConfidenceLevel.LOW: "red",
        ConfidenceLevel.VERY_LOW: "bold red",
    }

    ACTION_COLORS = {
        PositionAction.BUY_MORE: "green",
        PositionAction.HOLD: "yellow",
        PositionAction.REDUCE: "red",
        PositionAction.SELL_ALL: "bold red",
        PositionAction.REBALANCE: "cyan",
    }

    CONCENTRATION_COLORS = {
        ConcentrationRisk.LOW: "green",
        ConcentrationRisk.MEDIUM: "yellow",
        ConcentrationRisk.HIGH: "red",
        ConcentrationRisk.CRITICAL: "bold red",
    }

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    # ========== Portfolio List ==========

    def display_portfolio_list(self, portfolios: list[Portfolio]) -> None:
        """Display list of portfolios."""
        if not portfolios:
            self.console.print("[yellow]No portfolios found.[/yellow]")
            return

        table = Table(title="Portfolios")
        table.add_column("Name", style="cyan bold")
        table.add_column("Description", style="dim")
        table.add_column("Currency", justify="center")
        table.add_column("Created", justify="right")

        for p in portfolios:
            created = p.created_at.strftime("%Y-%m-%d") if p.created_at else "-"
            table.add_row(
                p.name,
                p.description or "-",
                p.currency,
                created,
            )

        self.console.print(table)

    # ========== Portfolio Summary ==========

    def display_portfolio_summary(
        self,
        summary: PortfolioSummary,
        show_positions: bool = True,
    ) -> None:
        """Display portfolio summary with holdings."""
        pnl_color = "green" if summary.total_pnl >= 0 else "red"
        pnl_sign = "+" if summary.total_pnl >= 0 else ""
        concentration_color = self.CONCENTRATION_COLORS.get(summary.concentration_risk, "white")

        # Header panel
        header_content = (
            f"[bold]{summary.portfolio.name}[/bold]\n"
            f"{summary.portfolio.description or ''}\n\n"
            f"Total Value: [bold]${summary.total_value:,.2f}[/bold] {summary.portfolio.currency}\n"
            f"Cost Basis: ${summary.total_cost_basis:,.2f}\n"
            f"P&L: [{pnl_color}]{pnl_sign}${summary.total_pnl:,.2f} ({pnl_sign}{summary.total_pnl_percent:.2f}%)[/{pnl_color}]\n\n"
            f"Positions: {summary.position_count}\n"
            f"Concentration Risk: [{concentration_color}]{summary.concentration_risk.value}[/{concentration_color}] "
            f"(Top 3: {summary.top_3_concentration:.1f}%)"
        )
        self.console.print(Panel(header_content, title="Portfolio Summary", border_style="blue"))

        # Sector allocation
        if summary.sector_allocations:
            self._display_sector_allocation(summary.sector_allocations)

        # Positions table
        if show_positions and summary.positions:
            self._display_positions_table(summary.positions)

    def _display_sector_allocation(self, allocations: list[SectorAllocation]) -> None:
        """Display sector allocation as horizontal bars."""
        self.console.print("\n[bold]Sector Allocation[/bold]")

        max_width = 30
        for alloc in allocations[:6]:  # Top 6 sectors
            bar_width = int((alloc.weight / 100) * max_width)
            bar = "█" * bar_width + "░" * (max_width - bar_width)
            self.console.print(
                f"  {alloc.sector:20} {bar} {alloc.weight:5.1f}% (${alloc.value:,.0f})"
            )

    def _display_positions_table(self, positions: list[PortfolioPosition]) -> None:
        """Display positions table."""
        self.console.print()

        table = Table(title="Holdings")
        table.add_column("Ticker", style="cyan bold")
        table.add_column("Shares", justify="right")
        table.add_column("Avg Cost", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Value", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("P&L %", justify="right")

        for p in positions:
            current = f"${p.current_price:.2f}" if p.current_price else "-"
            value = f"${p.current_value:,.2f}" if p.current_value else "-"

            if p.unrealized_pnl is not None:
                pnl_color = "green" if p.unrealized_pnl >= 0 else "red"
                pnl_sign = "+" if p.unrealized_pnl >= 0 else ""
                pnl = f"[{pnl_color}]{pnl_sign}${p.unrealized_pnl:,.2f}[/{pnl_color}]"
                pnl_pct = f"[{pnl_color}]{pnl_sign}{p.unrealized_pnl_percent:.1f}%[/{pnl_color}]"
            else:
                pnl = "-"
                pnl_pct = "-"

            table.add_row(
                p.ticker,
                f"{p.quantity:,.4f}".rstrip("0").rstrip("."),
                f"${p.purchase_price:.2f}",
                current,
                value,
                pnl,
                pnl_pct,
            )

        self.console.print(table)

    # ========== Portfolio Analysis ==========

    def display_portfolio_analysis(
        self,
        result: PortfolioAnalysisResult,
        verbose: bool = False,
    ) -> None:
        """Display full portfolio analysis result."""
        # Summary header
        signal_color = self.SIGNAL_COLORS.get(result.portfolio_signal, "white")
        confidence_color = self.CONFIDENCE_COLORS.get(result.portfolio_confidence, "white")
        pnl_color = "green" if result.total_pnl >= 0 else "red"
        pnl_sign = "+" if result.total_pnl >= 0 else ""
        concentration_color = self.CONCENTRATION_COLORS.get(result.concentration_risk, "white")

        summary_content = (
            f"[bold]{result.portfolio.name}[/bold]\n\n"
            f"Portfolio Signal: [{signal_color}]{result.portfolio_signal.value}[/{signal_color}]\n"
            f"Confidence: [{confidence_color}]{result.portfolio_confidence.value}[/{confidence_color}]\n"
            f"Score: {result.portfolio_score:.1f}\n\n"
            f"Total Value: [bold]${result.total_value:,.2f}[/bold]\n"
            f"P&L: [{pnl_color}]{pnl_sign}${result.total_pnl:,.2f} ({pnl_sign}{result.total_pnl_percent:.2f}%)[/{pnl_color}]\n\n"
            f"Concentration Risk: [{concentration_color}]{result.concentration_risk.value}[/{concentration_color}] "
            f"(Top 3: {result.top_3_concentration:.1f}%)"
        )
        self.console.print(Panel(summary_content, title="Portfolio Analysis Summary", border_style="blue"))

        # Sector allocation
        if result.sector_allocations:
            self._display_sector_allocation(result.sector_allocations)

        # Position recommendations table
        self._display_recommendations_table(result.positions_with_analysis)

        # Recommendations and warnings
        if result.key_recommendations or result.risk_warnings:
            self.console.print()
            cols = []

            if result.key_recommendations:
                recs = "\n".join(f"  • {r}" for r in result.key_recommendations)
                cols.append(Panel(f"[green]Recommendations[/green]\n{recs}", expand=True))

            if result.risk_warnings:
                warns = "\n".join(f"  • {w}" for w in result.risk_warnings)
                cols.append(Panel(f"[red]Warnings[/red]\n{warns}", expand=True))

            if cols:
                self.console.print(Columns(cols))

        # Verbose: show detailed per-position analysis
        if verbose:
            self._display_detailed_positions(result.positions_with_analysis)

    def _display_recommendations_table(
        self,
        positions: list[PositionWithAnalysis],
    ) -> None:
        """Display position recommendations table."""
        self.console.print()

        table = Table(title="Position Recommendations")
        table.add_column("Ticker", style="cyan bold")
        table.add_column("Signal", justify="center")
        table.add_column("Action", justify="center")
        table.add_column("Weight", justify="right")
        table.add_column("Target", justify="right")
        table.add_column("Upside", justify="right")
        table.add_column("P&L", justify="right")

        for pa in positions[:15]:  # Top 15 positions
            # Signal
            if pa.signal:
                signal_color = self.SIGNAL_COLORS.get(pa.signal, "white")
                signal = f"[{signal_color}]{pa.signal.value}[/{signal_color}]"
            else:
                signal = "[dim]-[/dim]"

            # Action
            action_color = self.ACTION_COLORS.get(pa.recommended_action, "white")
            action = f"[{action_color}]{pa.recommended_action.value}[/{action_color}]"

            # Target
            target = f"${pa.target_price:.2f}" if pa.target_price else "-"

            # Upside
            if pa.upside_potential is not None:
                upside_color = "green" if pa.upside_potential > 0 else "red"
                upside_sign = "+" if pa.upside_potential > 0 else ""
                upside = f"[{upside_color}]{upside_sign}{pa.upside_potential:.1f}%[/{upside_color}]"
            else:
                upside = "-"

            # P&L
            if pa.position.unrealized_pnl_percent is not None:
                pnl_color = "green" if pa.position.unrealized_pnl_percent >= 0 else "red"
                pnl_sign = "+" if pa.position.unrealized_pnl_percent >= 0 else ""
                pnl = f"[{pnl_color}]{pnl_sign}{pa.position.unrealized_pnl_percent:.1f}%[/{pnl_color}]"
            else:
                pnl = "-"

            table.add_row(
                pa.position.ticker,
                signal,
                action,
                f"{pa.weight_in_portfolio:.1f}%",
                target,
                upside,
                pnl,
            )

        self.console.print(table)

    def _display_detailed_positions(
        self,
        positions: list[PositionWithAnalysis],
    ) -> None:
        """Display detailed information for each position."""
        self.console.print("\n[bold]Detailed Position Analysis[/bold]")

        for pa in positions[:10]:  # Top 10 positions
            signal_color = self.SIGNAL_COLORS.get(pa.signal, "white") if pa.signal else "dim"
            action_color = self.ACTION_COLORS.get(pa.recommended_action, "white")

            content = (
                f"[bold]{pa.position.ticker}[/bold]"
                f" - {pa.position.company_name or 'N/A'}"
                f" ({pa.position.sector or 'Unknown'})\n\n"
                f"Signal: [{signal_color}]{pa.signal.value if pa.signal else 'N/A'}[/{signal_color}]\n"
                f"Action: [{action_color}]{pa.recommended_action.value}[/{action_color}]\n"
                f"Reason: {pa.action_reasoning or 'N/A'}\n\n"
                f"Shares: {pa.position.quantity:,.4f}\n"
                f"Avg Cost: ${pa.position.purchase_price:.2f}\n"
                f"Current: ${pa.position.current_price:.2f}" if pa.position.current_price else "Current: N/A"
            )

            self.console.print(Panel(content, border_style="dim"))

    # ========== CSV Import ==========

    def display_import_preview(
        self,
        mapping: dict,
        rows: list[dict],
    ) -> None:
        """Display CSV import preview."""
        self.console.print("\n[bold]Column Mapping Detected:[/bold]")
        self.console.print(f"  Ticker: {mapping.get('ticker', 'N/A')}")
        self.console.print(f"  Quantity: {mapping.get('quantity', 'N/A')}")
        self.console.print(f"  Price: {mapping.get('purchase_price', 'N/A')}")
        self.console.print(f"  Date: {mapping.get('purchase_date', 'N/A')}")
        if mapping.get('notes'):
            self.console.print(f"  Notes: {mapping['notes']}")

        self.console.print("\n[bold]Preview (first 5 rows):[/bold]")

        table = Table()
        table.add_column("Ticker", style="cyan")
        table.add_column("Quantity", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("Date", justify="center")

        for row in rows:
            table.add_row(
                row.get("ticker", "-"),
                f"{row.get('quantity', 0):,.4f}".rstrip("0").rstrip("."),
                f"${row.get('price', 0):.2f}",
                str(row.get("date", "-")),
            )

        self.console.print(table)

    def display_import_result(self, result: CSVImportResult) -> None:
        """Display CSV import result."""
        success_color = "green" if result.records_failed == 0 else "yellow"

        self.console.print(
            Panel(
                f"[bold]Import Complete[/bold]\n\n"
                f"File: {result.file_name}\n"
                f"Total Records: {result.records_total}\n"
                f"Successful: [{success_color}]{result.records_success}[/{success_color}]\n"
                f"Failed: {'[red]' + str(result.records_failed) + '[/red]' if result.records_failed else '0'}\n"
                f"Success Rate: {result.success_rate:.1f}%",
                title="Import Result",
                border_style="green" if result.records_failed == 0 else "yellow",
            )
        )

        # Show errors if any
        if result.errors:
            self.console.print("\n[red]Import Errors:[/red]")
            table = Table()
            table.add_column("Row", style="dim", width=6)
            table.add_column("Field", style="yellow")
            table.add_column("Value", style="dim")
            table.add_column("Error", style="red")

            for err in result.errors[:10]:  # Show first 10 errors
                table.add_row(
                    str(err.row_number),
                    err.field,
                    err.value[:20] + "..." if len(err.value) > 20 else err.value,
                    err.error,
                )

            self.console.print(table)

            if len(result.errors) > 10:
                self.console.print(f"[dim]...and {len(result.errors) - 10} more errors[/dim]")

    # ========== Import History ==========

    def display_import_history(self, history: list[dict]) -> None:
        """Display import history."""
        if not history:
            self.console.print("[yellow]No import history found.[/yellow]")
            return

        table = Table(title="Import History")
        table.add_column("ID", style="dim", width=6)
        table.add_column("File", style="cyan")
        table.add_column("Total", justify="right")
        table.add_column("Success", justify="right", style="green")
        table.add_column("Failed", justify="right")
        table.add_column("Date", justify="right")

        for h in history:
            failed_style = "red" if h.get("records_failed", 0) > 0 else "dim"
            table.add_row(
                str(h.get("id", "-")),
                h.get("file_name", "-"),
                str(h.get("records_total", 0)),
                str(h.get("records_success", 0)),
                f"[{failed_style}]{h.get('records_failed', 0)}[/{failed_style}]",
                h.get("imported_at").strftime("%Y-%m-%d %H:%M") if h.get("imported_at") else "-",
            )

        self.console.print(table)

    # ========== Analysis History ==========

    def display_analysis_history(self, history: list[dict]) -> None:
        """Display portfolio analysis history."""
        if not history:
            self.console.print("[yellow]No analysis history found.[/yellow]")
            return

        table = Table(title="Analysis History")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Signal", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Value", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("Date", justify="right")

        for h in history:
            signal = h.get("portfolio_signal", "-")
            signal_color = "green" if "BUY" in signal else "red" if "SELL" in signal else "yellow"

            pnl = h.get("total_pnl", 0)
            pnl_color = "green" if pnl >= 0 else "red"
            pnl_sign = "+" if pnl >= 0 else ""

            table.add_row(
                str(h.get("id", "-")),
                f"[{signal_color}]{signal}[/{signal_color}]",
                f"{h.get('portfolio_score', 0):.1f}",
                f"${h.get('total_value', 0):,.2f}",
                f"[{pnl_color}]{pnl_sign}${pnl:,.2f}[/{pnl_color}]",
                h.get("analyzed_at").strftime("%Y-%m-%d %H:%M") if h.get("analyzed_at") else "-",
            )

        self.console.print(table)

    # ========== Transactions ==========

    def display_transactions(
        self,
        transactions: list[PortfolioTransaction],
        ticker_filter: str | None = None,
        type_filter: TransactionType | None = None,
    ) -> None:
        """Display transaction history table."""
        if not transactions:
            self.console.print("[yellow]No transactions found.[/yellow]")
            return

        # Apply filters
        filtered = transactions
        if ticker_filter:
            filtered = [t for t in filtered if t.ticker == ticker_filter.upper()]
        if type_filter:
            filtered = [t for t in filtered if t.transaction_type == type_filter]

        if not filtered:
            self.console.print("[yellow]No transactions match the filters.[/yellow]")
            return

        title = "Transaction History"
        if ticker_filter:
            title += f" - {ticker_filter.upper()}"

        table = Table(title=title)
        table.add_column("Date", style="dim", width=10)
        table.add_column("Ticker", style="cyan bold", width=8)
        table.add_column("Type", justify="center", width=6)
        table.add_column("Qty", justify="right", width=10)
        table.add_column("Price", justify="right", width=10)
        table.add_column("Total", justify="right", width=12)
        table.add_column("Fees", justify="right", width=8)
        table.add_column("Realized P&L", justify="right", width=14)

        for t in filtered:
            # Transaction type color
            type_color = "green" if t.transaction_type == TransactionType.BUY else "red"
            type_label = f"[{type_color}]{t.transaction_type.value}[/{type_color}]"

            # Total value
            total = t.quantity * t.price
            total_str = f"${total:,.2f}"

            # Fees
            fees_str = f"${t.fees:.2f}" if t.fees > 0 else "[dim]-[/dim]"

            # Realized P&L (only for SELL)
            if t.transaction_type == TransactionType.SELL and t.realized_pnl is not None:
                pnl_color = "green" if t.realized_pnl >= 0 else "red"
                pnl_sign = "+" if t.realized_pnl >= 0 else ""
                pnl_str = f"[{pnl_color}]{pnl_sign}${t.realized_pnl:,.2f}[/{pnl_color}]"
            else:
                pnl_str = "[dim]-[/dim]"

            table.add_row(
                t.transaction_date.strftime("%Y-%m-%d"),
                t.ticker,
                type_label,
                f"{t.quantity:,.4f}".rstrip("0").rstrip("."),
                f"${t.price:.2f}",
                total_str,
                fees_str,
                pnl_str,
            )

        self.console.print(table)

        # Summary
        buy_count = sum(1 for t in filtered if t.transaction_type == TransactionType.BUY)
        sell_count = sum(1 for t in filtered if t.transaction_type == TransactionType.SELL)
        total_realized = sum(
            t.realized_pnl or Decimal("0")
            for t in filtered
            if t.transaction_type == TransactionType.SELL
        )

        self.console.print(
            f"\n[dim]Transactions: {len(filtered)} ({buy_count} buys, {sell_count} sells)"
            f" | Total Realized P&L: "
            f"{'[green]+' if total_realized >= 0 else '[red]'}"
            f"${total_realized:,.2f}[/][/dim]"
        )

    # ========== Performance ==========

    def display_performance(self, performance: PortfolioPerformance) -> None:
        """Display portfolio performance metrics including realized P&L."""
        # Colors for P&L
        unrealized_color = "green" if performance.total_unrealized_pnl >= 0 else "red"
        unrealized_sign = "+" if performance.total_unrealized_pnl >= 0 else ""
        realized_color = "green" if performance.total_realized_pnl >= 0 else "red"
        realized_sign = "+" if performance.total_realized_pnl >= 0 else ""
        total_color = "green" if performance.total_pnl >= 0 else "red"
        total_sign = "+" if performance.total_pnl >= 0 else ""

        # Calculate total return percentage
        if performance.total_cost_basis > 0:
            total_return_pct = (performance.total_pnl / performance.total_cost_basis) * 100
        else:
            total_return_pct = Decimal("0")

        # Build content
        content_lines = [
            f"[bold]{performance.portfolio.name}[/bold]",
            "",
            f"[bold]Current Value:[/bold] ${performance.total_value:,.2f}",
            f"[bold]Cost Basis:[/bold] ${performance.total_cost_basis:,.2f}",
            "",
            f"[bold]Unrealized P&L:[/bold] [{unrealized_color}]{unrealized_sign}${performance.total_unrealized_pnl:,.2f}[/{unrealized_color}]",
            f"[bold]Realized P&L:[/bold] [{realized_color}]{realized_sign}${performance.total_realized_pnl:,.2f}[/{realized_color}]",
            f"[bold]Total P&L:[/bold] [{total_color}]{total_sign}${performance.total_pnl:,.2f} ({total_sign}{total_return_pct:.2f}%)[/{total_color}]",
            "",
        ]

        # Trade statistics
        if performance.winning_trades > 0 or performance.losing_trades > 0:
            total_trades = performance.winning_trades + performance.losing_trades
            win_rate = (performance.winning_trades / total_trades * 100) if total_trades > 0 else 0
            content_lines.extend([
                "[bold]Trade Statistics:[/bold]",
                f"  Winning Trades: [green]{performance.winning_trades}[/green]",
                f"  Losing Trades: [red]{performance.losing_trades}[/red]",
                f"  Win Rate: {win_rate:.1f}%",
            ])

        # Holding period
        if performance.avg_holding_period_days is not None:
            content_lines.append(f"  Avg Holding Period: {performance.avg_holding_period_days} days")

        self.console.print(
            Panel(
                "\n".join(content_lines),
                title="Portfolio Performance",
                border_style="blue",
            )
        )

    # ========== P&L Summary ==========

    def display_pnl_summary(
        self,
        portfolio: Portfolio,
        pnl_by_ticker: dict[str, dict],
        total_realized: Decimal,
        total_fees: Decimal,
    ) -> None:
        """Display realized P&L summary by ticker."""
        # Header
        total_color = "green" if total_realized >= 0 else "red"
        total_sign = "+" if total_realized >= 0 else ""

        self.console.print(
            Panel(
                f"[bold]{portfolio.name}[/bold]\n\n"
                f"Total Realized P&L: [{total_color}]{total_sign}${total_realized:,.2f}[/{total_color}]\n"
                f"Total Fees Paid: [dim]${total_fees:,.2f}[/dim]",
                title="Realized P&L Summary",
                border_style="blue",
            )
        )

        if not pnl_by_ticker:
            self.console.print("[yellow]No realized gains/losses yet.[/yellow]")
            return

        # P&L by ticker table
        table = Table(title="P&L by Ticker")
        table.add_column("Ticker", style="cyan bold")
        table.add_column("Sells", justify="right")
        table.add_column("Avg Cost", justify="right")
        table.add_column("Avg Sell", justify="right")
        table.add_column("Realized P&L", justify="right")
        table.add_column("Holding Days", justify="right")

        for ticker, data in sorted(pnl_by_ticker.items()):
            pnl = data.get("realized_pnl", Decimal("0"))
            pnl_color = "green" if pnl >= 0 else "red"
            pnl_sign = "+" if pnl >= 0 else ""

            table.add_row(
                ticker,
                str(data.get("sell_count", 0)),
                f"${data.get('avg_cost_basis', 0):.2f}",
                f"${data.get('avg_sell_price', 0):.2f}",
                f"[{pnl_color}]{pnl_sign}${pnl:,.2f}[/{pnl_color}]",
                str(data.get("avg_holding_days", "-")),
            )

        self.console.print(table)

    # ========== Updated Import Preview (with transactions) ==========

    def display_transaction_import_preview(
        self,
        mapping: dict,
        rows: list[dict],
    ) -> None:
        """Display CSV import preview for transactions."""
        self.console.print("\n[bold]Column Mapping Detected:[/bold]")
        self.console.print(f"  Ticker: {mapping.get('ticker', 'N/A')}")
        self.console.print(f"  Quantity: {mapping.get('quantity', 'N/A')}")
        self.console.print(f"  Price: {mapping.get('purchase_price', 'N/A')}")
        self.console.print(f"  Date: {mapping.get('purchase_date', 'N/A')}")
        if mapping.get('transaction_type'):
            self.console.print(f"  Type: {mapping['transaction_type']}")
        if mapping.get('fees'):
            self.console.print(f"  Fees: {mapping['fees']}")
        if mapping.get('notes'):
            self.console.print(f"  Notes: {mapping['notes']}")

        self.console.print("\n[bold]Preview (first 5 rows):[/bold]")

        table = Table()
        table.add_column("Ticker", style="cyan")
        table.add_column("Type", justify="center")
        table.add_column("Quantity", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("Date", justify="center")
        if any(row.get("fees") for row in rows):
            table.add_column("Fees", justify="right")

        for row in rows:
            # Transaction type with color
            tx_type = row.get("transaction_type", "BUY")
            if hasattr(tx_type, "value"):
                tx_type = tx_type.value
            type_color = "green" if tx_type == "BUY" else "red"

            row_data = [
                row.get("ticker", "-"),
                f"[{type_color}]{tx_type}[/{type_color}]",
                f"{row.get('quantity', 0):,.4f}".rstrip("0").rstrip("."),
                f"${row.get('price', 0):.2f}",
                str(row.get("date", "-")),
            ]

            if any(r.get("fees") for r in rows):
                fees = row.get("fees", Decimal("0"))
                row_data.append(f"${fees:.2f}" if fees > 0 else "-")

            table.add_row(*row_data)

        self.console.print(table)

    def display_transaction_import_result(self, result: CSVImportResult) -> None:
        """Display transaction import result."""
        success_color = "green" if result.records_failed == 0 else "yellow"

        # Count buys and sells if available
        buy_count = 0
        sell_count = 0
        if result.transactions_created:
            buy_count = sum(
                1 for t in result.transactions_created
                if t.transaction_type == TransactionType.BUY
            )
            sell_count = sum(
                1 for t in result.transactions_created
                if t.transaction_type == TransactionType.SELL
            )

        content = (
            f"[bold]Import Complete[/bold]\n\n"
            f"File: {result.file_name}\n"
            f"Total Records: {result.records_total}\n"
            f"Successful: [{success_color}]{result.records_success}[/{success_color}]"
        )

        if buy_count or sell_count:
            content += f" ([green]{buy_count} buys[/green], [red]{sell_count} sells[/red])"

        content += (
            f"\nFailed: {'[red]' + str(result.records_failed) + '[/red]' if result.records_failed else '0'}\n"
            f"Success Rate: {result.success_rate:.1f}%"
        )

        self.console.print(
            Panel(
                content,
                title="Transaction Import Result",
                border_style="green" if result.records_failed == 0 else "yellow",
            )
        )

        # Show errors if any
        if result.errors:
            self.console.print("\n[red]Import Errors:[/red]")
            table = Table()
            table.add_column("Row", style="dim", width=6)
            table.add_column("Field", style="yellow")
            table.add_column("Value", style="dim")
            table.add_column("Error", style="red")

            for err in result.errors[:10]:
                table.add_row(
                    str(err.row_number),
                    err.field,
                    err.value[:20] + "..." if len(err.value) > 20 else err.value,
                    err.error,
                )

            self.console.print(table)

            if len(result.errors) > 10:
                self.console.print(f"[dim]...and {len(result.errors) - 10} more errors[/dim]")
