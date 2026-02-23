"""Interactive TUI for the board game cafe assistant."""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich.spinner import Spinner
from rich.syntax import Syntax

from database import init_db, DB_PATH
from agent import run_agent

console = Console()

WELCOME = """
# Board Game Cafe Assistant

I can help you answer questions about our cafe's data:

- **Inventory** - Board games in stock, prices, categories
- **Sales** - Game sales history, revenue, top sellers
- **Table Rentals** - Bookings, revenue, popular times
- **Food & Beverage** - Order history, popular items

Just ask me anything in natural language!

*Type `/help` for commands or `/quit` to exit.*
"""

HELP_TEXT = """
## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show this help message |
| `/tables` | Show database schema |
| `/sample` | Show sample questions |
| `/clear` | Clear the screen |
| `/history` | Clear conversation history |
| `/quit` | Exit the assistant |

Or just ask a question in plain English!
"""

MAX_HISTORY_PAIRS = 4

SAMPLE_QUESTIONS = [
    "How many board games do we have in stock?",
    "What are our top 3 selling games?",
    "What was our profit margin on game sales?",
    "What were our total operating expenses in January?",
    "Which food items have the highest profit margin?",
    "What's our net profit after all expenses?",
]

# Status markers (ASCII-safe for Windows compatibility)
ICONS = {
    "thinking": ">",
    "tool_call": ">",
    "executing": ">",
    "result": "<",
    "error": "X",
    "answer": ">",
    "retry": "!",
}


class ProgressDisplay:
    """Manages the live progress display during agent execution."""

    def __init__(self):
        self.steps: list[tuple[str, str, str]] = []
        self.current_spinner: Optional[str] = None

    def add_step(self, event: str, tool: str, detail: str):
        """Add a progress step."""
        self.steps.append((event, tool, detail))
        self.current_spinner = event

    def render(self) -> Group:
        """Render the current progress state."""
        elements = []

        for i, (event, tool, detail) in enumerate(self.steps):
            icon = ICONS.get(event, ">")
            is_last = (i == len(self.steps) - 1)

            if event == "thinking":
                if is_last:
                    line = Text()
                    line.append(f"  {icon} ", style="bold")
                    line.append("Thinking", style="bold cyan")
                    line.append("...", style="dim")
                    elements.append(line)
                else:
                    elements.append(Text(f"  {icon} Thinking", style="dim"))

            elif event == "tool_call":
                line = Text()
                line.append(f"  {icon} ", style="bold")
                if tool == "query":
                    line.append("SQL Query: ", style="bold yellow")
                    line.append(detail, style="dim")
                elif tool == "calculate":
                    line.append("Calculate: ", style="bold magenta")
                    line.append(detail, style="cyan")
                elif tool == "search":
                    line.append("Search: ", style="bold blue")
                    line.append(detail, style="cyan")
                elif tool == "whatif":
                    line.append("What-If: ", style="bold green")
                    line.append(detail, style="cyan")
                elements.append(line)

            elif event == "executing":
                if is_last:
                    line = Text()
                    line.append(f"  {icon} ", style="bold")
                    line.append(f"Running {tool}", style="bold")
                    line.append("...", style="dim")
                    elements.append(line)

            elif event == "result":
                line = Text()
                line.append(f"  {icon} ", style="bold")
                line.append("Result: ", style="bold green")
                line.append(detail, style="dim")
                elements.append(line)

            elif event == "error":
                line = Text()
                line.append(f"  {icon} ", style="bold red")
                line.append("Error: ", style="bold red")
                line.append(detail, style="red")
                line.append(" (retrying...)", style="dim")
                elements.append(line)

            elif event == "retry":
                line = Text()
                line.append(f"  {icon} ", style="bold")
                line.append(detail, style="yellow")
                elements.append(line)

            elif event == "answer":
                line = Text()
                line.append(f"  {icon} ", style="bold")
                line.append("Composing answer...", style="bold green")
                elements.append(line)

        return Group(*elements)


def show_welcome():
    """Display the welcome message."""
    console.print(Markdown(WELCOME))
    console.print()


def show_help():
    """Display help information."""
    console.print(Markdown(HELP_TEXT))


def show_tables():
    """Display database schema."""
    schema = """
## Database Tables

### board_games
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Game name |
| price | REAL | Retail/selling price |
| cost | REAL | Wholesale cost |
| category | TEXT | Game category |
| in_stock | INTEGER | Quantity available |

### game_sales
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| game_id | INTEGER | FK to board_games |
| sale_date | TEXT | Date (YYYY-MM-DD) |
| quantity | INTEGER | Units sold |
| unit_price | REAL | Price per unit |
| channel | TEXT | online or in_store |

### table_rentals
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| table_number | INTEGER | Table (1-5) |
| rental_date | TEXT | Date (YYYY-MM-DD) |
| start_time | TEXT | Start (HH:MM) |
| duration_hours | REAL | Length of rental |
| hourly_rate | REAL | Rate per hour |

### food_bev_items
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| item_name | TEXT | Menu item name |
| sell_price | REAL | Customer price |
| cost | REAL | Our cost |
| category | TEXT | Beverage/Alcohol/Food |

### food_bev_orders
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| rental_id | INTEGER | FK to table_rentals |
| item_name | TEXT | Food/drink item |
| quantity | INTEGER | Units ordered |
| unit_price | REAL | Price per unit |

### operating_expenses
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| month | TEXT | YYYY-MM format |
| category | TEXT | Expense type |
| amount | REAL | Cost amount |
| description | TEXT | Details |
"""
    console.print(Markdown(schema))


def show_samples():
    """Display sample questions."""
    console.print()
    console.print("[bold]Sample questions you can ask:[/bold]")
    console.print()
    for i, q in enumerate(SAMPLE_QUESTIONS, 1):
        console.print(f"  [dim]{i}.[/dim] {q}")
    console.print()


def process_query(query: str, conversation_history: list[dict]) -> str:
    """Process a user query and display the response with live progress.

    Returns the answer text for storing in conversation history.
    """
    console.print()

    progress = ProgressDisplay()

    def on_progress(event: str, tool: str, detail: str):
        progress.add_step(event, tool, detail)
        live.update(progress.render())

    try:
        with Live(
            Text("  > Thinking...", style="dim"),
            console=console,
            refresh_per_second=10,
        ) as live:
            answer = run_agent(query, on_progress=on_progress, conversation_history=conversation_history)
    except Exception as e:
        answer = f"Sorry, I encountered an error: {e}"

    console.print()

    # Display the answer in a panel
    console.print(Panel(
        Markdown(answer),
        title="[bold green]Answer[/bold green]",
        border_style="green",
        padding=(1, 2),
    ))
    console.print()

    return answer


def main():
    """Main entry point - interactive TUI."""
    # Handle single query mode for backwards compatibility
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        if not DB_PATH.exists():
            init_db()
        console.print(f"[bold]Question:[/bold] {query}")
        process_query(query, [])
        return

    # Initialize database if needed
    if not DB_PATH.exists():
        with console.status("[bold]Initializing database...[/bold]"):
            init_db()

    # Clear screen and show welcome
    console.clear()
    show_welcome()

    # Conversation history (stores Q&A pairs for context)
    conversation_history: list[dict] = []

    # Main interaction loop
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]").strip()

            if not user_input:
                continue

            # Handle commands
            cmd = user_input.lower()

            if cmd in ("/quit", "/exit", "/q"):
                console.print()
                console.print("[dim]Thanks for visiting! Come back soon.[/dim]")
                console.print()
                break

            elif cmd in ("/help", "/h", "/?"):
                show_help()
                continue

            elif cmd == "/tables":
                show_tables()
                continue

            elif cmd in ("/sample", "/samples", "/examples"):
                show_samples()
                continue

            elif cmd == "/clear":
                console.clear()
                show_welcome()
                continue

            elif cmd == "/history":
                conversation_history.clear()
                console.print("[dim]Conversation history cleared.[/dim]")
                continue

            elif cmd.startswith("/"):
                console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
                console.print("[dim]Type /help for available commands[/dim]")
                continue

            # Process as a natural language query
            answer = process_query(user_input, conversation_history)

            # Add Q&A pair to history
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": answer})

            # Trim history to max pairs (each pair is 2 messages)
            max_messages = MAX_HISTORY_PAIRS * 2
            while len(conversation_history) > max_messages:
                conversation_history.pop(0)

        except KeyboardInterrupt:
            console.print()
            console.print("[dim]Interrupted. Type /quit to exit.[/dim]")
            continue
        except EOFError:
            console.print()
            break


if __name__ == "__main__":
    main()
