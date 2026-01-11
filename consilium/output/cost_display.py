"""Cost estimation display using Rich."""

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from consilium.llm.cost_estimator import CostEstimate, CostEstimator


class CostDisplay:
    """Displays cost estimates to user."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def display(self, estimate: CostEstimate) -> None:
        """Display cost estimate with breakdown table."""
        # Build breakdown table
        table = Table(show_header=True, header_style="bold", box=None)
        table.add_column("Component", style="cyan")
        table.add_column("Calls", justify="right")
        table.add_column("Input Tokens", justify="right")
        table.add_column("Output Tokens", justify="right")
        table.add_column("Cost", justify="right", style="green")

        for b in estimate.breakdowns:
            table.add_row(
                b.component,
                str(b.api_calls),
                f"~{b.input_tokens:,}",
                f"~{b.output_tokens:,}",
                f"${b.cost_usd:.2f}",
            )

        # Add totals row
        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{estimate.total_api_calls}[/bold]",
            f"[bold]~{estimate.total_input_tokens:,}[/bold]",
            f"[bold]~{estimate.total_output_tokens:,}[/bold]",
            f"[bold green]${estimate.total_cost_usd:.2f}[/bold green]",
        )

        # Get model display name
        model_name = CostEstimator.get_model_name(estimate.model)

        # Build content
        content = Group(
            Text(f"Model: {model_name}", style="bold"),
            Text(f"Model ID: {estimate.model}", style="dim"),
            Text(""),
            table,
            Text(""),
            Text(f"Estimated Cost: ${estimate.total_cost_usd:.2f} USD", style="bold yellow"),
        )

        self.console.print()
        self.console.print(Panel(content, title="Cost Estimation", border_style="blue"))

    def display_compact(self, estimate: CostEstimate) -> None:
        """Display a compact one-line cost estimate."""
        model_name = CostEstimator.get_model_name(estimate.model)
        self.console.print(
            f"[dim]Estimated cost:[/dim] [bold yellow]${estimate.total_cost_usd:.2f}[/bold yellow] "
            f"[dim]({estimate.total_api_calls} API calls, {model_name})[/dim]"
        )
