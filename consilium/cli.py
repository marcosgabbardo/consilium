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
history_app = typer.Typer(help="Analysis history commands")
db_app = typer.Typer(help="Database management commands")

app.add_typer(agents_app, name="agents")
app.add_typer(watchlist_app, name="watchlist")
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
) -> None:
    """
    Analyze stocks using the multi-agent consensus system.

    Examples:
        consilium analyze AAPL
        consilium analyze "AAPL,NVDA,MSFT" --verbose
        consilium analyze TSLA --agents buffett,munger,graham
        consilium analyze AMZN --export json -o analysis.json
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
) -> None:
    """
    Analyze all tickers in a watchlist.

    Examples:
        consilium watchlist analyze tech-giants
        consilium watchlist analyze tech-giants --verbose
        consilium watchlist analyze tech-giants --agents buffett,munger
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


if __name__ == "__main__":
    app()
