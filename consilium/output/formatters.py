"""Rich console formatters for displaying analysis results."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns

from consilium.core.enums import SignalType, ConfidenceLevel
from consilium.core.models import ConsensusResult, AnalysisResult, AgentResponse


class ResultFormatter:
    """Formats analysis results for Rich console output."""

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

    def display_results(
        self,
        result: AnalysisResult,
        verbose: bool = False,
    ) -> None:
        """Display complete analysis results."""
        # Header
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Consilium Analysis Complete[/bold]\n"
                f"Tickers: {', '.join(result.tickers)}\n"
                f"Agents: {result.agents_used} | Time: {result.execution_time_seconds:.1f}s",
                title="Summary",
                border_style="blue",
            )
        )

        # Results for each ticker
        for consensus in result.results:
            self.display_consensus(consensus, verbose=verbose)

    def display_consensus(
        self,
        result: ConsensusResult,
        verbose: bool = False,
    ) -> None:
        """Display consensus result for a single ticker."""
        self.console.print()

        # Signal panel
        signal_color = self.SIGNAL_COLORS.get(result.final_signal, "white")
        confidence_color = self.CONFIDENCE_COLORS.get(result.confidence, "white")

        signal_text = Text()
        signal_text.append(f"{result.final_signal.value}", style=signal_color)

        self.console.print(
            Panel(
                f"[bold]{result.ticker}[/bold]\n\n"
                f"Signal: [{signal_color}]{result.final_signal.value}[/{signal_color}]\n"
                f"Confidence: [{confidence_color}]{result.confidence.value}[/{confidence_color}]\n"
                f"Score: {result.weighted_score:.1f}\n\n"
                f"Votes: {result.buy_votes} Buy | {result.hold_votes} Hold | {result.sell_votes} Sell\n"
                f"Agreement: {result.agreement_ratio:.0%}",
                title=f"Consensus: {result.ticker}",
                border_style=signal_color.replace("bold ", ""),
            )
        )

        # Key themes and risks
        if result.key_themes or result.primary_risks:
            cols = []
            if result.key_themes:
                themes = "\n".join(f"  - {t}" for t in result.key_themes[:3])
                cols.append(Panel(f"[green]Key Themes[/green]\n{themes}", expand=True))
            if result.primary_risks:
                risks = "\n".join(f"  - {r}" for r in result.primary_risks[:3])
                cols.append(Panel(f"[red]Risks[/red]\n{risks}", expand=True))
            if cols:
                self.console.print(Columns(cols))

        # Dissenters
        if result.dissenters:
            self.console.print(
                f"[yellow]Dissenters:[/yellow] {', '.join(result.dissenters)}"
            )

        # Verbose: show all agent responses
        if verbose:
            self._display_agent_table(result)

    def _display_agent_table(self, result: ConsensusResult) -> None:
        """Display table of all agent responses."""
        self.console.print()

        table = Table(title=f"Agent Responses for {result.ticker}")
        table.add_column("Agent", style="cyan", no_wrap=True)
        table.add_column("Signal", justify="center")
        table.add_column("Confidence", justify="center")
        table.add_column("Target", justify="right")
        table.add_column("Reasoning", max_width=50)

        for response in result.agent_responses:
            signal_color = self.SIGNAL_COLORS.get(response.signal, "white")
            conf_color = self.CONFIDENCE_COLORS.get(response.confidence, "white")

            target = f"${response.target_price:.2f}" if response.target_price else "-"
            reasoning = response.reasoning[:100] + "..." if len(response.reasoning) > 100 else response.reasoning

            table.add_row(
                response.agent_name,
                f"[{signal_color}]{response.signal.value}[/{signal_color}]",
                f"[{conf_color}]{response.confidence.value}[/{conf_color}]",
                target,
                reasoning,
            )

        self.console.print(table)

    def display_single_response(self, response: AgentResponse) -> None:
        """Display a single agent response in detail."""
        signal_color = self.SIGNAL_COLORS.get(response.signal, "white")

        self.console.print(
            Panel(
                f"[bold]{response.agent_name}[/bold] on {response.ticker}\n\n"
                f"Signal: [{signal_color}]{response.signal.value}[/{signal_color}]\n"
                f"Confidence: {response.confidence.value}\n"
                f"Target: ${response.target_price:.2f}" if response.target_price else "Target: N/A\n"
                f"Horizon: {response.time_horizon or 'N/A'}\n\n"
                f"[bold]Reasoning:[/bold]\n{response.reasoning}\n\n"
                f"[bold]Key Factors:[/bold]\n" +
                "\n".join(f"  - {f}" for f in response.key_factors) + "\n\n"
                f"[bold]Risks:[/bold]\n" +
                "\n".join(f"  - {r}" for r in response.risks),
                border_style=signal_color.replace("bold ", ""),
            )
        )


def format_signal(signal: SignalType) -> str:
    """Format signal with color for Rich."""
    colors = {
        SignalType.STRONG_BUY: "[bold green]STRONG BUY[/bold green]",
        SignalType.BUY: "[green]BUY[/green]",
        SignalType.HOLD: "[yellow]HOLD[/yellow]",
        SignalType.SELL: "[red]SELL[/red]",
        SignalType.STRONG_SELL: "[bold red]STRONG SELL[/bold red]",
    }
    return colors.get(signal, str(signal.value))


def format_confidence(confidence: ConfidenceLevel) -> str:
    """Format confidence with color for Rich."""
    colors = {
        ConfidenceLevel.VERY_HIGH: "[bold green]VERY HIGH[/bold green]",
        ConfidenceLevel.HIGH: "[green]HIGH[/green]",
        ConfidenceLevel.MEDIUM: "[yellow]MEDIUM[/yellow]",
        ConfidenceLevel.LOW: "[red]LOW[/red]",
        ConfidenceLevel.VERY_LOW: "[bold red]VERY LOW[/bold red]",
    }
    return colors.get(confidence, str(confidence.value))
