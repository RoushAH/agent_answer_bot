# Board Game Cafe Assistant

An AI-powered assistant that answers natural language questions about a board game cafe's data using Claude 3 Haiku via AWS Bedrock.

## Features

- **Natural Language Queries** - Ask questions in plain English about inventory, sales, rentals, and orders
- **Interactive TUI** - Beautiful terminal interface built with Rich
- **Agentic Architecture** - Claude autonomously decides when to query the database or perform calculations
- **Safe Execution** - SQL restricted to SELECT queries; calculator uses AST parsing for security

## Quick Start

### Prerequisites

- Python 3.10+
- AWS credentials configured with Bedrock access

### Installation

```bash
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

Or ask a single question directly:

```bash
python main.py "What are our top selling games?"
```

## How It Works

The assistant uses an agentic loop where Claude:

1. Receives your question
2. Decides which tool to use (SQL query or calculator)
3. Executes the tool and observes the result
4. Repeats until it can provide a final answer

### Available Tools

| Tool | Description |
|------|-------------|
| `query` | Execute SELECT queries against the SQLite database |
| `calculate` | Evaluate math expressions (+, -, *, /, parentheses) |

## Database Schema

The sample database includes:

- **board_games** - Inventory with retail prices, wholesale costs, categories, and stock levels
- **game_sales** - Sales history with dates, quantities, and channels (online/in-store)
- **table_rentals** - Table booking records with duration and hourly rates
- **food_bev_items** - Menu items with sell prices and costs for profit calculations
- **food_bev_orders** - Food and beverage orders linked to table rentals
- **operating_expenses** - Monthly expenses (rent, utilities, labor, insurance, marketing)

## Example Questions

- "How many board games do we have in stock?"
- "What are our top 3 selling games?"
- "What was our profit margin on game sales?"
- "What were our total operating expenses in January?"
- "Which food items have the highest profit margin?"
- "What's our net profit after all expenses?"

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help message |
| `/tables` | Show database schema |
| `/sample` | Show sample questions |
| `/clear` | Clear the screen |
| `/quit` | Exit the assistant |

## Project Structure

```
.
├── main.py          # Interactive TUI entry point
├── agent.py         # Core agent loop with Bedrock integration
├── database.py      # SQLite database setup and queries
├── calculator.py    # Safe math expression evaluator
├── schema.py        # JSON action validation
└── requirements.txt # Dependencies (boto3, rich)
```

## License

MIT
