"""Consilium CLI application using Typer and Rich."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from consilium import __version__
from consilium.config import get_settings

# Initialize CLI app and console
app = typer.Typer(
    name="consilium",
    help="Multi-agent hedge fund CLI - AI-powered investment analysis",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

# Sub-applications
agents_app = typer.Typer(help="Agent management commands")
watchlist_app = typer.Typer(help="Watchlist management commands")
universe_app = typer.Typer(help="Stock universe management commands")
portfolio_app = typer.Typer(help="Portfolio management commands")
history_app = typer.Typer(help="Analysis history commands")
db_app = typer.Typer(help="Database management commands")
app.add_typer(agents_app, name="agents")
app.add_typer(watchlist_app, name="watchlist")
app.add_typer(universe_app, name="universe")
app.add_typer(portfolio_app, name="portfolio")
app.add_typer(history_app, name="history")
app.add_typer(db_app, name="db")


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"[bold cyan]Consilium[/bold cyan] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Consilium - Multi-agent hedge fund CLI for AI-powered investment analysis."""
    pass


@app.command()
def analyze(
    tickers: str = typer.Argument(
        ...,
        help="Comma-separated ticker symbols (e.g., 'AAPL,NVDA,MSFT')",
    ),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        "-a",
        help="Specific agents to use (comma-separated IDs)",
    ),
    skip_specialists: bool = typer.Option(
        False,
        "--skip-specialists",
        "-s",
        help="Skip specialist analysis phase",
    ),
    export: Optional[str] = typer.Option(
        None,
        "--export",
        "-e",
        help="Export format: json, csv, or md",
    ),
    output_file: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path for export",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed agent reasoning",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip cost confirmation (use with caution)",
    ),
) -> None:
    """
    Analyze stocks using the multi-agent consensus system.

    Examples:
        consilium analyze AAPL
        consilium analyze "AAPL,NVDA,MSFT" --verbose
        consilium analyze TSLA --agents buffett,munger,graham
        consilium analyze AMZN --export json -o analysis.json
        consilium analyze AAPL --yes  # Skip cost confirmation
    """
    settings = get_settings()

    if not settings.is_configured:
        console.print(
            "[red]Error:[/red] ANTHROPIC_API_KEY not configured. "
            "Please set it in your .env file or environment."
        )
        raise typer.Exit(1)

    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    agent_filter = [a.strip().lower() for a in agents.split(",")] if agents else None

    if not ticker_list:
        console.print("[red]Error:[/red] No valid tickers provided.")
        raise typer.Exit(1)

    from rich.progress import Progress, SpinnerColumn, TextColumn
    from consilium.analysis.orchestrator import AnalysisOrchestrator
    from consilium.output.formatters import ResultFormatter
    from consilium.output.exporters import export_result
    from consilium.llm.cost_estimator import CostEstimator
    from consilium.output.cost_display import CostDisplay

    # Calculate number of agents
    num_investors = len(agent_filter) if agent_filter else 13
    num_specialists = 0 if skip_specialists else 7

    # Show cost estimate and ask for confirmation
    estimator = CostEstimator(settings.model)
    estimate = estimator.estimate(
        num_tickers=len(ticker_list),
        num_investors=num_investors,
        num_specialists=num_specialists,
        include_specialists=not skip_specialists,
    )

    cost_display = CostDisplay(console)
    cost_display.display(estimate)

    if not yes:
        if not typer.confirm("Proceed with analysis?"):
            console.print("[yellow]Analysis cancelled.[/yellow]")
            raise typer.Exit(0)

    console.print(
        Panel(
            f"[bold]Analyzing:[/bold] {', '.join(ticker_list)}\n"
            f"[bold]Agents:[/bold] {', '.join(agent_filter) if agent_filter else 'All'}\n"
            f"[bold]Specialists:[/bold] {'Disabled' if skip_specialists else 'Enabled'}",
            title="Analysis Request",
            border_style="blue",
        )
    )

    # Progress callback for orchestrator
    progress_messages = []

    def progress_callback(msg: str) -> None:
        progress_messages.append(msg)

    # Run analysis
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        async def run_analysis():
            from consilium.db.connection import close_pool

            try:
                orchestrator = AnalysisOrchestrator(
                    settings=settings,
                    progress_callback=lambda msg: progress.update(task, description=msg),
                )

                return await orchestrator.analyze(
                    tickers=ticker_list,
                    agent_filter=agent_filter,
                    include_specialists=not skip_specialists,
                )
            finally:
                await close_pool()

        try:
            result = asyncio.run(run_analysis())
        except Exception as e:
            console.print(f"\n[red]Error during analysis:[/red] {e}")
            raise typer.Exit(1)

    # Display results
    formatter = ResultFormatter(console)
    formatter.display_results(result, verbose=verbose)

    # Export if requested
    if export and output_file:
        try:
            export_result(result, output_file, format=export)
            console.print(f"\n[green]Results exported to {output_file}[/green]")
        except Exception as e:
            console.print(f"\n[red]Export error:[/red] {e}")


@app.command()
def compare(
    tickers: str = typer.Argument(
        ...,
        help="Ticker symbols to compare (comma-separated, e.g., 'AAPL,MSFT,GOOGL')",
    ),
    sort: str = typer.Option(
        "score",
        "--sort",
        "-s",
        help="Sort by: score, agreement, bullish, confidence",
    ),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        "-a",
        help="Specific agents to use (comma-separated IDs)",
    ),
    matrix: bool = typer.Option(
        False,
        "--matrix",
        "-m",
        help="Show agent consensus matrix",
    ),
    themes: bool = typer.Option(
        False,
        "--themes",
        "-t",
        help="Show themes/risks comparison",
    ),
    skip_specialists: bool = typer.Option(
        False,
        "--skip-specialists",
        help="Skip specialist analysis phase",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all comparison views",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip cost confirmation (use with caution)",
    ),
) -> None:
    """
    Compare multiple assets side-by-side.

    Analyzes all tickers and displays a ranked comparison with
    consensus signals, scores, and agent agreement.

    Examples:
        consilium compare AAPL,MSFT,GOOGL
        consilium compare AAPL,MSFT,GOOGL --sort agreement
        consilium compare NVDA,AMD,INTC --matrix --themes
        consilium compare "TSLA,F,GM" --agents buffett,munger --verbose
        consilium compare AAPL,MSFT --yes  # Skip cost confirmation
    """
    settings = get_settings()

    if not settings.is_configured:
        console.print(
            "[red]Error:[/red] ANTHROPIC_API_KEY not configured. "
            "Please set it in your .env file or environment."
        )
        raise typer.Exit(1)

    # Parse tickers
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    if len(ticker_list) < 2:
        console.print("[red]Error:[/red] Need at least 2 tickers to compare.")
        raise typer.Exit(1)

    agent_filter = [a.strip().lower() for a in agents.split(",")] if agents else None

    from rich.progress import Progress, SpinnerColumn, TextColumn
    from consilium.analysis.orchestrator import AnalysisOrchestrator
    from consilium.output.comparison import ComparisonFormatter
    from consilium.llm.cost_estimator import CostEstimator
    from consilium.output.cost_display import CostDisplay

    # Calculate number of agents
    num_investors = len(agent_filter) if agent_filter else 13
    num_specialists = 0 if skip_specialists else 7

    # Show cost estimate and ask for confirmation
    estimator = CostEstimator(settings.model)
    estimate = estimator.estimate(
        num_tickers=len(ticker_list),
        num_investors=num_investors,
        num_specialists=num_specialists,
        include_specialists=not skip_specialists,
    )

    cost_display = CostDisplay(console)
    cost_display.display(estimate)

    if not yes:
        if not typer.confirm("Proceed with comparison?"):
            console.print("[yellow]Comparison cancelled.[/yellow]")
            raise typer.Exit(0)

    console.print(
        Panel(
            f"[bold]Comparing:[/bold] {', '.join(ticker_list)}\n"
            f"[bold]Sort By:[/bold] {sort}\n"
            f"[bold]Agents:[/bold] {', '.join(agent_filter) if agent_filter else 'All'}\n"
            f"[bold]Specialists:[/bold] {'Disabled' if skip_specialists else 'Enabled'}",
            title="Comparison Request",
            border_style="blue",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing assets...", total=None)

        async def run_analysis():
            from consilium.db.connection import close_pool

            try:
                orchestrator = AnalysisOrchestrator(
                    settings=settings,
                    progress_callback=lambda msg: progress.update(task, description=msg),
                )
                return await orchestrator.analyze(
                    tickers=ticker_list,
                    agent_filter=agent_filter,
                    include_specialists=not skip_specialists,
                )
            finally:
                await close_pool()

        try:
            result = asyncio.run(run_analysis())
        except Exception as e:
            console.print(f"\n[red]Error during analysis:[/red] {e}")
            raise typer.Exit(1)

    # Display comparison
    formatter = ComparisonFormatter(console)
    formatter.display_comparison(
        result,
        sort_by=sort,
        show_matrix=matrix,
        show_themes=themes,
        verbose=verbose,
    )


@app.command()
def screen(
    criteria: str = typer.Option(
        "value",
        "--criteria",
        "-c",
        help="Screening criteria: value, growth, momentum, dividend",
    ),
    sector: Optional[str] = typer.Option(
        None,
        "--sector",
        "-s",
        help="Filter by sector",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum results to return",
    ),
) -> None:
    """
    Screen stocks based on predefined criteria.

    Examples:
        consilium screen --criteria value
        consilium screen --criteria growth --sector Technology
    """
    console.print(f"[cyan]Screening with criteria:[/cyan] {criteria}")
    if sector:
        console.print(f"[cyan]Sector filter:[/cyan] {sector}")
    console.print(f"[cyan]Limit:[/cyan] {limit}")
    console.print("\n[yellow]Screening feature not yet implemented.[/yellow]")


# ============== Agent Commands ==============


@agents_app.command("list")
def agents_list(
    agent_type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type: investor or specialist",
    ),
    show_weights: bool = typer.Option(
        False,
        "--weights",
        "-w",
        help="Show agent weights",
    ),
) -> None:
    """
    List all available agents.

    Examples:
        consilium agents list
        consilium agents list --type investor --weights
    """
    from consilium.config import get_settings

    settings = get_settings()

    # Define agent data
    investors = [
        ("buffett", "Warren Buffett", "VALUE", settings.weights.buffett),
        ("munger", "Charlie Munger", "VALUE", settings.weights.munger),
        ("graham", "Ben Graham", "VALUE", settings.weights.graham),
        ("damodaran", "Aswath Damodaran", "VALUE", settings.weights.damodaran),
        ("ackman", "Bill Ackman", "ACTIVIST", settings.weights.ackman),
        ("wood", "Cathie Wood", "GROWTH", settings.weights.wood),
        ("burry", "Michael Burry", "CONTRARIAN", settings.weights.burry),
        ("pabrai", "Mohnish Pabrai", "VALUE", settings.weights.pabrai),
        ("lynch", "Peter Lynch", "GROWTH", settings.weights.lynch),
        ("fisher", "Phil Fisher", "GROWTH", settings.weights.fisher),
        ("jhunjhunwala", "Rakesh Jhunjhunwala", "MOMENTUM", settings.weights.jhunjhunwala),
        ("druckenmiller", "Stanley Druckenmiller", "MACRO", settings.weights.druckenmiller),
        ("simons", "Jim Simons", "QUANTITATIVE", settings.weights.simons),
    ]

    specialists = [
        ("valuation", "Valuation Specialist", "QUANTITATIVE", settings.weights.valuation),
        ("fundamentals", "Fundamentals Specialist", "QUANTITATIVE", settings.weights.fundamentals),
        ("technicals", "Technicals Specialist", "QUANTITATIVE", settings.weights.technicals),
        ("sentiment", "Sentiment Specialist", "QUANTITATIVE", settings.weights.sentiment),
        ("risk", "Risk Manager", "QUANTITATIVE", settings.weights.risk),
        ("portfolio", "Portfolio Manager", "QUANTITATIVE", settings.weights.portfolio),
        ("political", "Political Risk Analyst", "QUANTITATIVE", settings.weights.political),
    ]

    table = Table(title="Available Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Type", style="magenta")
    table.add_column("Style", style="green")
    if show_weights:
        table.add_column("Weight", style="yellow", justify="right")

    agents_to_show = []
    if agent_type is None or agent_type.lower() == "investor":
        agents_to_show.extend([(a, "INVESTOR") for a in investors])
    if agent_type is None or agent_type.lower() == "specialist":
        agents_to_show.extend([(a, "SPECIALIST") for a in specialists])

    for agent_data, atype in agents_to_show:
        agent_id, name, style, weight = agent_data
        row = [agent_id, name, atype, style]
        if show_weights:
            row.append(f"{weight:.1f}")
        table.add_row(*row)

    console.print(table)


@agents_app.command("info")
def agents_info(
    agent_id: str = typer.Argument(..., help="Agent ID to show details"),
) -> None:
    """
    Show detailed information about a specific agent.

    Examples:
        consilium agents info buffett
    """
    agent_info_data = {
        "buffett": {
            "name": "Warren Buffett",
            "type": "INVESTOR",
            "style": "VALUE",
            "description": (
                "The Oracle of Omaha. Focuses on wonderful companies at fair prices, "
                "economic moats, quality management, and long-term compounding. "
                "Emphasizes circle of competence and margin of safety."
            ),
        },
        "munger": {
            "name": "Charlie Munger",
            "type": "INVESTOR",
            "style": "VALUE",
            "description": (
                "Warren Buffett's partner. Uses mental models and multidisciplinary thinking. "
                "Focuses on quality over price, inversion thinking, and avoiding cognitive biases."
            ),
        },
        "graham": {
            "name": "Ben Graham",
            "type": "INVESTOR",
            "style": "VALUE",
            "description": (
                "The godfather of value investing. Focuses on quantitative screens, "
                "margin of safety, net-net valuations, and the Mr. Market analogy."
            ),
        },
        "burry": {
            "name": "Michael Burry",
            "type": "INVESTOR",
            "style": "CONTRARIAN",
            "description": (
                "The Big Short contrarian. Hunts for deep value, analyzes balance sheets, "
                "identifies market bubbles, and maintains patience with unpopular positions."
            ),
        },
    }

    agent_id_lower = agent_id.lower()
    if agent_id_lower not in agent_info_data:
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")
        console.print("[dim]Use 'consilium agents list' to see available agents.[/dim]")
        raise typer.Exit(1)

    info = agent_info_data[agent_id_lower]
    settings = get_settings()
    weight = settings.weights.get_weight(agent_id_lower)

    panel = Panel(
        f"[bold]{info['name']}[/bold]\n\n"
        f"[cyan]Type:[/cyan] {info['type']}\n"
        f"[cyan]Style:[/cyan] {info['style']}\n"
        f"[cyan]Weight:[/cyan] {weight}\n\n"
        f"[yellow]Description:[/yellow]\n{info['description']}",
        title=f"Agent: {agent_id_lower}",
        border_style="blue",
    )
    console.print(panel)


# ============== Watchlist Commands ==============


@watchlist_app.command("create")
def watchlist_create(
    name: str = typer.Argument(..., help="Watchlist name"),
    tickers: list[str] = typer.Argument(..., help="Ticker symbols to add"),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="Watchlist description",
    ),
) -> None:
    """
    Create a new watchlist with tickers.

    Examples:
        consilium watchlist create tech-giants AAPL MSFT GOOGL NVDA META
        consilium watchlist create value-picks AAPL MSFT -d "My value investments"
    """
    async def create_watchlist():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import WatchlistRepository

        try:
            pool = await get_pool()
            repo = WatchlistRepository(pool)

            # Check if already exists
            existing = await repo.get_by_name(name)
            if existing:
                console.print(f"[red]Error:[/red] Watchlist '{name}' already exists.")
                console.print("[dim]Use 'consilium watchlist add' to add tickers to existing list.[/dim]")
                return False

            ticker_list = [t.upper() for t in tickers]
            await repo.create(name, ticker_list, description)
            return ticker_list
        finally:
            await close_pool()

    try:
        result = asyncio.run(create_watchlist())
    except Exception as e:
        console.print(f"[red]Error creating watchlist:[/red] {e}")
        raise typer.Exit(1)

    if result:
        console.print(f"[green]Created watchlist '{name}' with {len(result)} tickers:[/green]")
        console.print(f"  {', '.join(result)}")


@watchlist_app.command("add")
def watchlist_add(
    name: str = typer.Argument(..., help="Watchlist name"),
    tickers: list[str] = typer.Argument(..., help="Ticker symbols to add"),
) -> None:
    """
    Add tickers to an existing watchlist.

    Examples:
        consilium watchlist add tech-giants AMZN TSLA
    """
    async def add_to_watchlist():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import WatchlistRepository

        try:
            pool = await get_pool()
            repo = WatchlistRepository(pool)

            # Check if watchlist exists
            existing = await repo.get_by_name(name)
            if not existing:
                console.print(f"[red]Error:[/red] Watchlist '{name}' not found.")
                console.print("[dim]Use 'consilium watchlist create' to create a new watchlist.[/dim]")
                return None

            ticker_list = [t.upper() for t in tickers]
            await repo.add_tickers(name, ticker_list)

            # Get updated watchlist
            updated = await repo.get_by_name(name)
            return updated
        finally:
            await close_pool()

    try:
        result = asyncio.run(add_to_watchlist())
    except Exception as e:
        console.print(f"[red]Error adding tickers:[/red] {e}")
        raise typer.Exit(1)

    if result:
        added = [t.upper() for t in tickers]
        console.print(f"[green]Added to '{name}':[/green] {', '.join(added)}")
        console.print(f"[dim]Watchlist now has {len(result['tickers'])} tickers[/dim]")


@watchlist_app.command("remove")
def watchlist_remove(
    name: str = typer.Argument(..., help="Watchlist name"),
    tickers: list[str] = typer.Argument(..., help="Ticker symbols to remove"),
) -> None:
    """
    Remove tickers from a watchlist.

    Examples:
        consilium watchlist remove tech-giants META AMZN
    """
    async def remove_from_watchlist():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import WatchlistRepository

        try:
            pool = await get_pool()
            repo = WatchlistRepository(pool)

            # Check if watchlist exists
            existing = await repo.get_by_name(name)
            if not existing:
                console.print(f"[red]Error:[/red] Watchlist '{name}' not found.")
                return None

            ticker_list = [t.upper() for t in tickers]

            # Check which tickers are actually in the list
            current_tickers = set(existing.get("tickers", []))
            to_remove = set(ticker_list) & current_tickers
            not_found = set(ticker_list) - current_tickers

            if not_found:
                console.print(f"[yellow]Warning:[/yellow] Tickers not in watchlist: {', '.join(not_found)}")

            if to_remove:
                await repo.remove_tickers(name, list(to_remove))

            # Get updated watchlist
            updated = await repo.get_by_name(name)
            return updated, list(to_remove)
        finally:
            await close_pool()

    try:
        result = asyncio.run(remove_from_watchlist())
    except Exception as e:
        console.print(f"[red]Error removing tickers:[/red] {e}")
        raise typer.Exit(1)

    if result:
        updated, removed = result
        if removed:
            console.print(f"[green]Removed from '{name}':[/green] {', '.join(removed)}")
        console.print(f"[dim]Watchlist now has {len(updated['tickers'])} tickers[/dim]")


@watchlist_app.command("delete")
def watchlist_delete(
    name: str = typer.Argument(..., help="Watchlist name to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Delete a watchlist.

    Examples:
        consilium watchlist delete old-list
        consilium watchlist delete old-list --force
    """
    async def delete_watchlist():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import WatchlistRepository

        try:
            pool = await get_pool()
            repo = WatchlistRepository(pool)

            # Check if watchlist exists
            existing = await repo.get_by_name(name)
            if not existing:
                console.print(f"[red]Error:[/red] Watchlist '{name}' not found.")
                return False

            return existing
        finally:
            await close_pool()

    async def confirm_and_delete():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import WatchlistRepository

        try:
            pool = await get_pool()
            repo = WatchlistRepository(pool)
            await repo.delete(name)
            return True
        finally:
            await close_pool()

    try:
        existing = asyncio.run(delete_watchlist())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not existing:
        raise typer.Exit(1)

    ticker_count = len(existing.get("tickers", []))

    if not force:
        confirm = typer.confirm(
            f"Delete watchlist '{name}' with {ticker_count} tickers?"
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    try:
        asyncio.run(confirm_and_delete())
        console.print(f"[green]Deleted watchlist '{name}'[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting watchlist:[/red] {e}")
        raise typer.Exit(1)


@watchlist_app.command("list")
def watchlist_list() -> None:
    """
    List all watchlists.

    Examples:
        consilium watchlist list
    """
    async def fetch_watchlists():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import WatchlistRepository

        try:
            pool = await get_pool()
            repo = WatchlistRepository(pool)
            return await repo.list_all()
        finally:
            await close_pool()

    try:
        watchlists = asyncio.run(fetch_watchlists())
    except Exception as e:
        console.print(f"[red]Error fetching watchlists:[/red] {e}")
        raise typer.Exit(1)

    if not watchlists:
        console.print("[yellow]No watchlists found.[/yellow]")
        console.print("[dim]Use 'consilium watchlist create' to create one.[/dim]")
        return

    table = Table(title="Watchlists")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Created", style="dim")
    table.add_column("Updated", style="dim")

    for wl in watchlists:
        desc = wl.get("description") or "-"
        created = wl.get("created_at").strftime("%Y-%m-%d") if wl.get("created_at") else "-"
        updated = wl.get("updated_at").strftime("%Y-%m-%d") if wl.get("updated_at") else "-"
        table.add_row(wl["name"], desc[:40], created, updated)

    console.print(table)
    console.print(f"\n[dim]Use 'consilium watchlist show <name>' for details[/dim]")


@watchlist_app.command("show")
def watchlist_show(
    name: str = typer.Argument(..., help="Watchlist name"),
) -> None:
    """
    Show details and tickers of a watchlist.

    Examples:
        consilium watchlist show tech-giants
    """
    async def fetch_watchlist():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import WatchlistRepository

        try:
            pool = await get_pool()
            repo = WatchlistRepository(pool)
            return await repo.get_by_name(name)
        finally:
            await close_pool()

    try:
        watchlist = asyncio.run(fetch_watchlist())
    except Exception as e:
        console.print(f"[red]Error fetching watchlist:[/red] {e}")
        raise typer.Exit(1)

    if not watchlist:
        console.print(f"[red]Watchlist '{name}' not found.[/red]")
        raise typer.Exit(1)

    tickers = watchlist.get("tickers", [])
    desc = watchlist.get("description") or "No description"
    created = watchlist.get("created_at").strftime("%Y-%m-%d %H:%M") if watchlist.get("created_at") else "N/A"
    updated = watchlist.get("updated_at").strftime("%Y-%m-%d %H:%M") if watchlist.get("updated_at") else "N/A"

    panel_content = (
        f"[bold]Description:[/bold] {desc}\n"
        f"[bold]Tickers:[/bold] {len(tickers)}\n"
        f"[bold]Created:[/bold] {created}\n"
        f"[bold]Updated:[/bold] {updated}\n\n"
        f"[cyan]{', '.join(tickers) if tickers else 'No tickers'}[/cyan]"
    )

    console.print(Panel(panel_content, title=f"Watchlist: {name}", border_style="blue"))
    console.print(f"\n[dim]Use 'consilium watchlist analyze {name}' to run analysis[/dim]")


@watchlist_app.command("analyze")
def watchlist_analyze(
    name: str = typer.Argument(..., help="Watchlist name"),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        "-a",
        help="Specific agents to use (comma-separated IDs)",
    ),
    skip_specialists: bool = typer.Option(
        False,
        "--skip-specialists",
        "-s",
        help="Skip specialist analysis phase",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed agent reasoning",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip cost confirmation (use with caution)",
    ),
) -> None:
    """
    Analyze all tickers in a watchlist.

    Examples:
        consilium watchlist analyze tech-giants
        consilium watchlist analyze tech-giants --verbose
        consilium watchlist analyze tech-giants --agents buffett,munger
        consilium watchlist analyze tech-giants --yes  # Skip cost confirmation
    """
    settings = get_settings()

    if not settings.is_configured:
        console.print(
            "[red]Error:[/red] ANTHROPIC_API_KEY not configured. "
            "Please set it in your .env file or environment."
        )
        raise typer.Exit(1)

    async def fetch_watchlist():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import WatchlistRepository

        try:
            pool = await get_pool()
            repo = WatchlistRepository(pool)
            return await repo.get_by_name(name)
        finally:
            await close_pool()

    try:
        watchlist = asyncio.run(fetch_watchlist())
    except Exception as e:
        console.print(f"[red]Error fetching watchlist:[/red] {e}")
        raise typer.Exit(1)

    if not watchlist:
        console.print(f"[red]Watchlist '{name}' not found.[/red]")
        raise typer.Exit(1)

    tickers = watchlist.get("tickers", [])
    if not tickers:
        console.print(f"[yellow]Watchlist '{name}' has no tickers.[/yellow]")
        raise typer.Exit(0)

    agent_filter = [a.strip().lower() for a in agents.split(",")] if agents else None

    from rich.progress import Progress, SpinnerColumn, TextColumn
    from consilium.analysis.orchestrator import AnalysisOrchestrator
    from consilium.output.formatters import ResultFormatter
    from consilium.llm.cost_estimator import CostEstimator
    from consilium.output.cost_display import CostDisplay

    # Calculate number of agents
    num_investors = len(agent_filter) if agent_filter else 13
    num_specialists = 0 if skip_specialists else 7

    # Show cost estimate and ask for confirmation
    estimator = CostEstimator(settings.model)
    estimate = estimator.estimate(
        num_tickers=len(tickers),
        num_investors=num_investors,
        num_specialists=num_specialists,
        include_specialists=not skip_specialists,
    )

    cost_display = CostDisplay(console)
    cost_display.display(estimate)

    if not yes:
        if not typer.confirm("Proceed with analysis?"):
            console.print("[yellow]Analysis cancelled.[/yellow]")
            raise typer.Exit(0)

    console.print(
        Panel(
            f"[bold]Watchlist:[/bold] {name}\n"
            f"[bold]Tickers:[/bold] {', '.join(tickers)}\n"
            f"[bold]Agents:[/bold] {', '.join(agent_filter) if agent_filter else 'All'}\n"
            f"[bold]Specialists:[/bold] {'Disabled' if skip_specialists else 'Enabled'}",
            title="Watchlist Analysis",
            border_style="blue",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        async def run_analysis():
            from consilium.db.connection import close_pool

            try:
                orchestrator = AnalysisOrchestrator(
                    settings=settings,
                    progress_callback=lambda msg: progress.update(task, description=msg),
                )

                return await orchestrator.analyze(
                    tickers=tickers,
                    agent_filter=agent_filter,
                    include_specialists=not skip_specialists,
                )
            finally:
                await close_pool()

        try:
            result = asyncio.run(run_analysis())
        except Exception as e:
            console.print(f"\n[red]Error during analysis:[/red] {e}")
            raise typer.Exit(1)

    # Display results
    formatter = ResultFormatter(console)
    formatter.display_results(result, verbose=verbose)


# ============== Universe Commands ==============


@universe_app.command("list")
def universe_list() -> None:
    """
    List all available universes.

    Shows both built-in universes (e.g., mag7, brazilian) and external index-based
    universes (e.g., sp500, nasdaq100).

    Examples:
        consilium universe list
    """
    from consilium.data.universes import UniverseDataProvider

    provider = UniverseDataProvider()
    available = provider.get_available_universes()

    table = Table(title="Available Stock Universes")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Status", style="yellow")

    async def check_populated():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import UniverseRepository

        try:
            pool = await get_pool()
            repo = UniverseRepository(pool)
            populated = await repo.list_universes()
            return {u["name"]: u for u in populated}
        finally:
            await close_pool()

    try:
        populated = asyncio.run(check_populated())
    except Exception:
        populated = {}

    for name in available:
        desc = provider.UNIVERSE_DESCRIPTIONS.get(name, "")
        if name in populated:
            count = populated[name].get("ticker_count", 0)
            status = f"[green]{count} tickers[/green]"
        else:
            status = "[dim]Not populated[/dim]"
        table.add_row(name, desc, status)

    console.print(table)
    console.print("\n[dim]Use 'consilium universe populate <name>' to fetch data[/dim]")


@universe_app.command("populate")
def universe_populate(
    name: str = typer.Argument(
        None,
        help="Universe name (sp500, nasdaq100, dow30, mag7, brazilian)",
    ),
    all_universes: bool = typer.Option(
        False,
        "--all",
        help="Populate all built-in universes",
    ),
) -> None:
    """
    Populate a stock universe from external data source.

    Fetches index constituents and saves to database for fast access.

    Examples:
        consilium universe populate sp500
        consilium universe populate --all
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from consilium.data.universes import UniverseDataProvider

    provider = UniverseDataProvider()

    if all_universes:
        names_to_populate = provider.get_available_universes()
    elif name:
        names_to_populate = [name.lower()]
    else:
        console.print("[red]Error:[/red] Provide a universe name or use --all")
        raise typer.Exit(1)

    async def populate_universe(u_name: str):
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import UniverseRepository

        data = provider.fetch_universe(u_name)
        if not data:
            return None, f"Universe '{u_name}' not found"

        try:
            pool = await get_pool()
            repo = UniverseRepository(pool)
            await repo.save_universe(
                name=data.name,
                tickers=data.tickers,
                description=data.description,
                source_url=data.source_url,
            )
            return data, None
        finally:
            await close_pool()

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for u_name in names_to_populate:
            task = progress.add_task(f"Fetching {u_name}...", total=None)
            try:
                data, error = asyncio.run(populate_universe(u_name))
                if error:
                    results.append((u_name, None, error))
                else:
                    results.append((u_name, data, None))
            except Exception as e:
                results.append((u_name, None, str(e)))
            progress.remove_task(task)

    # Display results
    table = Table(title="Universe Population Results")
    table.add_column("Universe", style="cyan")
    table.add_column("Tickers", justify="right")
    table.add_column("Status")

    for u_name, data, error in results:
        if error:
            table.add_row(u_name, "-", f"[red]{error}[/red]")
        else:
            table.add_row(u_name, str(len(data.tickers)), "[green]Saved[/green]")

    console.print(table)


@universe_app.command("show")
def universe_show(
    name: str = typer.Argument(..., help="Universe name"),
) -> None:
    """
    Show universe details and tickers.

    Examples:
        consilium universe show mag7
        consilium universe show sp500
    """
    async def fetch_universe():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import UniverseRepository

        try:
            pool = await get_pool()
            repo = UniverseRepository(pool)
            return await repo.get_universe(name.lower())
        finally:
            await close_pool()

    try:
        universe = asyncio.run(fetch_universe())
    except Exception as e:
        console.print(f"[red]Error fetching universe:[/red] {e}")
        raise typer.Exit(1)

    if not universe:
        # Try fetching from provider directly
        from consilium.data.universes import UniverseDataProvider
        provider = UniverseDataProvider()
        data = provider.fetch_universe(name)
        if data:
            console.print(f"[yellow]Universe '{name}' not populated in database.[/yellow]")
            console.print(f"[dim]Use 'consilium universe populate {name}' first.[/dim]")
            console.print(f"\n[cyan]Available tickers ({len(data.tickers)}):[/cyan]")
            console.print(f"  {', '.join(data.tickers[:20])}{'...' if len(data.tickers) > 20 else ''}")
        else:
            console.print(f"[red]Universe '{name}' not found.[/red]")
        raise typer.Exit(1)

    tickers = universe.get("tickers", [])
    desc = universe.get("description") or "No description"
    updated = universe.get("last_updated")
    updated_str = updated.strftime("%Y-%m-%d %H:%M") if updated else "N/A"

    # Group tickers for display
    ticker_groups = []
    for i in range(0, len(tickers), 10):
        ticker_groups.append(", ".join(tickers[i:i+10]))

    panel_content = (
        f"[bold]Description:[/bold] {desc}\n"
        f"[bold]Tickers:[/bold] {len(tickers)}\n"
        f"[bold]Last Updated:[/bold] {updated_str}\n\n"
        f"[cyan]Tickers:[/cyan]\n" + "\n".join(ticker_groups)
    )

    console.print(Panel(panel_content, title=f"Universe: {name}", border_style="blue"))
    console.print(f"\n[dim]Use 'consilium universe analyze {name}' to run analysis[/dim]")


@universe_app.command("sync")
def universe_sync(
    name: str = typer.Argument(..., help="Universe name to re-fetch"),
) -> None:
    """
    Re-fetch and update universe data from source.

    Examples:
        consilium universe sync sp500
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from consilium.data.universes import UniverseDataProvider

    provider = UniverseDataProvider()

    async def sync_universe():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import UniverseRepository

        data = provider.fetch_universe(name.lower())
        if not data:
            return None, f"Universe '{name}' not found"

        try:
            pool = await get_pool()
            repo = UniverseRepository(pool)

            # Get old count for comparison
            existing = await repo.get_universe(name.lower())
            old_count = len(existing.get("tickers", [])) if existing else 0

            await repo.save_universe(
                name=data.name,
                tickers=data.tickers,
                description=data.description,
                source_url=data.source_url,
            )
            return data, old_count, None
        finally:
            await close_pool()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Syncing {name}...", total=None)
        try:
            result = asyncio.run(sync_universe())
        except Exception as e:
            console.print(f"[red]Error syncing universe:[/red] {e}")
            raise typer.Exit(1)

    if result[2]:  # error
        console.print(f"[red]Error:[/red] {result[2]}")
        raise typer.Exit(1)

    data, old_count, _ = result
    diff = len(data.tickers) - old_count
    diff_str = f"(+{diff})" if diff > 0 else f"({diff})" if diff < 0 else "(no change)"

    console.print(f"[green]Synced '{name}':[/green] {len(data.tickers)} tickers {diff_str}")


@universe_app.command("delete")
def universe_delete(
    name: str = typer.Argument(..., help="Universe name to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Delete a universe from the database.

    Examples:
        consilium universe delete sp500
        consilium universe delete sp500 --force
    """
    async def fetch_universe():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import UniverseRepository

        try:
            pool = await get_pool()
            repo = UniverseRepository(pool)
            return await repo.get_universe(name.lower())
        finally:
            await close_pool()

    async def do_delete():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import UniverseRepository

        try:
            pool = await get_pool()
            repo = UniverseRepository(pool)
            return await repo.delete_universe(name.lower())
        finally:
            await close_pool()

    try:
        existing = asyncio.run(fetch_universe())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not existing:
        console.print(f"[red]Universe '{name}' not found in database.[/red]")
        raise typer.Exit(1)

    ticker_count = len(existing.get("tickers", []))

    if not force:
        confirm = typer.confirm(
            f"Delete universe '{name}' with {ticker_count} tickers?"
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    try:
        asyncio.run(do_delete())
        console.print(f"[green]Deleted universe '{name}'[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting universe:[/red] {e}")
        raise typer.Exit(1)


@universe_app.command("analyze")
def universe_analyze(
    name: str = typer.Argument(..., help="Universe name"),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        "-l",
        help="Analyze only N random tickers (for large universes)",
    ),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        "-a",
        help="Specific agents to use (comma-separated IDs)",
    ),
    skip_specialists: bool = typer.Option(
        False,
        "--skip-specialists",
        "-s",
        help="Skip specialist analysis phase",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed agent reasoning",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip cost confirmation (use with caution)",
    ),
) -> None:
    """
    Analyze all tickers in a universe.

    For large universes like sp500, use --limit to analyze a subset.

    Examples:
        consilium universe analyze mag7
        consilium universe analyze mag7 --verbose
        consilium universe analyze sp500 --limit 10 --agents buffett,simons
    """
    import random

    settings = get_settings()

    if not settings.is_configured:
        console.print(
            "[red]Error:[/red] ANTHROPIC_API_KEY not configured. "
            "Please set it in your .env file or environment."
        )
        raise typer.Exit(1)

    async def fetch_universe():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import UniverseRepository

        try:
            pool = await get_pool()
            repo = UniverseRepository(pool)
            return await repo.get_universe(name.lower())
        finally:
            await close_pool()

    try:
        universe = asyncio.run(fetch_universe())
    except Exception as e:
        console.print(f"[red]Error fetching universe:[/red] {e}")
        raise typer.Exit(1)

    if not universe:
        # Check if universe exists but not populated
        from consilium.data.universes import UniverseDataProvider
        provider = UniverseDataProvider()
        if name.lower() in provider.get_available_universes():
            console.print(f"[yellow]Universe '{name}' not populated.[/yellow]")
            console.print(f"[dim]Run 'consilium universe populate {name}' first.[/dim]")
        else:
            console.print(f"[red]Universe '{name}' not found.[/red]")
        raise typer.Exit(1)

    tickers = universe.get("tickers", [])
    if not tickers:
        console.print(f"[yellow]Universe '{name}' has no tickers.[/yellow]")
        raise typer.Exit(0)

    # Apply limit if specified
    original_count = len(tickers)
    if limit and limit < len(tickers):
        tickers = random.sample(tickers, limit)
        console.print(f"[dim]Sampling {limit} of {original_count} tickers[/dim]")

    agent_filter = [a.strip().lower() for a in agents.split(",")] if agents else None

    from rich.progress import Progress, SpinnerColumn, TextColumn
    from consilium.analysis.orchestrator import AnalysisOrchestrator
    from consilium.output.formatters import ResultFormatter
    from consilium.llm.cost_estimator import CostEstimator
    from consilium.output.cost_display import CostDisplay

    console.print(
        Panel(
            f"[bold]Universe:[/bold] {name}\n"
            f"[bold]Tickers:[/bold] {len(tickers)} of {original_count}\n"
            f"[bold]Agents:[/bold] {', '.join(agent_filter) if agent_filter else 'All'}\n"
            f"[bold]Specialists:[/bold] {'Disabled' if skip_specialists else 'Enabled'}",
            title="Universe Analysis",
            border_style="blue",
        )
    )

    # Calculate number of agents for cost estimation
    num_investors = len(agent_filter) if agent_filter else 13
    num_specialists = 0 if skip_specialists else 7

    # Show cost estimate and ask for confirmation
    estimator = CostEstimator(settings.model)
    estimate = estimator.estimate(
        num_tickers=len(tickers),
        num_investors=num_investors,
        num_specialists=num_specialists,
        include_specialists=not skip_specialists,
    )

    cost_display = CostDisplay(console)
    cost_display.display(estimate)

    if not yes:
        if not typer.confirm("Proceed with analysis?"):
            console.print("[yellow]Analysis cancelled.[/yellow]")
            raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        async def run_analysis():
            from consilium.db.connection import close_pool

            try:
                orchestrator = AnalysisOrchestrator(
                    settings=settings,
                    progress_callback=lambda msg: progress.update(task, description=msg),
                )

                return await orchestrator.analyze(
                    tickers=tickers,
                    agent_filter=agent_filter,
                    include_specialists=not skip_specialists,
                )
            finally:
                await close_pool()

        try:
            result = asyncio.run(run_analysis())
        except Exception as e:
            console.print(f"\n[red]Error during analysis:[/red] {e}")
            raise typer.Exit(1)

    # Display results
    formatter = ResultFormatter(console)
    formatter.display_results(result, verbose=verbose)


# ============== Portfolio Commands ==============


@portfolio_app.command("create")
def portfolio_create(
    name: str = typer.Argument(..., help="Portfolio name"),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="Portfolio description",
    ),
    currency: str = typer.Option(
        "USD",
        "--currency",
        "-c",
        help="Portfolio currency (default: USD)",
    ),
) -> None:
    """
    Create a new portfolio.

    Examples:
        consilium portfolio create "Tech Holdings"
        consilium portfolio create "Tech Holdings" -d "My tech investments" -c USD
    """
    async def create():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            # Check if already exists
            existing = await repo.get_portfolio_by_name(name)
            if existing:
                console.print(f"[red]Error:[/red] Portfolio '{name}' already exists.")
                return None

            portfolio_id = await repo.create_portfolio(name, description, currency)
            return portfolio_id
        finally:
            await close_pool()

    try:
        portfolio_id = asyncio.run(create())
    except Exception as e:
        console.print(f"[red]Error creating portfolio:[/red] {e}")
        raise typer.Exit(1)

    if portfolio_id:
        console.print(f"[green]Created portfolio '{name}'[/green]")
        console.print("[dim]Use 'consilium portfolio add' to add positions[/dim]")


@portfolio_app.command("add")
def portfolio_add(
    name: str = typer.Argument(..., help="Portfolio name"),
    ticker: str = typer.Argument(..., help="Ticker symbol"),
    quantity: float = typer.Argument(..., help="Number of shares"),
    price: float = typer.Argument(..., help="Purchase price per share"),
    date: Optional[str] = typer.Option(
        None,
        "--date",
        "-d",
        help="Purchase date (YYYY-MM-DD), defaults to today",
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        "-n",
        help="Notes for this position",
    ),
) -> None:
    """
    Add a position to a portfolio.

    Examples:
        consilium portfolio add "Tech Holdings" AAPL 100 150.00
        consilium portfolio add "Tech Holdings" NVDA 50 450.00 --date 2024-01-15
        consilium portfolio add "Tech Holdings" MSFT 25 380.00 -n "Earnings play"
    """
    from datetime import date as dt_date
    from decimal import Decimal

    # Parse date
    if date:
        try:
            from datetime import datetime
            purchase_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid date format. Use YYYY-MM-DD.")
            raise typer.Exit(1)
    else:
        purchase_date = dt_date.today()

    async def add_position():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            # Check if portfolio exists
            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                console.print(f"[red]Error:[/red] Portfolio '{name}' not found.")
                return None

            position_id = await repo.add_position(
                portfolio_id=portfolio.id,
                ticker=ticker.upper(),
                quantity=Decimal(str(quantity)),
                purchase_price=Decimal(str(price)),
                purchase_date=purchase_date,
                notes=notes,
            )
            return position_id, portfolio
        finally:
            await close_pool()

    try:
        result = asyncio.run(add_position())
    except Exception as e:
        console.print(f"[red]Error adding position:[/red] {e}")
        raise typer.Exit(1)

    if result:
        position_id, portfolio = result
        total_value = quantity * price
        console.print(
            f"[green]Added to '{name}':[/green] {quantity} {ticker.upper()} @ ${price:.2f} = ${total_value:,.2f}"
        )
        console.print(f"[dim]Purchase date: {purchase_date}[/dim]")


@portfolio_app.command("list")
def portfolio_list() -> None:
    """
    List all portfolios.

    Examples:
        consilium portfolio list
    """
    async def fetch_portfolios():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)
            return await repo.list_portfolios()
        finally:
            await close_pool()

    try:
        portfolios = asyncio.run(fetch_portfolios())
    except Exception as e:
        console.print(f"[red]Error fetching portfolios:[/red] {e}")
        raise typer.Exit(1)

    if not portfolios:
        console.print("[yellow]No portfolios found.[/yellow]")
        console.print("[dim]Use 'consilium portfolio create' to create one.[/dim]")
        return

    from consilium.output.portfolio_formatter import PortfolioFormatter
    formatter = PortfolioFormatter(console)
    formatter.display_portfolio_list(portfolios)
    console.print(f"\n[dim]Use 'consilium portfolio show <name>' for details[/dim]")


@portfolio_app.command("show")
def portfolio_show(
    name: str = typer.Argument(..., help="Portfolio name"),
    refresh: bool = typer.Option(
        True,
        "--refresh/--no-refresh",
        help="Fetch current prices (default: yes)",
    ),
) -> None:
    """
    Show portfolio details with positions and P&L.

    Examples:
        consilium portfolio show "Tech Holdings"
        consilium portfolio show "Tech Holdings" --no-refresh
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    async def fetch_portfolio():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository
        from consilium.portfolio.analyzer import PortfolioAnalyzer

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                return None, None

            positions = await repo.get_positions(portfolio.id)
            return portfolio, positions
        finally:
            await close_pool()

    try:
        portfolio, positions = asyncio.run(fetch_portfolio())
    except Exception as e:
        console.print(f"[red]Error fetching portfolio:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(1)

    if not positions:
        console.print(f"[yellow]Portfolio '{name}' has no positions.[/yellow]")
        console.print("[dim]Use 'consilium portfolio add' to add positions[/dim]")
        return

    # Get summary with optional price refresh
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=not refresh,
    ) as progress:
        if refresh:
            progress.add_task("Fetching current prices...", total=None)

        async def get_summary():
            from consilium.db.connection import close_pool
            from consilium.portfolio.analyzer import PortfolioAnalyzer

            try:
                analyzer = PortfolioAnalyzer()
                return await analyzer.get_portfolio_summary(
                    portfolio, positions, refresh_prices=refresh
                )
            finally:
                await close_pool()

        try:
            summary = asyncio.run(get_summary())
        except Exception as e:
            console.print(f"[red]Error calculating summary:[/red] {e}")
            raise typer.Exit(1)

    from consilium.output.portfolio_formatter import PortfolioFormatter
    formatter = PortfolioFormatter(console)
    formatter.display_portfolio_summary(summary)
    console.print(f"\n[dim]Use 'consilium portfolio analyze {name}' to run agent analysis[/dim]")


@portfolio_app.command("remove")
def portfolio_remove(
    name: str = typer.Argument(..., help="Portfolio name"),
    ticker: str = typer.Argument(..., help="Ticker symbol to remove"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Remove all positions for a ticker from a portfolio.

    Examples:
        consilium portfolio remove "Tech Holdings" AAPL
        consilium portfolio remove "Tech Holdings" AAPL --force
    """
    async def check_positions():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                return None, []

            positions = await repo.get_position_by_ticker(portfolio.id, ticker)
            return portfolio, positions
        finally:
            await close_pool()

    async def do_remove(portfolio_id: int):
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)
            return await repo.delete_positions_by_ticker(portfolio_id, ticker)
        finally:
            await close_pool()

    try:
        portfolio, positions = asyncio.run(check_positions())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(1)

    if not positions:
        console.print(f"[yellow]No positions found for {ticker.upper()} in '{name}'[/yellow]")
        return

    total_shares = sum(p.quantity for p in positions)
    total_value = sum(p.cost_basis for p in positions)

    if not force:
        confirm = typer.confirm(
            f"Remove {len(positions)} position(s) for {ticker.upper()} ({total_shares:,.4f} shares, ${total_value:,.2f} cost basis)?"
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    try:
        deleted = asyncio.run(do_remove(portfolio.id))
        console.print(f"[green]Removed {deleted} position(s) for {ticker.upper()} from '{name}'[/green]")
    except Exception as e:
        console.print(f"[red]Error removing positions:[/red] {e}")
        raise typer.Exit(1)


@portfolio_app.command("delete")
def portfolio_delete(
    name: str = typer.Argument(..., help="Portfolio name to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Delete a portfolio and all its positions.

    Examples:
        consilium portfolio delete "Old Portfolio"
        consilium portfolio delete "Old Portfolio" --force
    """
    async def check_portfolio():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                return None, 0

            positions = await repo.get_positions(portfolio.id)
            return portfolio, len(positions)
        finally:
            await close_pool()

    async def do_delete():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)
            return await repo.delete_portfolio_by_name(name)
        finally:
            await close_pool()

    try:
        portfolio, position_count = asyncio.run(check_portfolio())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(
            f"Delete portfolio '{name}' with {position_count} positions?"
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    try:
        asyncio.run(do_delete())
        console.print(f"[green]Deleted portfolio '{name}'[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting portfolio:[/red] {e}")
        raise typer.Exit(1)


@portfolio_app.command("import")
def portfolio_import(
    name: str = typer.Argument(..., help="Portfolio name"),
    file_path: str = typer.Argument(..., help="CSV file path"),
    preview: bool = typer.Option(
        False,
        "--preview",
        "-p",
        help="Preview import without saving",
    ),
    ticker_col: Optional[str] = typer.Option(
        None,
        "--ticker",
        help="Ticker column name override",
    ),
    quantity_col: Optional[str] = typer.Option(
        None,
        "--quantity",
        help="Quantity column name override",
    ),
    price_col: Optional[str] = typer.Option(
        None,
        "--price",
        help="Price column name override",
    ),
    date_col: Optional[str] = typer.Option(
        None,
        "--date",
        help="Date column name override",
    ),
) -> None:
    """
    Import positions from a CSV file.

    Auto-detects columns or use overrides for custom column names.

    Examples:
        consilium portfolio import "Tech Holdings" holdings.csv
        consilium portfolio import "Tech Holdings" holdings.csv --preview
        consilium portfolio import "Tech Holdings" broker.csv --ticker symbol --quantity shares
    """
    from pathlib import Path

    csv_path = Path(file_path)
    if not csv_path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(1)

    async def get_portfolio():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)
            return await repo.get_portfolio_by_name(name)
        finally:
            await close_pool()

    try:
        portfolio = asyncio.run(get_portfolio())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        console.print("[dim]Create it first with 'consilium portfolio create'[/dim]")
        raise typer.Exit(1)

    from consilium.portfolio.importer import CSVImporter
    from consilium.core.portfolio_models import CSVColumnMapping

    importer = CSVImporter()

    # Build custom mapping if provided
    custom_mapping = None
    if any([ticker_col, quantity_col, price_col, date_col]):
        custom_mapping = CSVColumnMapping(
            ticker=ticker_col or "ticker",
            quantity=quantity_col or "quantity",
            purchase_price=price_col or "purchase_price",
            purchase_date=date_col or "purchase_date",
        )

    if preview:
        # Preview mode
        try:
            mapping, rows = importer.preview(csv_path, custom_mapping, limit=5)
            from consilium.output.portfolio_formatter import PortfolioFormatter
            formatter = PortfolioFormatter(console)
            formatter.display_import_preview(mapping.model_dump(), rows)
            console.print("\n[dim]Run without --preview to import[/dim]")
        except Exception as e:
            console.print(f"[red]Error parsing CSV:[/red] {e}")
            raise typer.Exit(1)
        return

    # Full import
    try:
        result = importer.parse_file(csv_path, portfolio.id, custom_mapping)
    except Exception as e:
        console.print(f"[red]Error parsing CSV:[/red] {e}")
        raise typer.Exit(1)

    if result.records_success == 0:
        console.print("[red]No valid records found in CSV.[/red]")
        if result.errors:
            from consilium.output.portfolio_formatter import PortfolioFormatter
            formatter = PortfolioFormatter(console)
            formatter.display_import_result(result)
        raise typer.Exit(1)

    # Save positions to database
    async def save_positions():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            saved = 0
            for position in result.positions_created:
                await repo.add_position(
                    portfolio_id=portfolio.id,
                    ticker=position.ticker,
                    quantity=position.quantity,
                    purchase_price=position.purchase_price,
                    purchase_date=position.purchase_date,
                    notes=position.notes,
                )
                saved += 1

            # Save import history
            await repo.save_import(
                portfolio_id=portfolio.id,
                file_name=result.file_name,
                records_total=result.records_total,
                records_success=result.records_success,
                records_failed=result.records_failed,
                errors=result.errors,
                column_mapping=result.column_mapping,
            )

            return saved
        finally:
            await close_pool()

    try:
        saved = asyncio.run(save_positions())
    except Exception as e:
        console.print(f"[red]Error saving positions:[/red] {e}")
        raise typer.Exit(1)

    from consilium.output.portfolio_formatter import PortfolioFormatter
    formatter = PortfolioFormatter(console)
    formatter.display_import_result(result)


@portfolio_app.command("import-history")
def portfolio_import_history(
    name: str = typer.Argument(..., help="Portfolio name"),
) -> None:
    """
    Show import history for a portfolio.

    Examples:
        consilium portfolio import-history "Tech Holdings"
    """
    async def fetch_history():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                return None, []

            history = await repo.get_import_history(portfolio.id)
            return portfolio, history
        finally:
            await close_pool()

    try:
        portfolio, history = asyncio.run(fetch_history())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(1)

    from consilium.output.portfolio_formatter import PortfolioFormatter
    formatter = PortfolioFormatter(console)
    formatter.display_import_history(history)


@portfolio_app.command("analyze")
def portfolio_analyze(
    name: str = typer.Argument(..., help="Portfolio name"),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        "-a",
        help="Specific agents to use (comma-separated IDs)",
    ),
    skip_specialists: bool = typer.Option(
        False,
        "--skip-specialists",
        "-s",
        help="Skip specialist analysis phase",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed analysis",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip cost confirmation (use with caution)",
    ),
    export: Optional[str] = typer.Option(
        None,
        "--export",
        "-e",
        help="Export format: json",
    ),
    output_file: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path for export",
    ),
) -> None:
    """
    Analyze portfolio positions using multi-agent system.

    Examples:
        consilium portfolio analyze "Tech Holdings"
        consilium portfolio analyze "Tech Holdings" --verbose
        consilium portfolio analyze "Tech Holdings" --agents buffett,munger --yes
        consilium portfolio analyze "Tech Holdings" --export json -o analysis.json
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    settings = get_settings()

    if not settings.is_configured:
        console.print(
            "[red]Error:[/red] ANTHROPIC_API_KEY not configured. "
            "Please set it in your .env file or environment."
        )
        raise typer.Exit(1)

    async def fetch_portfolio():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                return None, []

            positions = await repo.get_positions(portfolio.id)
            return portfolio, positions
        finally:
            await close_pool()

    try:
        portfolio, positions = asyncio.run(fetch_portfolio())
    except Exception as e:
        console.print(f"[red]Error fetching portfolio:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(1)

    if not positions:
        console.print(f"[yellow]Portfolio '{name}' has no positions to analyze.[/yellow]")
        raise typer.Exit(0)

    # Get unique tickers
    tickers = list(set(p.ticker for p in positions))
    agent_filter = [a.strip().lower() for a in agents.split(",")] if agents else None

    from consilium.llm.cost_estimator import CostEstimator
    from consilium.output.cost_display import CostDisplay

    # Calculate number of agents for cost estimation
    num_investors = len(agent_filter) if agent_filter else 13
    num_specialists = 0 if skip_specialists else 7

    # Show cost estimate
    estimator = CostEstimator(settings.model)
    estimate = estimator.estimate(
        num_tickers=len(tickers),
        num_investors=num_investors,
        num_specialists=num_specialists,
        include_specialists=not skip_specialists,
    )

    cost_display = CostDisplay(console)
    cost_display.display(estimate)

    console.print(
        Panel(
            f"[bold]Portfolio:[/bold] {name}\n"
            f"[bold]Positions:[/bold] {len(positions)} ({len(tickers)} unique tickers)\n"
            f"[bold]Agents:[/bold] {', '.join(agent_filter) if agent_filter else 'All'}\n"
            f"[bold]Specialists:[/bold] {'Disabled' if skip_specialists else 'Enabled'}",
            title="Portfolio Analysis",
            border_style="blue",
        )
    )

    if not yes:
        if not typer.confirm("Proceed with analysis?"):
            console.print("[yellow]Analysis cancelled.[/yellow]")
            raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing analysis...", total=None)

        async def run_analysis():
            from consilium.db.connection import close_pool
            from consilium.portfolio.analyzer import PortfolioAnalyzer
            from consilium.db.portfolio_repository import PortfolioRepository
            from consilium.db.connection import get_pool

            try:
                analyzer = PortfolioAnalyzer(
                    settings=settings,
                    progress_callback=lambda msg: progress.update(task, description=msg),
                )

                result = await analyzer.analyze(
                    portfolio=portfolio,
                    positions=positions,
                    agent_filter=agent_filter,
                    include_specialists=not skip_specialists,
                )

                # Save analysis to database
                pool = await get_pool()
                repo = PortfolioRepository(pool)
                await repo.save_portfolio_analysis(
                    portfolio_id=portfolio.id,
                    analysis_id=None,  # Would link to main analysis if we had the DB ID
                    total_value=result.total_value,
                    total_cost_basis=result.total_cost_basis,
                    total_pnl=result.total_pnl,
                    total_pnl_percent=result.total_pnl_percent,
                    portfolio_signal=result.portfolio_signal.value,
                    portfolio_score=result.portfolio_score,
                    sector_allocation=[s.model_dump() for s in result.sector_allocations],
                    position_recommendations=[
                        {
                            "ticker": pa.position.ticker,
                            "signal": pa.signal.value if pa.signal else None,
                            "action": pa.recommended_action.value,
                            "weight": float(pa.weight_in_portfolio),
                        }
                        for pa in result.positions_with_analysis
                    ],
                )

                return result
            finally:
                await close_pool()

        try:
            result = asyncio.run(run_analysis())
        except Exception as e:
            console.print(f"\n[red]Error during analysis:[/red] {e}")
            raise typer.Exit(1)

    # Display results
    from consilium.output.portfolio_formatter import PortfolioFormatter
    formatter = PortfolioFormatter(console)
    formatter.display_portfolio_analysis(result, verbose=verbose)

    # Export if requested
    if export and output_file:
        if export.lower() == "json":
            import json
            with open(output_file, "w") as f:
                json.dump(result.model_dump(), f, indent=2, default=str)
            console.print(f"\n[green]Results exported to {output_file}[/green]")
        else:
            console.print(f"[red]Unsupported export format:[/red] {export}")


@portfolio_app.command("analysis-history")
def portfolio_analysis_history(
    name: str = typer.Argument(..., help="Portfolio name"),
) -> None:
    """
    Show analysis history for a portfolio.

    Examples:
        consilium portfolio analysis-history "Tech Holdings"
    """
    async def fetch_history():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                return None, []

            history = await repo.get_portfolio_analysis_history(portfolio.id)
            return portfolio, history
        finally:
            await close_pool()

    try:
        portfolio, history = asyncio.run(fetch_history())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(1)

    from consilium.output.portfolio_formatter import PortfolioFormatter
    formatter = PortfolioFormatter(console)
    formatter.display_analysis_history(history)


@portfolio_app.command("sell")
def portfolio_sell(
    name: str = typer.Argument(..., help="Portfolio name"),
    ticker: str = typer.Argument(..., help="Ticker symbol"),
    quantity: float = typer.Argument(..., help="Number of shares to sell"),
    price: float = typer.Argument(..., help="Sell price per share"),
    date: Optional[str] = typer.Option(
        None,
        "--date",
        "-d",
        help="Sell date (YYYY-MM-DD), defaults to today",
    ),
    fees: float = typer.Option(
        0.0,
        "--fees",
        "-f",
        help="Transaction fees",
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        "-n",
        help="Notes for this sale",
    ),
) -> None:
    """
    Sell (reduce) a position in a portfolio.

    Records a SELL transaction with realized P&L calculation using
    weighted average cost basis.

    Examples:
        consilium portfolio sell "Tech Holdings" AAPL 50 180.00
        consilium portfolio sell "Tech Holdings" NVDA 25 520.00 --date 2024-06-15
        consilium portfolio sell "Tech Holdings" MSFT 10 400.00 --fees 9.99 -n "Taking profits"
    """
    from datetime import date as dt_date
    from decimal import Decimal

    # Parse date
    if date:
        try:
            from datetime import datetime
            sell_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid date format. Use YYYY-MM-DD.")
            raise typer.Exit(1)
    else:
        sell_date = dt_date.today()

    async def record_sale():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository
        from consilium.core.portfolio_models import TransactionType

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            # Check if portfolio exists
            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                console.print(f"[red]Error:[/red] Portfolio '{name}' not found.")
                return None

            # Check if we have enough shares to sell
            positions = await repo.get_positions(portfolio.id)
            ticker_upper = ticker.upper()
            position = next((p for p in positions if p.ticker == ticker_upper), None)

            if not position:
                console.print(f"[red]Error:[/red] No position in {ticker_upper} found.")
                return None

            if position.quantity < Decimal(str(quantity)):
                console.print(
                    f"[red]Error:[/red] Cannot sell {quantity} shares. "
                    f"Only {position.quantity} shares available."
                )
                return None

            # Calculate realized P&L
            realized_pnl, holding_days, cost_basis = await repo.calculate_realized_pnl_for_sell(
                portfolio_id=portfolio.id,
                ticker=ticker_upper,
                sell_quantity=Decimal(str(quantity)),
                sell_price=Decimal(str(price)),
                sell_date=sell_date,
            )

            # Record the sell transaction
            transaction_id = await repo.add_transaction(
                portfolio_id=portfolio.id,
                ticker=ticker_upper,
                transaction_type=TransactionType.SELL,
                quantity=Decimal(str(quantity)),
                price=Decimal(str(price)),
                transaction_date=sell_date,
                fees=Decimal(str(fees)),
                notes=notes,
                realized_pnl=realized_pnl,
                holding_period_days=holding_days,
                cost_basis_used=cost_basis,
            )

            # Update the position (reduce quantity)
            new_quantity = position.quantity - Decimal(str(quantity))
            if new_quantity <= 0:
                # Remove position entirely
                await repo.delete_position(position.id)
            else:
                # Update position quantity
                await repo.update_position_quantity(position.id, new_quantity)

            return {
                "portfolio": portfolio,
                "transaction_id": transaction_id,
                "realized_pnl": realized_pnl,
                "holding_days": holding_days,
                "cost_basis": cost_basis,
                "remaining_shares": new_quantity if new_quantity > 0 else Decimal("0"),
            }
        finally:
            await close_pool()

    try:
        result = asyncio.run(record_sale())
    except Exception as e:
        console.print(f"[red]Error recording sale:[/red] {e}")
        raise typer.Exit(1)

    if result:
        total_proceeds = quantity * price
        pnl = result["realized_pnl"]
        pnl_color = "green" if pnl >= 0 else "red"
        pnl_sign = "+" if pnl >= 0 else ""

        console.print(
            f"[red]SOLD from '{name}':[/red] {quantity} {ticker.upper()} @ ${price:.2f} = ${total_proceeds:,.2f}"
        )
        console.print(f"[dim]Sale date: {sell_date}[/dim]")
        console.print(f"[dim]Cost basis used: ${result['cost_basis']:.2f}[/dim]")
        console.print(
            f"[{pnl_color}]Realized P&L: {pnl_sign}${pnl:,.2f}[/{pnl_color}] "
            f"(held {result['holding_days']} days)"
        )
        if result["remaining_shares"] > 0:
            console.print(f"[dim]Remaining position: {result['remaining_shares']} shares[/dim]")
        else:
            console.print(f"[dim]Position fully closed[/dim]")


@portfolio_app.command("transactions")
def portfolio_transactions(
    name: str = typer.Argument(..., help="Portfolio name"),
    ticker: Optional[str] = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Filter by ticker symbol",
    ),
    tx_type: Optional[str] = typer.Option(
        None,
        "--type",
        help="Filter by transaction type (BUY or SELL)",
    ),
    limit: int = typer.Option(50, "--limit", "-l", help="Number of transactions to show"),
) -> None:
    """
    Show transaction history for a portfolio.

    Examples:
        consilium portfolio transactions "Tech Holdings"
        consilium portfolio transactions "Tech Holdings" --ticker AAPL
        consilium portfolio transactions "Tech Holdings" --type sell
        consilium portfolio transactions "Tech Holdings" --limit 100
    """
    from consilium.core.portfolio_models import TransactionType

    # Parse transaction type filter
    type_filter = None
    if tx_type:
        tx_type_upper = tx_type.upper()
        if tx_type_upper == "BUY":
            type_filter = TransactionType.BUY
        elif tx_type_upper == "SELL":
            type_filter = TransactionType.SELL
        else:
            console.print(f"[red]Error:[/red] Invalid type. Use BUY or SELL.")
            raise typer.Exit(1)

    async def fetch_transactions():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                return None, []

            transactions = await repo.get_transactions(
                portfolio_id=portfolio.id,
                ticker=ticker.upper() if ticker else None,
                limit=limit,
            )
            return portfolio, transactions
        finally:
            await close_pool()

    try:
        portfolio, transactions = asyncio.run(fetch_transactions())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(1)

    from consilium.output.portfolio_formatter import PortfolioFormatter
    formatter = PortfolioFormatter(console)
    formatter.display_transactions(transactions, ticker_filter=ticker, type_filter=type_filter)


@portfolio_app.command("pnl")
def portfolio_pnl(
    name: str = typer.Argument(..., help="Portfolio name"),
    ticker: Optional[str] = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Filter by ticker symbol",
    ),
) -> None:
    """
    Show realized P&L summary for a portfolio.

    Displays realized gains/losses from closed positions, broken down by ticker.

    Examples:
        consilium portfolio pnl "Tech Holdings"
        consilium portfolio pnl "Tech Holdings" --ticker AAPL
    """
    from decimal import Decimal

    async def fetch_pnl():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.portfolio_repository import PortfolioRepository

        try:
            pool = await get_pool()
            repo = PortfolioRepository(pool)

            portfolio = await repo.get_portfolio_by_name(name)
            if not portfolio:
                return None, {}, Decimal("0"), Decimal("0")

            # Get P&L by ticker
            pnl_by_ticker = await repo.get_realized_pnl_by_ticker(
                portfolio_id=portfolio.id,
                ticker=ticker.upper() if ticker else None,
            )

            # Calculate totals
            total_realized = sum(
                data.get("realized_pnl", Decimal("0"))
                for data in pnl_by_ticker.values()
            )
            total_fees = sum(
                data.get("total_fees", Decimal("0"))
                for data in pnl_by_ticker.values()
            )

            return portfolio, pnl_by_ticker, total_realized, total_fees
        finally:
            await close_pool()

    try:
        portfolio, pnl_by_ticker, total_realized, total_fees = asyncio.run(fetch_pnl())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not portfolio:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(1)

    from consilium.output.portfolio_formatter import PortfolioFormatter
    formatter = PortfolioFormatter(console)
    formatter.display_pnl_summary(portfolio, pnl_by_ticker, total_realized, total_fees)


# ============== History Commands ==============


@history_app.command("list")
def history_list(
    ticker: Optional[str] = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Filter by ticker symbol",
    ),
    days: Optional[int] = typer.Option(
        None,
        "--days",
        "-d",
        help="Filter by number of days",
    ),
    signal: Optional[str] = typer.Option(
        None,
        "--signal",
        "-s",
        help="Filter by signal (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL)",
    ),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of entries to show"),
) -> None:
    """
    Show recent analysis history.

    Examples:
        consilium history list
        consilium history list --ticker AAPL --limit 20
        consilium history list --days 7 --signal BUY
    """
    async def fetch_history():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import HistoryRepository

        try:
            pool = await get_pool()
            repo = HistoryRepository(pool)
            return await repo.get_history(
                ticker=ticker,
                days=days,
                limit=limit,
                signal=signal,
            )
        finally:
            await close_pool()

    try:
        results = asyncio.run(fetch_history())
    except Exception as e:
        console.print(f"[red]Error fetching history:[/red] {e}")
        raise typer.Exit(1)

    if not results:
        console.print("[yellow]No analysis history found.[/yellow]")
        return

    table = Table(title="Analysis History")
    table.add_column("Request ID", style="cyan", max_width=10)
    table.add_column("Tickers", style="white")
    table.add_column("Signal", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Confidence", style="magenta")
    table.add_column("Date", style="dim")

    signal_colors = {
        "STRONG_BUY": "bold green",
        "BUY": "green",
        "HOLD": "yellow",
        "SELL": "red",
        "STRONG_SELL": "bold red",
    }

    for r in results:
        tickers_str = ", ".join(r.get("tickers", [])) if r.get("tickers") else "N/A"
        sig = r.get("consensus_signal", "N/A")
        sig_style = signal_colors.get(sig, "white")
        score = f"{r.get('consensus_score', 0):.1f}" if r.get("consensus_score") is not None else "N/A"
        conf = r.get("consensus_confidence", "N/A")
        date_str = r.get("created_at").strftime("%Y-%m-%d %H:%M") if r.get("created_at") else "N/A"

        table.add_row(
            r.get("request_id", "")[:8] + "...",
            tickers_str[:20] + ("..." if len(tickers_str) > 20 else ""),
            f"[{sig_style}]{sig}[/{sig_style}]",
            score,
            conf,
            date_str,
        )

    console.print(table)
    console.print(f"\n[dim]Use 'consilium history show <request_id>' for details[/dim]")


@history_app.command("show")
def history_show(
    request_id: str = typer.Argument(..., help="Analysis request ID (or prefix)"),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show full agent responses",
    ),
) -> None:
    """
    Show details of a specific analysis.

    Examples:
        consilium history show abc123
        consilium history show abc123 --verbose
    """
    async def fetch_analysis():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import HistoryRepository

        try:
            pool = await get_pool()
            repo = HistoryRepository(pool)
            return await repo.get_analysis_by_id(request_id)
        finally:
            await close_pool()

    try:
        result = asyncio.run(fetch_analysis())
    except Exception as e:
        console.print(f"[red]Error fetching analysis:[/red] {e}")
        raise typer.Exit(1)

    if not result:
        console.print(f"[red]Analysis not found:[/red] {request_id}")
        raise typer.Exit(1)

    # Display summary panel
    sig = result.get("consensus_signal", "N/A")
    signal_colors = {
        "STRONG_BUY": "bold green",
        "BUY": "green",
        "HOLD": "yellow",
        "SELL": "red",
        "STRONG_SELL": "bold red",
    }
    sig_style = signal_colors.get(sig, "white")

    tickers = result.get("tickers", [])
    panel_content = (
        f"[bold]Tickers:[/bold] {', '.join(tickers)}\n"
        f"[bold]Signal:[/bold] [{sig_style}]{sig}[/{sig_style}]\n"
        f"[bold]Score:[/bold] {result.get('consensus_score', 'N/A')}\n"
        f"[bold]Confidence:[/bold] {result.get('consensus_confidence', 'N/A')}\n"
        f"[bold]Agents Used:[/bold] {result.get('agents_used', 'N/A')}\n"
        f"[bold]Execution Time:[/bold] {result.get('execution_time_ms', 0) / 1000:.2f}s\n"
        f"[bold]Date:[/bold] {result.get('created_at', 'N/A')}"
    )

    console.print(Panel(panel_content, title=f"Analysis: {request_id}", border_style="blue"))

    # Show detailed results if verbose
    if verbose and result.get("results_json"):
        results_data = result["results_json"]
        if results_data.get("results"):
            for consensus in results_data["results"]:
                console.print(f"\n[bold cyan]Ticker: {consensus.get('ticker', 'N/A')}[/bold cyan]")

                # Agent responses table
                if consensus.get("agent_responses"):
                    table = Table(title="Agent Responses")
                    table.add_column("Agent", style="cyan")
                    table.add_column("Signal", style="bold")
                    table.add_column("Confidence")
                    table.add_column("Target", justify="right")

                    for resp in consensus["agent_responses"]:
                        ag_sig = resp.get("signal", "N/A")
                        ag_style = signal_colors.get(ag_sig, "white")
                        target = f"${resp.get('target_price', 0):.2f}" if resp.get("target_price") else "-"

                        table.add_row(
                            resp.get("agent_id", "N/A"),
                            f"[{ag_style}]{ag_sig}[/{ag_style}]",
                            resp.get("confidence", "N/A"),
                            target,
                        )

                    console.print(table)


@history_app.command("export")
def history_export(
    output_file: str = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output file path",
    ),
    format: str = typer.Option(
        "csv",
        "--format",
        "-f",
        help="Export format: csv, json",
    ),
    days: Optional[int] = typer.Option(
        30,
        "--days",
        "-d",
        help="Number of days to export",
    ),
    ticker: Optional[str] = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Filter by ticker",
    ),
) -> None:
    """
    Export analysis history to file.

    Examples:
        consilium history export -o history.csv --days 30
        consilium history export -o history.json -f json --ticker AAPL
    """
    import json
    import csv

    async def fetch_history():
        from consilium.db.connection import get_pool, close_pool
        from consilium.db.repository import HistoryRepository

        try:
            pool = await get_pool()
            repo = HistoryRepository(pool)
            return await repo.get_history(ticker=ticker, days=days, limit=1000)
        finally:
            await close_pool()

    try:
        results = asyncio.run(fetch_history())
    except Exception as e:
        console.print(f"[red]Error fetching history:[/red] {e}")
        raise typer.Exit(1)

    if not results:
        console.print("[yellow]No history to export.[/yellow]")
        return

    if format.lower() == "json":
        # Convert datetime objects to strings
        for r in results:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
    elif format.lower() == "csv":
        fieldnames = [
            "request_id", "tickers", "consensus_signal", "consensus_score",
            "consensus_confidence", "agents_used", "execution_time_ms", "created_at"
        ]
        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                row = {k: v for k, v in r.items() if k in fieldnames}
                if row.get("tickers"):
                    row["tickers"] = ",".join(row["tickers"])
                writer.writerow(row)
    else:
        console.print(f"[red]Unsupported format:[/red] {format}")
        raise typer.Exit(1)

    console.print(f"[green]Exported {len(results)} records to {output_file}[/green]")


# ============== Database Commands ==============


@db_app.command("init")
def db_init(
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Drop all tables and recreate (DANGEROUS)",
    ),
) -> None:
    """
    Initialize database schema (create tables).

    Examples:
        consilium db init
        consilium db init --reset  # WARNING: Drops all data!
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    settings = get_settings()

    console.print(
        Panel(
            f"[bold]Host:[/bold] {settings.database.host}:{settings.database.port}\n"
            f"[bold]Database:[/bold] {settings.database.name}\n"
            f"[bold]User:[/bold] {settings.database.user}",
            title="Database Configuration",
            border_style="blue",
        )
    )

    if reset:
        confirm = typer.confirm(
            "[red]WARNING:[/red] This will DROP ALL TABLES and data. Continue?",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(0)

    async def run_init():
        from consilium.db.connection import DatabasePool
        from consilium.db.migrations import run_migrations, reset_database

        pool = DatabasePool(settings)
        await pool.connect()

        try:
            if reset:
                console.print("[yellow]Resetting database...[/yellow]")
                await reset_database(pool)
                console.print("[green]Database reset complete![/green]")
            else:
                applied = await run_migrations(pool)
                if applied:
                    console.print(f"[green]Applied migrations:[/green] {applied}")
                else:
                    console.print("[green]Database already up to date.[/green]")
        finally:
            await pool.disconnect()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Connecting to database...", total=None)
        try:
            asyncio.run(run_init())
        except Exception as e:
            console.print(f"\n[red]Database error:[/red] {e}")
            console.print(
                "\n[dim]Make sure MySQL is running and the database exists.[/dim]"
            )
            raise typer.Exit(1)


@db_app.command("status")
def db_status() -> None:
    """Check database connection and schema status."""
    settings = get_settings()

    async def check_db():
        from consilium.db.connection import DatabasePool
        from consilium.db.migrations import get_current_version, SCHEMA_VERSION

        pool = DatabasePool(settings)
        await pool.connect()

        try:
            # Check connection
            result = await pool.fetch_one("SELECT 1 as ok")
            connected = result and result.get("ok") == 1

            # Check schema version
            current_version = await get_current_version(pool)

            return connected, current_version
        finally:
            await pool.disconnect()

    table = Table(title="Database Status")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="white")

    try:
        connected, version = asyncio.run(check_db())
        from consilium.db.migrations import SCHEMA_VERSION

        table.add_row("Connection", "[green]Connected[/green]")
        table.add_row(
            "Schema Version",
            f"{version}/{SCHEMA_VERSION}" + (
                " [green](up to date)[/green]" if version >= SCHEMA_VERSION
                else " [yellow](needs migration)[/yellow]"
            ),
        )
    except Exception as e:
        table.add_row("Connection", f"[red]Failed: {e}[/red]")

    console.print(table)


# ============== Status Command ==============


@app.command()
def status() -> None:
    """Show configuration status and connectivity."""
    settings = get_settings()

    table = Table(title="Configuration Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Status", style="green")

    # API Key
    api_status = "OK" if settings.is_configured else "Missing"
    api_style = "green" if settings.is_configured else "red"
    table.add_row(
        "Anthropic API Key",
        "***configured***" if settings.is_configured else "Not set",
        f"[{api_style}]{api_status}[/{api_style}]",
    )

    # Model
    table.add_row("Claude Model", settings.model, "[green]OK[/green]")

    # Database
    table.add_row(
        "Database",
        f"{settings.database.host}:{settings.database.port}/{settings.database.name}",
        "[yellow]Not tested[/yellow]",
    )

    # Cache TTLs
    table.add_row(
        "Cache TTL (price)",
        f"{settings.cache.price_ttl} min",
        "[green]OK[/green]",
    )

    console.print(table)


# ============================================================================
# ASK COMMANDS - Q&A with investor agents
# ============================================================================


@app.command("ask")
def ask_question(
    question: str = typer.Argument(
        ...,
        help="Your question for the investor(s)",
    ),
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        "-a",
        help="Single agent ID (e.g., 'buffett')",
    ),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        help="Multiple agent IDs, comma-separated (e.g., 'buffett,munger,graham')",
    ),
    ticker: Optional[str] = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Explicit ticker(s) to fetch data for (comma-separated)",
    ),
    no_data: bool = typer.Option(
        False,
        "--no-data",
        help="Skip fetching market data (for philosophical questions)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip cost confirmation",
    ),
) -> None:
    """
    Ask investor agents a direct question.

    Examples:
        consilium ask "O que você acha de TSLA?" --agent buffett
        consilium ask "Vale investir em AAPL?" --agents buffett,munger,graham
        consilium ask "Qual sua visão para NVDA em 2 anos?" --agent lynch
        consilium ask "Devo comprar IBIT e shortar MSTR?" --agents buffett,simons
        consilium ask "O que você pensa sobre IA?" --agent buffett --no-data
    """

    settings = get_settings()

    if not settings.is_configured:
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY not configured.")
        console.print("Set it in your environment or .env file.")
        raise typer.Exit(1)

    # Parse agents
    agent_ids: list[str] = []
    if agent:
        agent_ids = [agent.strip().lower()]
    elif agents:
        agent_ids = [a.strip().lower() for a in agents.split(",")]
    else:
        console.print("[red]Error:[/red] Please specify --agent or --agents")
        console.print("Example: consilium ask \"Your question\" --agent buffett")
        raise typer.Exit(1)

    # Parse explicit tickers
    explicit_tickers: list[str] | None = None
    if ticker:
        explicit_tickers = [t.strip().upper() for t in ticker.split(",")]

    include_market_data = not no_data

    # Cost estimation and confirmation
    if not yes:
        from consilium.llm.cost_estimator import CostEstimator
        from consilium.output.cost_display import CostDisplay

        estimator = CostEstimator(settings.model)
        estimate = estimator.estimate_ask(
            num_agents=len(agent_ids),
            include_market_data=include_market_data,
        )

        cost_display = CostDisplay(console)
        cost_display.display_ask_estimate(
            estimate,
            num_agents=len(agent_ids),
            include_market_data=include_market_data,
        )

        if not typer.confirm("\nProceed with question?"):
            console.print("[yellow]Question cancelled.[/yellow]")
            raise typer.Exit(0)

    # Run the question
    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Preparing question...", total=None)

        async def run_ask():
            from consilium.db.connection import close_pool
            from consilium.ask.orchestrator import AskOrchestrator

            try:
                orchestrator = AskOrchestrator(
                    settings=settings,
                    progress_callback=lambda msg: progress.update(task, description=msg),
                )
                return await orchestrator.ask(
                    question=question,
                    agent_ids=agent_ids,
                    explicit_tickers=explicit_tickers,
                    include_market_data=include_market_data,
                )
            finally:
                await close_pool()

        try:
            result = asyncio.run(run_ask())
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
            raise typer.Exit(1)

    # Display result
    from consilium.output.ask_formatter import AskFormatter

    console.print()
    formatter = AskFormatter(console)
    if len(result.responses) == 1:
        formatter.display_single_response(result)
    else:
        formatter.display_comparison(result)


@app.command("ask-history")
def ask_history(
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        "-a",
        help="Filter by agent ID",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Number of records to show",
    ),
) -> None:
    """View history of previous questions."""
    settings = get_settings()

    async def fetch_history():
        from consilium.db.connection import close_pool
        from consilium.db.ask_repository import AskRepository

        try:
            repo = AskRepository(settings)
            return await repo.list_questions(
                agent_id=agent,
                limit=limit,
            )
        finally:
            await close_pool()

    try:
        questions = asyncio.run(fetch_history())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    from consilium.output.ask_formatter import AskFormatter

    formatter = AskFormatter(console)
    title = f"Q&A History (agent: {agent})" if agent else "Q&A History"
    formatter.display_history(questions, title=title)


@app.command("ask-show")
def ask_show(
    question_id: int = typer.Argument(
        ...,
        help="Question ID to show",
    ),
) -> None:
    """Show details of a specific question and its responses."""
    settings = get_settings()

    async def fetch_question():
        from consilium.db.connection import close_pool
        from consilium.db.ask_repository import AskRepository

        try:
            repo = AskRepository(settings)
            return await repo.get_question(question_id)
        finally:
            await close_pool()

    try:
        result = asyncio.run(fetch_question())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not result:
        console.print(f"[yellow]Question {question_id} not found.[/yellow]")
        raise typer.Exit(1)

    from consilium.output.ask_formatter import AskFormatter

    formatter = AskFormatter(console)
    formatter.display_question_detail(result)


# ============================================================================
# Backtest Commands
# ============================================================================


@app.command("backtest")
def backtest_command(
    ticker: str = typer.Argument(
        ...,
        help="Ticker symbol to backtest (e.g., 'AAPL')",
    ),
    start: Optional[str] = typer.Option(
        None,
        "--start",
        help="Start date (YYYY-MM-DD)",
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        help="End date (YYYY-MM-DD)",
    ),
    period: Optional[str] = typer.Option(
        None,
        "--period",
        "-p",
        help="Period shorthand: 1y, 2y, 6m, 3m (alternative to --start/--end)",
    ),
    benchmark: str = typer.Option(
        "SPY",
        "--benchmark",
        "-b",
        help="Benchmark ticker for comparison",
    ),
    strategy: str = typer.Option(
        "signal",
        "--strategy",
        "-s",
        help="Strategy type: 'signal' or 'threshold'",
    ),
    threshold: Optional[float] = typer.Option(
        None,
        "--threshold",
        "-t",
        help="Score threshold for threshold strategy (e.g., 50)",
    ),
    capital: float = typer.Option(
        100000.0,
        "--capital",
        "-c",
        help="Initial capital for backtest",
    ),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        "-a",
        help="Specific agents to use (comma-separated IDs)",
    ),
    slippage: float = typer.Option(
        0.1,
        "--slippage",
        help="Slippage percentage for trades",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output including all trades",
    ),
    export: Optional[str] = typer.Option(
        None,
        "--export",
        "-e",
        help="Export format: json",
    ),
    output_file: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path for export",
    ),
) -> None:
    """
    Run a backtest on historical data.

    Tests agent recommendations against historical prices and calculates
    performance metrics.

    Examples:
        consilium backtest AAPL --period 2y
        consilium backtest NVDA --start 2023-01-01 --end 2025-01-01
        consilium backtest TSLA --strategy threshold --threshold 50
        consilium backtest AAPL --benchmark QQQ --capital 50000
        consilium backtest MSFT --agents buffett,simons --verbose
    """
    from datetime import date, datetime
    from decimal import Decimal

    from rich.progress import Progress, SpinnerColumn, TextColumn

    from consilium.backtesting import BacktestEngine, BacktestStrategyType, parse_period
    from consilium.output.backtest_formatter import BacktestFormatter
    from consilium.db.connection import close_pool

    settings = get_settings()

    # Validate date parameters
    if not period and not (start and end):
        # Default to 1 year
        period = "1y"

    # Parse dates
    if period:
        try:
            start_date, end_date = parse_period(period)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    else:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            console.print("[red]Error:[/red] Invalid date format. Use YYYY-MM-DD.")
            raise typer.Exit(1)

    # Parse strategy
    try:
        strategy_type = BacktestStrategyType(strategy.lower())
    except ValueError:
        console.print("[red]Error:[/red] Strategy must be 'signal' or 'threshold'.")
        raise typer.Exit(1)

    # Validate threshold for threshold strategy
    if strategy_type == BacktestStrategyType.THRESHOLD and threshold is None:
        threshold = 50.0
        console.print(f"[dim]Using default threshold: {threshold}[/dim]")

    # Parse agent filter
    agent_filter = [a.strip().lower() for a in agents.split(",")] if agents else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running backtest...", total=None)

        async def run_backtest():
            try:
                engine = BacktestEngine(
                    settings=settings,
                    progress_callback=lambda msg: progress.update(task, description=msg),
                )
                return await engine.run(
                    ticker=ticker.upper(),
                    start_date=start_date,
                    end_date=end_date,
                    benchmark=benchmark.upper(),
                    strategy=strategy_type,
                    threshold=Decimal(str(threshold)) if threshold else None,
                    initial_capital=Decimal(str(capital)),
                    agent_filter=agent_filter,
                    slippage_pct=Decimal(str(slippage)),
                )
            finally:
                await close_pool()

        try:
            result = asyncio.run(run_backtest())
        except Exception as e:
            console.print(f"\n[red]Error during backtest:[/red] {e}")
            raise typer.Exit(1)

    # Display result
    formatter = BacktestFormatter(console)
    formatter.display_result(result, show_trades=verbose, max_trades=20)

    # Export if requested
    if export and export.lower() == "json":
        import json
        output_path = output_file or f"backtest_{ticker}_{start_date}_{end_date}.json"
        with open(output_path, "w") as f:
            # Convert to serializable dict
            data = {
                "ticker": result.ticker,
                "benchmark": result.benchmark,
                "start_date": str(result.start_date),
                "end_date": str(result.end_date),
                "strategy_type": result.strategy_type.value,
                "initial_capital": float(result.initial_capital),
                "final_value": float(result.final_value),
                "metrics": {
                    "total_return_pct": float(result.metrics.total_return_pct),
                    "cagr": float(result.metrics.cagr),
                    "sharpe_ratio": float(result.metrics.sharpe_ratio),
                    "sortino_ratio": float(result.metrics.sortino_ratio),
                    "max_drawdown": float(result.metrics.max_drawdown),
                    "win_rate": float(result.metrics.win_rate),
                    "profit_factor": float(result.metrics.profit_factor),
                    "alpha": float(result.metrics.alpha),
                    "beta": float(result.metrics.beta),
                },
                "trades": [
                    {
                        "date": str(t.trade_date),
                        "type": t.trade_type.value,
                        "price": float(t.price),
                        "quantity": float(t.quantity),
                        "realized_pnl": float(t.realized_pnl) if t.realized_pnl else None,
                    }
                    for t in result.trades
                ],
            }
            json.dump(data, f, indent=2)
        console.print(f"\n[green]Results exported to:[/green] {output_path}")


@app.command("backtest-history")
def backtest_history_command(
    ticker: Optional[str] = typer.Option(
        None,
        "--ticker",
        "-t",
        help="Filter by ticker",
    ),
    strategy: Optional[str] = typer.Option(
        None,
        "--strategy",
        "-s",
        help="Filter by strategy type",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Maximum number of results",
    ),
) -> None:
    """
    View history of previous backtests.

    Examples:
        consilium backtest-history
        consilium backtest-history --ticker AAPL
        consilium backtest-history --strategy threshold --limit 10
    """
    from consilium.backtesting import BacktestRepository, BacktestStrategyType
    from consilium.output.backtest_formatter import BacktestFormatter
    from consilium.db.connection import close_pool

    settings = get_settings()

    # Parse strategy filter
    strategy_filter = None
    if strategy:
        try:
            strategy_filter = BacktestStrategyType(strategy.lower())
        except ValueError:
            console.print("[red]Error:[/red] Strategy must be 'signal' or 'threshold'.")
            raise typer.Exit(1)

    async def fetch_history():
        try:
            repo = BacktestRepository(settings)
            return await repo.list_backtests(
                ticker=ticker.upper() if ticker else None,
                strategy=strategy_filter,
                limit=limit,
            )
        finally:
            await close_pool()

    try:
        backtests = asyncio.run(fetch_history())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    formatter = BacktestFormatter(console)
    formatter.display_history(backtests)


@app.command("backtest-show")
def backtest_show_command(
    backtest_id: int = typer.Argument(
        ...,
        help="Backtest ID to show",
    ),
    all_trades: bool = typer.Option(
        False,
        "--all-trades",
        help="Show all trades (not just first/last 20)",
    ),
) -> None:
    """
    Show details of a specific backtest.

    Examples:
        consilium backtest-show 1
        consilium backtest-show 5 --all-trades
    """
    from consilium.backtesting import BacktestRepository
    from consilium.output.backtest_formatter import BacktestFormatter
    from consilium.db.connection import close_pool

    settings = get_settings()

    async def fetch_backtest():
        try:
            repo = BacktestRepository(settings)
            return await repo.get_backtest(backtest_id)
        finally:
            await close_pool()

    try:
        result = asyncio.run(fetch_backtest())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not result:
        console.print(f"[yellow]Backtest with ID {backtest_id} not found.[/yellow]")
        raise typer.Exit(1)

    formatter = BacktestFormatter(console)
    max_trades = 1000 if all_trades else 20
    formatter.display_result(result, show_trades=True, max_trades=max_trades)


@app.command("backtest-generate")
def backtest_generate_command(
    ticker: str = typer.Argument(
        ...,
        help="Ticker symbol to generate signals for (e.g., 'AAPL')",
    ),
    start: Optional[str] = typer.Option(
        None,
        "--start",
        "-s",
        help="Start date (YYYY-MM-DD)",
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        "-e",
        help="End date (YYYY-MM-DD)",
    ),
    period: Optional[str] = typer.Option(
        "2y",
        "--period",
        "-p",
        help="Period (e.g., '1y', '2y', '6m') - used if start/end not provided",
    ),
    granularity: str = typer.Option(
        "monthly",
        "--granularity",
        "-g",
        help="Signal frequency: monthly, quarterly, semiannual, annual",
    ),
    agents: Optional[str] = typer.Option(
        None,
        "--agents",
        "-a",
        help="Comma-separated list of agent IDs (e.g., 'buffett,simons')",
    ),
    no_specialists: bool = typer.Option(
        False,
        "--no-specialists",
        help="Skip specialist analysis (faster, cheaper)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip cost confirmation prompt",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed progress",
    ),
) -> None:
    """
    Generate retroactive trading signals using real AI agents.

    This command runs actual analysis on historical data points to generate
    meaningful signals for backtesting. Uses point-in-time data to avoid
    look-ahead bias.

    WARNING: This can be expensive as it runs real API calls for each signal date.

    Examples:
        consilium backtest-generate AAPL --period 2y --granularity monthly
        consilium backtest-generate NVDA --start 2023-01-01 --end 2025-01-01 -g quarterly
        consilium backtest-generate TSLA --agents buffett,lynch --no-specialists
        consilium backtest-generate MSFT --period 1y -g monthly --yes
    """
    from datetime import date, datetime
    from decimal import Decimal

    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from consilium.backtesting import parse_period
    from consilium.backtesting.models import SignalGranularity
    from consilium.backtesting.signal_generator import RetroactiveSignalGenerator
    from consilium.db.connection import close_pool

    settings = get_settings()
    ticker = ticker.upper().strip()

    # Parse dates
    if start and end:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            console.print("[red]Error:[/red] Invalid date format. Use YYYY-MM-DD.")
            raise typer.Exit(1)
    elif period:
        start_date, end_date = parse_period(period)
    else:
        console.print("[red]Error:[/red] Provide either --start/--end or --period.")
        raise typer.Exit(1)

    # Parse granularity
    try:
        signal_granularity = SignalGranularity(granularity.lower())
    except ValueError:
        console.print(
            f"[red]Error:[/red] Invalid granularity '{granularity}'. "
            "Use: monthly, quarterly, semiannual, annual"
        )
        raise typer.Exit(1)

    # Parse agent filter
    agent_filter = None
    if agents:
        agent_filter = [a.strip().lower() for a in agents.split(",")]

    include_specialists = not no_specialists

    # Create generator and calculate schedule
    generator = RetroactiveSignalGenerator(settings=settings)
    dates = generator.generate_date_schedule(start_date, end_date, signal_granularity)
    num_dates = len(dates)

    # Count agents
    from consilium.agents.registry import AgentRegistry
    registry = AgentRegistry(settings)
    investors = registry.get_investors(agent_filter)
    specialists = registry.get_specialists() if include_specialists else []
    num_investors = len(investors)
    num_specialists = len(specialists)

    # Estimate cost
    estimated_cost = generator.estimate_cost(
        num_dates=num_dates,
        num_investors=num_investors,
        num_specialists=num_specialists,
        include_specialists=include_specialists,
    )

    # Display cost estimation
    console.print()
    cost_table = Table(title="Retroactive Signal Generation Plan", show_header=False)
    cost_table.add_column("Field", style="cyan")
    cost_table.add_column("Value", style="white")

    cost_table.add_row("Ticker", ticker)
    cost_table.add_row("Period", f"{start_date} to {end_date}")
    cost_table.add_row("Granularity", signal_granularity.value)
    cost_table.add_row("Signal Dates", str(num_dates))
    cost_table.add_row("Investors", f"{num_investors} agents")
    cost_table.add_row("Specialists", f"{num_specialists} agents" if include_specialists else "Skipped")
    cost_table.add_row("", "")
    cost_table.add_row("Estimated Cost", f"[bold yellow]${estimated_cost:.2f}[/bold yellow]")

    console.print(cost_table)
    console.print()

    # Confirm with user
    if not yes:
        console.print(
            Panel(
                "[yellow]This will run real AI analysis for each signal date.\n"
                "API costs will be incurred.[/yellow]",
                title="⚠️  Cost Warning",
            )
        )
        if not typer.confirm("Do you want to proceed?"):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    # Run signal generation
    progress_messages = []

    def progress_callback(msg: str) -> None:
        if verbose:
            console.print(f"  [dim]{msg}[/dim]")
        progress_messages.append(msg)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Generating signals for {ticker}...", total=None)

        async def run_generation():
            try:
                gen = RetroactiveSignalGenerator(
                    settings=settings,
                    progress_callback=progress_callback,
                )
                return await gen.generate_signals(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    granularity=signal_granularity,
                    agent_filter=agent_filter,
                    include_specialists=include_specialists,
                )
            finally:
                await close_pool()

        try:
            signals = asyncio.run(run_generation())
        except Exception as e:
            console.print(f"\n[red]Error during signal generation:[/red] {e}")
            raise typer.Exit(1)

    # Display results
    console.print()
    if signals:
        results_table = Table(title=f"Generated Signals for {ticker}")
        results_table.add_column("Date", style="cyan")
        results_table.add_column("Signal", style="white")
        results_table.add_column("Score", justify="right")
        results_table.add_column("Source", style="dim")

        for signal in signals:
            signal_color = {
                "STRONG_BUY": "bold green",
                "BUY": "green",
                "HOLD": "yellow",
                "SELL": "red",
                "STRONG_SELL": "bold red",
            }.get(signal.signal.value, "white")

            results_table.add_row(
                str(signal.date),
                f"[{signal_color}]{signal.signal.value}[/{signal_color}]",
                f"{signal.weighted_score:.1f}",
                signal.source,
            )

        console.print(results_table)
        console.print(f"\n[green]Successfully generated {len(signals)} signals.[/green]")
        console.print("[dim]Signals have been saved to history for use in backtesting.[/dim]")
    else:
        console.print("[yellow]No signals were generated.[/yellow]")


if __name__ == "__main__":
    app()
