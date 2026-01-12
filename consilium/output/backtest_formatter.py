"""Rich formatters for backtest output."""

from decimal import Decimal

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from consilium.backtesting.models import (
    BacktestResult,
    BacktestTrade,
    TradeAction,
)


class BacktestFormatter:
    """Formats backtest output for display."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def display_result(
        self,
        result: BacktestResult,
        show_trades: bool = True,
        max_trades: int = 20,
    ) -> None:
        """
        Display complete backtest results.

        Args:
            result: BacktestResult to display
            show_trades: Whether to show trade history
            max_trades: Maximum number of trades to display
        """
        # Main results panel
        self._display_summary_panel(result)

        # Metrics sections
        self._display_returns_section(result)
        self._display_risk_section(result)
        self._display_trade_stats_section(result)

        # Trade history table
        if show_trades and result.trades:
            self._display_trade_history(result.trades, max_trades)

    def display_history(
        self,
        backtests: list[dict],
        title: str = "Backtest History",
    ) -> None:
        """Display list of previous backtests."""
        if not backtests:
            self.console.print("[yellow]No backtests found.[/yellow]")
            return

        table = Table(title=title, box=box.ROUNDED)
        table.add_column("ID", style="dim", width=6)
        table.add_column("Date", width=12)
        table.add_column("Ticker", width=8)
        table.add_column("Period", width=22)
        table.add_column("Strategy", width=10)
        table.add_column("Return", justify="right", width=10)
        table.add_column("Sharpe", justify="right", width=8)
        table.add_column("Max DD", justify="right", width=8)

        for bt in backtests:
            # Format return with color
            total_return = bt.get("total_return", Decimal("0"))
            return_color = "green" if total_return >= 0 else "red"
            return_str = f"[{return_color}]{total_return:+.1f}%[/{return_color}]"

            # Format period
            start = bt.get("start_date")
            end = bt.get("end_date")
            period_str = f"{start} - {end}" if start and end else "-"

            # Format max drawdown
            max_dd = bt.get("max_drawdown", Decimal("0"))
            dd_str = f"[red]-{max_dd:.1f}%[/red]" if max_dd > 0 else "0%"

            date_str = bt["created_at"].strftime("%Y-%m-%d") if bt.get("created_at") else "-"

            table.add_row(
                str(bt["id"]),
                date_str,
                bt.get("ticker", "-"),
                period_str,
                bt.get("strategy_type", "-"),
                return_str,
                f"{bt.get('sharpe_ratio', Decimal('0')):.2f}",
                dd_str,
            )

        self.console.print(table)

    def _display_summary_panel(self, result: BacktestResult) -> None:
        """Display main summary panel."""
        m = result.metrics

        # Format return with color
        return_color = "green" if m.total_return_pct >= 0 else "red"
        return_str = f"[{return_color}]{m.total_return_pct:+.2f}%[/{return_color}]"

        # Format alpha with color
        alpha_color = "green" if m.alpha >= 0 else "red"
        alpha_str = f"[{alpha_color}]{m.alpha:+.2f}%[/{alpha_color}]"

        # Build summary content
        summary_lines = [
            f"[bold]Ticker:[/bold] {result.ticker}",
            f"[bold]Period:[/bold] {result.start_date} to {result.end_date} ({result.duration_days} days)",
            f"[bold]Strategy:[/bold] {result.strategy_type.value.capitalize()}",
            f"[bold]Benchmark:[/bold] {result.benchmark}",
            f"[bold]Initial Capital:[/bold] ${result.initial_capital:,.2f}",
            "",
            f"[bold]Final Value:[/bold] ${result.final_value:,.2f}",
            f"[bold]Total Return:[/bold] {return_str} (${m.total_return:+,.2f})",
            f"[bold]Alpha vs {result.benchmark}:[/bold] {alpha_str}",
        ]

        if result.threshold_value:
            summary_lines.insert(3, f"[bold]Threshold:[/bold] {result.threshold_value}")

        if result.agent_filter:
            agents_str = ", ".join(result.agent_filter)
            summary_lines.insert(4, f"[bold]Agents:[/bold] {agents_str}")

        self.console.print()
        self.console.print(Panel(
            "\n".join(summary_lines),
            title="Backtest Results",
            border_style="blue",
            box=box.ROUNDED,
        ))

    def _display_returns_section(self, result: BacktestResult) -> None:
        """Display returns metrics."""
        m = result.metrics

        table = Table(
            title="Returns",
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
        )
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        # Color formatting
        cagr_color = "green" if m.cagr >= 0 else "red"
        benchmark_color = "green" if m.benchmark_return >= 0 else "red"
        excess_color = "green" if m.excess_return >= 0 else "red"

        table.add_row("CAGR", f"[{cagr_color}]{m.cagr:+.2f}%[/{cagr_color}]")
        table.add_row("Benchmark Return", f"[{benchmark_color}]{m.benchmark_return:+.2f}%[/{benchmark_color}]")
        table.add_row("Excess Return", f"[{excess_color}]{m.excess_return:+.2f}%[/{excess_color}]")

        self.console.print(table)

    def _display_risk_section(self, result: BacktestResult) -> None:
        """Display risk metrics."""
        m = result.metrics

        table = Table(
            title="Risk Metrics",
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
        )
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        # Sharpe color (>1 is good, >2 is great)
        sharpe_color = "green" if m.sharpe_ratio > 1 else ("yellow" if m.sharpe_ratio > 0 else "red")
        sortino_color = "green" if m.sortino_ratio > 1 else ("yellow" if m.sortino_ratio > 0 else "red")

        table.add_row("Sharpe Ratio", f"[{sharpe_color}]{m.sharpe_ratio:.2f}[/{sharpe_color}]")
        table.add_row("Sortino Ratio", f"[{sortino_color}]{m.sortino_ratio:.2f}[/{sortino_color}]")
        table.add_row("Calmar Ratio", f"{m.calmar_ratio:.2f}")
        table.add_row("Max Drawdown", f"[red]-{m.max_drawdown:.2f}%[/red]")
        table.add_row("Max DD Duration", f"{m.max_drawdown_duration_days} days")
        table.add_row("VaR (95%)", f"[red]-{m.var_95:.2f}%[/red]")
        table.add_row("Beta", f"{m.beta:.2f}")

        self.console.print(table)

    def _display_trade_stats_section(self, result: BacktestResult) -> None:
        """Display trade statistics."""
        m = result.metrics

        table = Table(
            title="Trade Statistics",
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
        )
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        # Win rate color
        win_color = "green" if m.win_rate >= 50 else "red"

        table.add_row("Total Trades", str(m.total_trades))
        table.add_row("Winning Trades", f"[green]{m.winning_trades}[/green]")
        table.add_row("Losing Trades", f"[red]{m.losing_trades}[/red]")
        table.add_row("Win Rate", f"[{win_color}]{m.win_rate:.1f}%[/{win_color}]")
        table.add_row("Profit Factor", f"{m.profit_factor:.2f}")
        table.add_row("Avg Holding Period", f"{m.avg_holding_days} days")

        if m.avg_win > 0:
            table.add_row("Avg Win", f"[green]+${m.avg_win:,.2f}[/green]")
        if m.avg_loss > 0:
            table.add_row("Avg Loss", f"[red]-${m.avg_loss:,.2f}[/red]")

        self.console.print(table)

    def _display_trade_history(
        self,
        trades: list[BacktestTrade],
        max_trades: int = 20,
    ) -> None:
        """Display trade history table."""
        table = Table(
            title="Trade History",
            box=box.ROUNDED,
        )
        table.add_column("Date", width=12)
        table.add_column("Side", width=6)
        table.add_column("Price", justify="right", width=12)
        table.add_column("Qty", justify="right", width=12)
        table.add_column("Total", justify="right", width=14)
        table.add_column("P&L", justify="right", width=14)
        table.add_column("Signal", width=12)

        # Show first and last trades if too many
        display_trades = trades
        truncated = False
        if len(trades) > max_trades:
            half = max_trades // 2
            display_trades = trades[:half] + trades[-half:]
            truncated = True

        for i, trade in enumerate(display_trades):
            # Add separator if truncated
            if truncated and i == max_trades // 2:
                table.add_row(
                    "[dim]...[/dim]",
                    "[dim]...[/dim]",
                    "[dim]...[/dim]",
                    "[dim]...[/dim]",
                    "[dim]...[/dim]",
                    "[dim]...[/dim]",
                    "[dim]...[/dim]",
                )

            # Format side with color
            if trade.trade_type == TradeAction.BUY:
                side_str = "[green]BUY[/green]"
            else:
                side_str = "[red]SELL[/red]"

            # Format P&L
            pnl_str = "-"
            if trade.realized_pnl is not None:
                pnl_color = "green" if trade.realized_pnl >= 0 else "red"
                pnl_str = f"[{pnl_color}]{trade.realized_pnl:+,.2f}[/{pnl_color}]"

            # Format signal
            signal_str = "-"
            if trade.signal:
                signal_str = trade.signal.value

            table.add_row(
                str(trade.trade_date),
                side_str,
                f"${trade.price:,.2f}",
                f"{trade.quantity:,.4f}",
                f"${trade.total_value:,.2f}",
                pnl_str,
                signal_str,
            )

        self.console.print()
        self.console.print(table)

        if truncated:
            self.console.print(
                f"[dim]Showing {max_trades} of {len(trades)} trades. "
                f"Use --all-trades to see all.[/dim]"
            )

    def display_compact(self, result: BacktestResult) -> None:
        """Display a compact one-line summary."""
        m = result.metrics
        return_color = "green" if m.total_return_pct >= 0 else "red"

        self.console.print(
            f"[bold]{result.ticker}[/bold] | "
            f"[{return_color}]{m.total_return_pct:+.1f}%[/{return_color}] | "
            f"Sharpe: {m.sharpe_ratio:.2f} | "
            f"Max DD: [red]-{m.max_drawdown:.1f}%[/red] | "
            f"Trades: {m.total_trades} ({m.win_rate:.0f}% win)"
        )
