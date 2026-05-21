#!/usr/bin/env python3
"""
MyGameShelf — Personal Game Collection & Progress Tracker
Entry point: run with `python main.py` from the mygameshelf/ folder.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm

from db.connection import initialize_schema
from db.models import (
    add_game, list_games, get_game, update_game_status, rate_game, delete_game,
    log_session, get_sessions,
    add_to_wishlist, list_wishlist, remove_from_wishlist,
    get_stats,
)
from ui.display import (
    console, print_games_table, print_wishlist_table,
    print_sessions_table, print_stats,
)

STATUSES   = ["Backlog", "Playing", "Completed", "Abandoned"]
PRIORITIES = ["High", "Medium", "Low"]


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def pick_game(prompt_text="Enter Game ID") -> int | None:
    """Show game list and ask user to pick an ID."""
    games = list_games()
    if not games:
        console.print("[yellow]No games in your collection yet.[/yellow]\n")
        return None
    print_games_table(games)
    return IntPrompt.ask(f"\n[cyan]{prompt_text}[/cyan]")


def pick_from_list(options: list[str], label: str) -> str:
    for i, opt in enumerate(options, 1):
        console.print(f"  [dim]{i}.[/dim] {opt}")
    while True:
        choice = IntPrompt.ask(f"[cyan]{label}[/cyan]")
        if 1 <= choice <= len(options):
            return options[choice - 1]
        console.print("[red]Invalid choice, try again.[/red]")


# ─── GAME MENU ────────────────────────────────────────────────────────────────

def menu_games():
    while True:
        console.print(Panel(
            "[1] ➕  Add a game\n"
            "[2] 📄  List all games\n"
            "[3] 🔄  Update game status\n"
            "[4] ⭐  Rate & review a game\n"
            "[5] 🗑   Delete a game\n"
            "[6] ⏱   View play sessions\n"
            "[0] ◀   Back",
            title="🎮 Game Collection", border_style="cyan"
        ))
        choice = Prompt.ask("[bold]Choose[/bold]", choices=["0","1","2","3","4","5","6"])

        if choice == "1":
            title    = Prompt.ask("[cyan]Title[/cyan]")
            platform = Prompt.ask("[cyan]Platform[/cyan]", default="")
            genre    = Prompt.ask("[cyan]Genre[/cyan]", default="")
            year_str = Prompt.ask("[cyan]Release year[/cyan]", default="")
            year     = int(year_str) if year_str.isdigit() else None
            console.print("Status:")
            status = pick_from_list(STATUSES, "Status")
            notes  = Prompt.ask("[cyan]Notes (optional)[/cyan]", default="")
            gid = add_game(title, platform, genre, year, status, notes)
            console.print(f"\n[green]✅ Game added with ID {gid}![/green]\n")

        elif choice == "2":
            console.print("\nFilter by status? Leave blank for all.")
            console.print("  [dim]Options: Backlog | Playing | Completed | Abandoned | (blank)[/dim]")
            sf = Prompt.ask("[cyan]Status filter[/cyan]", default="")
            games = list_games(sf if sf else None)
            print_games_table(games)

        elif choice == "3":
            gid = pick_game("Game ID to update")
            if gid is None:
                continue
            console.print("New status:")
            new_status = pick_from_list(STATUSES, "New status")
            update_game_status(gid, new_status)
            console.print(f"[green]✅ Status updated to {new_status}.[/green]\n")

        elif choice == "4":
            gid = pick_game("Game ID to rate")
            if gid is None:
                continue
            rating = FloatPrompt.ask("[cyan]Rating (0-10)[/cyan]")
            notes  = Prompt.ask("[cyan]Review notes (optional)[/cyan]", default="")
            rate_game(gid, rating, notes)
            console.print("[green]✅ Rating saved.[/green]\n")

        elif choice == "5":
            gid = pick_game("Game ID to delete")
            if gid is None:
                continue
            if Confirm.ask(f"[red]Delete game ID {gid}? This also removes sessions.[/red]"):
                delete_game(gid)
                console.print("[green]✅ Game deleted.[/green]\n")

        elif choice == "6":
            gid = pick_game("Game ID to view sessions")
            if gid is None:
                continue
            game = get_game(gid)
            if game:
                sessions = get_sessions(gid)
                print_sessions_table(sessions, game[1])

        elif choice == "0":
            break


# ─── SESSION MENU ─────────────────────────────────────────────────────────────

def menu_log_session():
    gid = pick_game("Game ID to log session for")
    if gid is None:
        return
    game = get_game(gid)
    if not game:
        console.print("[red]Game not found.[/red]\n")
        return
    console.print(f"\nLogging session for [bold]{game[1]}[/bold]")
    hours = FloatPrompt.ask("[cyan]Hours played[/cyan]")
    notes = Prompt.ask("[cyan]Session notes (optional)[/cyan]", default="")
    log_session(gid, hours, notes)
    console.print(f"[green]✅ Logged {hours}h for {game[1]}.[/green]\n")


# ─── WISHLIST MENU ────────────────────────────────────────────────────────────

def menu_wishlist():
    while True:
        console.print(Panel(
            "[1] ➕  Add to wishlist\n"
            "[2] 📄  View wishlist\n"
            "[3] 🗑   Remove from wishlist\n"
            "[0] ◀   Back",
            title="📋 Wishlist", border_style="red"
        ))
        choice = Prompt.ask("[bold]Choose[/bold]", choices=["0","1","2","3"])

        if choice == "1":
            title    = Prompt.ask("[cyan]Game title[/cyan]")
            platform = Prompt.ask("[cyan]Platform[/cyan]", default="")
            console.print("Priority:")
            priority = pick_from_list(PRIORITIES, "Priority")
            notes    = Prompt.ask("[cyan]Notes (optional)[/cyan]", default="")
            add_to_wishlist(title, platform, priority, notes)
            console.print("[green]✅ Added to wishlist.[/green]\n")

        elif choice == "2":
            items = list_wishlist()
            print_wishlist_table(items)

        elif choice == "3":
            items = list_wishlist()
            if not items:
                continue
            print_wishlist_table(items)
            wid = IntPrompt.ask("\n[cyan]Wishlist ID to remove[/cyan]")
            if Confirm.ask(f"[red]Remove item {wid}?[/red]"):
                remove_from_wishlist(wid)
                console.print("[green]✅ Removed from wishlist.[/green]\n")

        elif choice == "0":
            break


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold magenta]MyGameShelf[/bold magenta] 🎮\n"
        "[dim]Your personal game collection tracker[/dim]",
        border_style="magenta"
    ))

    try:
        initialize_schema()
    except Exception as e:
        console.print(f"[bold red]❌ Could not connect to the database:[/bold red] {e}")
        console.print("[dim]Make sure PostgreSQL is running and your .env file is configured.[/dim]")
        return

    while True:
        console.print(Panel(
            "[1] 🎮  Game Collection\n"
            "[2] ⏱   Log a Play Session\n"
            "[3] 📋  Wishlist\n"
            "[4] 📊  Stats Dashboard\n"
            "[0] 🚪  Exit",
            title="Main Menu", border_style="magenta"
        ))
        choice = Prompt.ask("[bold]Choose[/bold]", choices=["0","1","2","3","4"])

        if   choice == "1": menu_games()
        elif choice == "2": menu_log_session()
        elif choice == "3": menu_wishlist()
        elif choice == "4":
            stats = get_stats()
            print_stats(stats)
        elif choice == "0":
            console.print("\n[bold magenta]See you next session! 🎮[/bold magenta]\n")
            break


if __name__ == "__main__":
    main()
