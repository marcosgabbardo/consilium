"""Comparison formatter for side-by-side asset analysis."""

from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from consilium.core.enums import SignalType, ConfidenceLevel
from consilium.core.models import AnalysisResult, ConsensusResult


class ComparisonFormatter:
    """Formats comparison output for multiple assets."""

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

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def display_comparison(
        self,
        result: AnalysisResult,
        sort_by: str = "score",
        show_matrix: bool = False,
        show_themes: bool = False,
        verbose: bool = False,
    ) -> None:
        """Display full comparison output."""
        self.console.print()

        # Header
        self._display_header(result)

        # Ranking table (always shown)
        self.display_ranking_table(result.results, sort_by)

        # Winner announcement
        if result.results:
            self._display_winner(result.results, sort_by)

        # Optional: Agent matrix
        if show_matrix or verbose:
            self.display_agent_matrix(result.results)

        # Optional: Themes comparison
        if show_themes or verbose:
            self.display_themes_comparison(result.results)
            self.display_risks_comparison(result.results)

    def display_ranking_table(
        self,
        results: list[ConsensusResult],
        sort_by: str = "score",
    ) -> None:
        """Display ranking table sorted by metric."""
        if not results:
            self.console.print("[yellow]No results to compare.[/yellow]")
            return

        # Sort results
        sorted_results = self._sort_results(results, sort_by)

        table = Table(title=f"Asset Comparison (sorted by {sort_by})")
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Ticker", style="cyan bold", width=8)
        table.add_column("Signal", justify="center", width=12)
        table.add_column("Score", justify="right", width=8)
        table.add_column("Confidence", justify="center", width=12)
        table.add_column("Agreement", justify="right", width=10)
        table.add_column("Votes", width=14)

        for idx, r in enumerate(sorted_results, 1):
            signal_color = self.SIGNAL_COLORS.get(r.final_signal, "white")
            conf_color = self.CONFIDENCE_COLORS.get(r.confidence, "white")

            table.add_row(
                str(idx),
                r.ticker,
                f"[{signal_color}]{r.final_signal.value}[/{signal_color}]",
                f"{r.weighted_score:.1f}",
                f"[{conf_color}]{r.confidence.value}[/{conf_color}]",
                f"{r.agreement_ratio:.0%}",
                f"{r.buy_votes}B {r.hold_votes}H {r.sell_votes}S",
            )

        self.console.print(table)

    def display_agent_matrix(self, results: list[ConsensusResult]) -> None:
        """Display agent consensus matrix across assets."""
        if not results:
            return

        # Collect all agents
        all_agents: set[str] = set()
        for r in results:
            for resp in r.agent_responses:
                all_agents.add(resp.agent_name)

        if not all_agents:
            return

        sorted_agents = sorted(list(all_agents))

        self.console.print()
        table = Table(title="Agent Consensus Matrix")
        table.add_column("Agent", style="cyan", no_wrap=True, width=20)

        # Sort results by score for column order
        sorted_results = self._sort_results(results, "score")

        for r in sorted_results:
            table.add_column(r.ticker, justify="center", width=8)

        # Build signal map
        signal_map: dict[str, dict[str, SignalType]] = defaultdict(dict)
        for r in results:
            for resp in r.agent_responses:
                signal_map[resp.agent_name][r.ticker] = resp.signal

        for agent in sorted_agents:
            row = [agent]
            for r in sorted_results:
                signal = signal_map.get(agent, {}).get(r.ticker)
                if signal:
                    color = self.SIGNAL_COLORS.get(signal, "white")
                    abbrev = self._abbreviate_signal(signal)
                    row.append(f"[{color}]{abbrev}[/{color}]")
                else:
                    row.append("[dim]-[/dim]")
            table.add_row(*row)

        self.console.print(table)

    def display_themes_comparison(self, results: list[ConsensusResult]) -> None:
        """Display common themes across assets."""
        if not results:
            return

        # Collect all themes
        all_themes: set[str] = set()
        theme_map: dict[str, set[str]] = {}
        for r in results:
            theme_map[r.ticker] = set(r.key_themes)
            all_themes.update(r.key_themes)

        if not all_themes:
            return

        self.console.print()
        table = Table(title="Key Themes Comparison")
        table.add_column("Theme", style="white", width=30)

        sorted_results = self._sort_results(results, "score")
        for r in sorted_results:
            table.add_column(r.ticker, justify="center", width=8)

        for theme in sorted(all_themes):
            row = [theme]
            for r in sorted_results:
                if theme in theme_map.get(r.ticker, set()):
                    row.append("[green]✓[/green]")
                else:
                    row.append("[dim]-[/dim]")
            table.add_row(*row)

        self.console.print(table)

    def display_risks_comparison(self, results: list[ConsensusResult]) -> None:
        """Display common risks across assets."""
        if not results:
            return

        # Collect all risks
        all_risks: set[str] = set()
        risk_map: dict[str, set[str]] = {}
        for r in results:
            risk_map[r.ticker] = set(r.primary_risks)
            all_risks.update(r.primary_risks)

        if not all_risks:
            return

        self.console.print()
        table = Table(title="Risk Factors Comparison")
        table.add_column("Risk", style="white", width=30)

        sorted_results = self._sort_results(results, "score")
        for r in sorted_results:
            table.add_column(r.ticker, justify="center", width=8)

        for risk in sorted(all_risks):
            row = [risk]
            for r in sorted_results:
                if risk in risk_map.get(r.ticker, set()):
                    row.append("[red]✓[/red]")
                else:
                    row.append("[dim]-[/dim]")
            table.add_row(*row)

        self.console.print(table)

    def _sort_results(
        self,
        results: list[ConsensusResult],
        sort_by: str,
    ) -> list[ConsensusResult]:
        """Sort results by specified metric."""
        if sort_by == "score":
            return sorted(results, key=lambda r: r.weighted_score, reverse=True)
        elif sort_by == "agreement":
            return sorted(results, key=lambda r: r.agreement_ratio, reverse=True)
        elif sort_by == "bullish":
            return sorted(results, key=lambda r: r.buy_votes, reverse=True)
        elif sort_by == "confidence":
            return sorted(
                results, key=lambda r: r.confidence.multiplier, reverse=True
            )
        return results

    def _display_winner(
        self,
        results: list[ConsensusResult],
        sort_by: str,
    ) -> None:
        """Display the winning asset."""
        sorted_results = self._sort_results(results, sort_by)
        winner = sorted_results[0]
        signal_color = self.SIGNAL_COLORS.get(winner.final_signal, "white")

        self.console.print(
            f"\n[bold]Winner:[/bold] [{signal_color}]{winner.ticker}[/{signal_color}] "
            f"with {winner.final_signal.value} signal and {winner.agreement_ratio:.0%} agreement\n"
        )

    def _display_header(self, result: AnalysisResult) -> None:
        """Display comparison header."""
        self.console.print(
            Panel(
                f"[bold]Comparison Analysis[/bold]\n"
                f"Tickers: {', '.join(result.tickers)}\n"
                f"Agents: {result.agents_used} | Time: {result.execution_time_seconds:.1f}s",
                title="Consilium Compare",
                border_style="blue",
            )
        )

    def _abbreviate_signal(self, signal: SignalType) -> str:
        """Abbreviate signal for matrix display."""
        abbrevs = {
            SignalType.STRONG_BUY: "S_BUY",
            SignalType.BUY: "BUY",
            SignalType.HOLD: "HOLD",
            SignalType.SELL: "SELL",
            SignalType.STRONG_SELL: "S_SELL",
        }
        return abbrevs.get(signal, signal.value)
