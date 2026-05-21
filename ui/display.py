from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

STATUS_STYLES = {
    "Backlog":   ("🟡", "yellow"),
    "Playing":   ("🟢", "green"),
    "Completed": ("✅", "bright_green"),
    "Abandoned": ("🔴", "red"),
}

PRIORITY_STYLES = {
    "High":   ("🔥", "red"),
    "Medium": ("⚡", "yellow"),
    "Low":    ("💤", "dim"),
}


def print_games_table(games, title="🎮 Game Collection"):
    if not games:
        console.print(f"[dim]No games found.[/dim]\n")
        return

    table = Table(title=title, box=box.ROUNDED, header_style="bold magenta", show_lines=True)
    table.add_column("ID",       style="dim",     width=4,  justify="right")
    table.add_column("Title",    style="bold",    width=28)
    table.add_column("Platform", style="cyan",    width=12)
    table.add_column("Genre",    style="blue",    width=14)
    table.add_column("Year",     style="dim",     width=6,  justify="center")
    table.add_column("Status",                    width=14)
    table.add_column("Rating",                    width=8,  justify="center")
    table.add_column("Hours",    style="magenta", width=8,  justify="right")

    for row in games:
        gid, title_val, platform, genre, year, status, rating, hours = row
        icon, color = STATUS_STYLES.get(status, ("?", "white"))
        status_text = Text(f"{icon} {status}", style=color)
        rating_str = f"⭐ {rating}" if rating is not None else "—"
        table.add_row(
            str(gid),
            title_val or "—",
            platform or "—",
            genre or "—",
            str(year) if year else "—",
            status_text,
            rating_str,
            f"{hours}h",
        )
    console.print(table)


def print_wishlist_table(items):
    if not items:
        console.print("[dim]Your wishlist is empty.[/dim]\n")
        return

    table = Table(title="📋 Wishlist", box=box.ROUNDED, header_style="bold magenta", show_lines=True)
    table.add_column("ID",       style="dim",  width=4, justify="right")
    table.add_column("Title",    style="bold", width=28)
    table.add_column("Platform", style="cyan", width=14)
    table.add_column("Priority",               width=12)
    table.add_column("Notes",    style="dim",  width=30)

    for row in items:
        wid, title_val, platform, priority, notes = row
        icon, color = PRIORITY_STYLES.get(priority, ("", "white"))
        priority_text = Text(f"{icon} {priority}", style=color)
        table.add_row(
            str(wid),
            title_val,
            platform or "—",
            priority_text,
            notes or "—",
        )
    console.print(table)


def print_sessions_table(sessions, game_title):
    if not sessions:
        console.print(f"[dim]No sessions logged for {game_title}.[/dim]\n")
        return

    table = Table(title=f"⏱  Sessions — {game_title}", box=box.SIMPLE_HEAVY, header_style="bold cyan")
    table.add_column("Date",  style="dim",     width=12)
    table.add_column("Hours", style="magenta", width=8, justify="right")
    table.add_column("Notes", style="dim",     width=40)

    for date, hours, notes in sessions:
        table.add_row(str(date), f"{hours}h", notes or "—")
    console.print(table)


def print_stats(stats):
    total    = stats["total_games"]
    done     = stats["completed"]
    pct      = stats["completion_pct"]
    hours    = stats["total_hours"]
    genre    = stats["top_genre"]
    wishlist = stats["wishlist_count"]

    bar_filled = int(pct / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    content = (
        f"[bold]Total Games:[/bold]      [cyan]{total}[/cyan]\n"
        f"[bold]Completed:[/bold]        [green]{done}[/green]  /  {total}\n"
        f"[bold]Completion:[/bold]       [{bar}] [yellow]{pct}%[/yellow]\n"
        f"[bold]Total Hours:[/bold]      [magenta]{hours}h[/magenta]\n"
        f"[bold]Favourite Genre:[/bold]  [blue]{genre}[/blue]\n"
        f"[bold]Wishlist Items:[/bold]   [dim]{wishlist}[/dim]"
    )
    console.print(Panel(content, title="📊 Stats Dashboard", border_style="magenta", expand=False))
