"""
main.py
SmartDine AI — CLI entry point.

Usage:
    python main.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text

# ---------------------------------------------------------------------------
# Bootstrap: make sure the project root is on sys.path so `src.*` imports work
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.menu_loader import MenuLoader
from src.rag_engine import RAGEngine
from src.order_manager import OrderManager
from src.ai_agent import SmartDineAgent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MENU_PATH = PROJECT_ROOT / "data" / "menu.xlsx"
CHROMA_DIR = str(PROJECT_ROOT / "chroma_db")
ENV_PATH = PROJECT_ROOT / ".env"

console = Console()

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

BANNER = r"""
  ____                      _   ____  _
 / ___| _ __ ___   __ _ _ __| |_|  _ \(_)_ __   ___
 \___ \| '_ ` _ \ / _` | '__| __| | | | | '_ \ / _ \
  ___) | | | | | | (_| | |  | |_| |_| | | | | |  __/
 |____/|_| |_| |_|\__,_|_|   \__|____/|_|_| |_|\___|

        A I   R e s t a u r a n t   O r d e r i n g
"""


def show_welcome() -> None:
    """Display the welcome banner."""
    console.print(
        Panel(
            Text(BANNER, style="bold cyan", justify="center"),
            title="[bold yellow]Welcome[/bold yellow]",
            subtitle="[dim]Powered by Claude AI + RAG[/dim]",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )
    console.print(
        "[dim]Type your order in plain English.  "
        "Special commands: [bold]menu[/bold] | [bold]order[/bold] | [bold]clear[/bold] | [bold]quit[/bold][/dim]\n"
    )


def show_categories(categories: list[str]) -> None:
    """Display available menu categories in a table."""
    table = Table(
        title="[bold]Available Menu Categories[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="bright_blue",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Category", style="bold white")

    for i, cat in enumerate(categories, start=1):
        table.add_row(str(i), cat)

    console.print(table)
    console.print()


def show_order_summary(agent: SmartDineAgent) -> None:
    """Pretty-print the current order."""
    summary = agent.order_manager.get_order_summary()
    if not summary["items"]:
        console.print("[yellow]Your order is currently empty.[/yellow]\n")
        return

    table = Table(
        title="[bold]Your Current Order[/bold]",
        show_header=True,
        header_style="bold magenta",
        border_style="magenta",
    )
    table.add_column("Item", style="white")
    table.add_column("Qty", justify="center", width=5)
    table.add_column("Price", justify="right", width=8)
    table.add_column("Subtotal", justify="right", width=10)
    table.add_column("Notes", style="dim")

    for item in summary["items"]:
        table.add_row(
            item["name"],
            str(item["qty"]),
            f"${item['price']:.2f}",
            f"${item['subtotal']:.2f}",
            item.get("special_request", ""),
        )

    console.print(table)
    console.print(f"  Subtotal : [white]${summary['subtotal']:.2f}[/white]")
    console.print(f"  Tax (10%): [white]${summary['tax']:.2f}[/white]")
    console.print(f"  [bold green]Total    : ${summary['total']:.2f}[/bold green]\n")


def show_receipt(receipt_text: str) -> None:
    """Display the receipt inside a Rich panel."""
    console.print(
        Panel(
            Text(receipt_text, style="green"),
            title="[bold yellow]Your Receipt[/bold yellow]",
            border_style="green",
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def ensure_menu_exists() -> None:
    """Run setup_menu.py logic to create data/menu.xlsx if missing."""
    if not MENU_PATH.exists():
        console.print("[yellow]Menu file not found — creating it now...[/yellow]")
        # Import and call directly rather than subprocess
        sys.path.insert(0, str(PROJECT_ROOT))
        from setup_menu import create_menu_excel
        create_menu_excel(str(MENU_PATH))
        console.print("[green]Menu file created.[/green]\n")


def index_menu_with_spinner(rag: RAGEngine) -> None:
    """Index the menu while showing a loading spinner."""
    with Live(
        Spinner("dots", text="[cyan]Indexing menu into vector store...[/cyan]"),
        console=console,
        refresh_per_second=10,
    ):
        rag.index_menu()
    console.print("[green]Menu indexed and ready.[/green]\n")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # 1. Load environment variables
    load_dotenv(dotenv_path=ENV_PATH)

    # 2. Welcome banner
    show_welcome()

    # 3. Ensure menu spreadsheet exists
    ensure_menu_exists()

    # 4. Load menu data
    try:
        loader = MenuLoader(str(MENU_PATH))
        menu_items = loader.load()
        categories = loader.get_categories()
    except (FileNotFoundError, RuntimeError) as exc:
        console.print(f"[bold red]Error loading menu: {exc}[/bold red]")
        sys.exit(1)

    console.print(f"[dim]Loaded [bold]{len(menu_items)}[/bold] menu items.[/dim]")
    show_categories(categories)

    # 5. Initialise RAG engine and index
    rag = RAGEngine(menu_items, persist_dir=CHROMA_DIR)
    index_menu_with_spinner(rag)

    # 6. Initialise order manager and AI agent
    order_mgr = OrderManager()
    try:
        agent = SmartDineAgent(rag_engine=rag, order_manager=order_mgr)
    except EnvironmentError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        sys.exit(1)

    console.print("[bold green]SmartDine AI is ready to take your order![/bold green]")
    console.print("[dim]─" * 60 + "[/dim]\n")

    # 7. Main chat loop
    try:
        while True:
            try:
                user_input = console.input("[bold cyan]\\[You]: [/bold cyan]").strip()
            except EOFError:
                break

            if not user_input:
                continue

            lower = user_input.lower()

            # --- Special commands ---
            if lower in ("quit", "exit", "bye", "q"):
                break

            if lower == "clear":
                agent.reset()
                console.print("[yellow]Order cleared and conversation reset.[/yellow]\n")
                continue

            if lower == "menu":
                show_categories(categories)
                continue

            if lower == "order":
                show_order_summary(agent)
                continue

            # --- AI response ---
            with console.status("[cyan]SmartDine AI is thinking...[/cyan]", spinner="dots"):
                response = agent.chat(user_input)

            console.print(f"\n[bold green]\\[SmartDine AI]:[/bold green] {response}\n")

            # Detect receipt in response and display it in a panel
            if "RECEIPT" in response.upper():
                # Extract the ASCII receipt block if present
                receipt_start = response.find("=" * 10)
                if receipt_start != -1:
                    receipt_text = response[receipt_start:]
                    show_receipt(receipt_text)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")

    # 8. Show order summary on exit if cart is not empty
    if not order_mgr.is_empty():
        console.print("\n[yellow]You have items in your cart:[/yellow]")
        show_order_summary(agent)
        console.print("[dim]Your order was not placed.  Come back anytime![/dim]")

    console.print(
        Panel(
            "[bold cyan]Thank you for visiting SmartDine AI![/bold cyan]\n"
            "[dim]We hope to serve you again soon.[/dim]",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )


if __name__ == "__main__":
    main()
