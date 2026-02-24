# Board Game Cafe Assistant

An AI-powered assistant that answers natural language questions about a board game cafe's data. Supports multiple LLM backends (AWS Bedrock, Ollama).

## Features

- **Natural Language Queries** - Ask questions in plain English about inventory, sales, rentals, and orders
- **Interactive TUI** - Beautiful terminal interface built with Rich
- **HTTP API** - Embed in other systems via REST endpoint
- **Agentic Architecture** - LLM autonomously decides when to query, calculate, search, or run scenarios
- **Conversation History** - Follow-up questions maintain context (last 4 exchanges)
- **Configurable Backend** - Switch between AWS Bedrock (Claude) and local Ollama models
- **Safe Execution** - SQL restricted to SELECT; calculator uses AST parsing; all tools whitelisted

## Quick Start

### Prerequisites

- Python 3.10+
- AWS credentials (for Bedrock) OR Ollama running locally

### Installation

```bash
pip install -r requirements.txt
```

### Run

**Interactive TUI:**
```bash
python main.py
```

**Single question:**
```bash
python main.py "What are our top selling games?"
```

**HTTP API:**
```bash
uvicorn api:app --reload
# Then POST to http://localhost:8000/ask
```

## Configuring the LLM Backend

Edit the top of `agent.py`:

```python
BACKEND = "bedrock"  # or "ollama"

# Bedrock settings
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Ollama settings
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3"  # or mistral, mixtral, phi3, etc.
```

## How It Works

The assistant uses an agentic loop:

1. Receives your question (with conversation history for context)
2. Decides which tool to use
3. Executes the tool and observes the result
4. Repeats until it can provide a final answer (max 10 turns)

### Available Tools

| Tool | Description |
|------|-------------|
| `query` | Execute SELECT queries against the SQLite database |
| `calculate` | Math expressions and statistics (mean, median, mode, stdev, range) |
| `search` | Semantic search for games by description/vibe using ChromaDB |
| `whatif` | Scenario analysis ("What if prices increased 10%?") |

### What-If Scenarios

The `whatif` tool supports business projections:

- **price_change** - Impact of price adjustments on revenue/profit
- **volume_change** - Impact of selling more/fewer units
- **expense_change** - Impact of operating cost changes
- **hours_change** - Impact of additional table rental hours

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
- "What was our average daily revenue?"
- "Find me cooperative games for families"
- "What if we raised game prices by 15%?"
- "What would profit look like if we sold 50 more coffees?"

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help message |
| `/tables` | Show database schema |
| `/sample` | Show sample questions |
| `/clear` | Clear the screen |
| `/history` | Clear conversation history |
| `/quit` | Exit the assistant |

## API Usage

```bash
# Ask a question
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are our top selling games?"}'

# With conversation history
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Why is that?",
    "conversation_history": [
      {"role": "user", "content": "What are our top selling games?"},
      {"role": "assistant", "content": "The top selling games are..."}
    ]
  }'
```

Interactive API docs available at `http://localhost:8000/docs`

## Project Structure

```
.
├── main.py          # Interactive TUI entry point
├── api.py           # FastAPI HTTP server
├── agent.py         # Core agent loop (configurable LLM backend)
├── database.py      # SQLite database setup and queries
├── calculator.py    # Safe math/statistics evaluator (AST-based)
├── schema.py        # JSON action validation
├── search.py        # Semantic search with ChromaDB
├── whatif.py        # Scenario analysis engine
└── requirements.txt # Dependencies
```

## Security

- **SQL Injection Prevention** - Only SELECT queries allowed, validated before execution
- **Safe Calculator** - AST parsing whitelist, no `eval()`
- **Tool Whitelist** - Only explicitly defined actions can execute
- **Turn Limits** - Agent can't loop indefinitely (max 10 turns)

## License

MIT
