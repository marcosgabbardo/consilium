"""Rich formatters for Q&A output."""

from decimal import Decimal

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from consilium.ask.models import AskResult, AskResponse
from consilium.core.enums import SignalType, ConfidenceLevel


class AskFormatter:
    """Formats Q&A output for display."""

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

    def display_single_response(self, result: AskResult) -> None:
        """Display a single investor response in detail."""
        if not result.responses:
            self.console.print("[yellow]No responses received.[/yellow]")
            return

        response = result.responses[0]
        self._display_response_panel(result, response)
        self._display_cost_footer(result)

    def display_comparison(self, result: AskResult) -> None:
        """Display comparison of multiple investor responses."""
        if not result.responses:
            self.console.print("[yellow]No responses received.[/yellow]")
            return

        # Header with question info
        self._display_header(result)

        # Summary table
        self._display_summary_table(result)

        # Consensus
        self._display_consensus(result)

        # Individual responses
        self.console.print()
        for response in result.responses:
            self._display_response_section(response)

        self._display_cost_footer(result)

    def display_history(
        self,
        questions: list[dict],
        title: str = "Q&A History",
    ) -> None:
        """Display list of previous questions."""
        if not questions:
            self.console.print("[yellow]No questions found.[/yellow]")
            return

        table = Table(title=title)
        table.add_column("ID", style="dim", width=6)
        table.add_column("Date", width=12)
        table.add_column("Question", width=50)
        table.add_column("Tickers", width=15)
        table.add_column("Agents", width=10, justify="center")
        table.add_column("Cost", justify="right", width=8)

        for q in questions:
            question_text = q["question"]
            if len(question_text) > 47:
                question_text = question_text[:47] + "..."

            tickers = ", ".join(q.get("tickers", [])) or "-"
            if len(tickers) > 12:
                tickers = tickers[:12] + "..."

            agents_count = len(q.get("agents", []))
            date_str = q["created_at"].strftime("%Y-%m-%d") if q.get("created_at") else "-"
            cost = f"${q.get('cost_usd', Decimal('0')):.2f}"

            table.add_row(
                str(q["id"]),
                date_str,
                question_text,
                tickers,
                str(agents_count),
                cost,
            )

        self.console.print(table)

    def display_question_detail(self, result: AskResult) -> None:
        """Display detailed view of a single question with all responses."""
        # Header
        self._display_header(result)

        if len(result.responses) == 1:
            self._display_response_panel(result, result.responses[0])
        else:
            # Summary table
            self._display_summary_table(result)
            self._display_consensus(result)

            # Individual responses
            self.console.print()
            for response in result.responses:
                self._display_response_section(response)

        self._display_cost_footer(result)

    def _display_header(self, result: AskResult) -> None:
        """Display header with question info."""
        tickers_str = ", ".join(result.tickers) if result.tickers else "None detected"

        header_text = (
            f"[bold]Question:[/bold] \"{result.question}\"\n"
            f"[bold]Tickers:[/bold] {tickers_str}"
        )

        if result.include_market_data and result.tickers:
            header_text += " (with market data)"

        self.console.print(Panel(
            header_text,
            title="Investor Q&A",
            border_style="blue",
        ))

    def _display_response_panel(self, result: AskResult, response: AskResponse) -> None:
        """Display a response in a detailed panel."""
        signal_color = self.SIGNAL_COLORS.get(response.signal, "white")
        conf_color = self.CONFIDENCE_COLORS.get(response.confidence, "white")

        # Build content
        lines = []

        # Question
        lines.append(f"[bold]Question:[/bold] \"{result.question}\"")

        # Tickers
        if result.tickers:
            lines.append(f"[bold]Tickers:[/bold] {', '.join(result.tickers)}")

        lines.append("")

        # Signal info
        signal_line = (
            f"[bold]Signal:[/bold] [{signal_color}]{response.signal.value}[/{signal_color}]"
            f"          "
            f"[bold]Confidence:[/bold] [{conf_color}]{response.confidence.value}[/{conf_color}]"
            f"          "
            f"[bold]Score:[/bold] {response.weighted_score:.1f}"
        )
        lines.append(signal_line)

        lines.append("")
        lines.append("[dim]" + "─" * 60 + "[/dim]")
        lines.append("")

        # Reasoning
        lines.append(response.reasoning)

        # Key factors
        if response.key_factors:
            lines.append("")
            lines.append("[bold]Key Factors:[/bold]")
            for factor in response.key_factors:
                lines.append(f"  [green]•[/green] {factor}")

        # Risks
        if response.risks:
            lines.append("")
            lines.append("[bold]Risks:[/bold]")
            for risk in response.risks:
                lines.append(f"  [red]•[/red] {risk}")

        # Time horizon
        if response.time_horizon:
            lines.append("")
            lines.append(f"[bold]Time Horizon:[/bold] {response.time_horizon}")

        # Target price
        if response.target_price:
            lines.append(f"[bold]Target Price:[/bold] ${response.target_price:.2f}")

        content = "\n".join(lines)

        self.console.print(Panel(
            content,
            title=f"{response.agent_name}'s Response",
            border_style="cyan",
        ))

    def _display_summary_table(self, result: AskResult) -> None:
        """Display summary table of all responses."""
        table = Table(title="Response Summary")
        table.add_column("Investor", style="cyan", no_wrap=True)
        table.add_column("Signal", justify="center")
        table.add_column("Confidence", justify="center")
        table.add_column("Score", justify="right")

        for response in result.responses:
            signal_color = self.SIGNAL_COLORS.get(response.signal, "white")
            conf_color = self.CONFIDENCE_COLORS.get(response.confidence, "white")

            table.add_row(
                response.agent_name,
                f"[{signal_color}]{response.signal.value}[/{signal_color}]",
                f"[{conf_color}]{response.confidence.value}[/{conf_color}]",
                f"{response.weighted_score:+.1f}",
            )

        self.console.print(table)

    def _display_consensus(self, result: AskResult) -> None:
        """Display consensus information."""
        consensus = result.consensus_signal
        if consensus:
            signal_color = self.SIGNAL_COLORS.get(consensus, "white")
            self.console.print(
                f"\n[bold]Consensus:[/bold] [{signal_color}]{consensus.value}[/{signal_color}] "
                f"({result.bullish_count} bullish, {result.neutral_count} neutral, "
                f"{result.bearish_count} bearish)"
            )

    def _display_response_section(self, response: AskResponse) -> None:
        """Display a response as a section (for multi-response view)."""
        signal_color = self.SIGNAL_COLORS.get(response.signal, "white")

        # Header line
        header = Text()
        header.append("─" * 20 + " ", style="dim")
        header.append(response.agent_name, style="bold cyan")
        header.append(" ", style="dim")
        header.append(f"[{response.signal.value}]", style=signal_color)
        header.append(" " + "─" * 20, style="dim")

        self.console.print(header)
        self.console.print()

        # Reasoning (wrapped)
        self.console.print(response.reasoning)

        # Key factors (condensed)
        if response.key_factors:
            factors_str = " | ".join(response.key_factors[:3])
            self.console.print(f"\n[bold]Key:[/bold] {factors_str}")

        # Risks (condensed)
        if response.risks:
            risks_str = " | ".join(response.risks[:2])
            self.console.print(f"[bold]Risks:[/bold] {risks_str}")

        self.console.print()

    def _display_cost_footer(self, result: AskResult) -> None:
        """Display cost information footer."""
        self.console.print(
            f"\n[dim]Cost: ${result.total_cost_usd:.2f} | "
            f"Tokens: {result.total_input_tokens:,} in / {result.total_output_tokens:,} out | "
            f"Time: {result.execution_time_seconds:.1f}s[/dim]"
        )
