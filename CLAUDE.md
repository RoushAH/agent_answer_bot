# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Board Game Cafe Assistant - An AI-powered assistant that answers natural language questions about a board game cafe's data. Supports multiple LLM backends (Ollama local models, AWS Bedrock).

## Build & Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run interactive TUI
python main.py

# Run with a single question
python main.py "What are our top selling games?"

# Run HTTP API server
uvicorn api:app --reload

# Initialize/reset the database
python database.py

# Test the calculator
python calculator.py

# Test the agent directly
python agent.py

# Run benchmark suite
python benchmark.py

# Run single benchmark case
python benchmark.py count_games
```

**Prerequisites:** Python 3.10+, plus either AWS credentials (for Bedrock) or Ollama running locally.

## Architecture

### Agentic Loop Pattern

The core architecture is an agentic loop in `agent.py` where Claude autonomously decides which tool to use:

1. User asks a question (with optional `conversation_history` for follow-up context)
2. Claude receives the question + system prompt with tool definitions
3. Claude responds with exactly one JSON action: `query`, `calculate`, `whatif`, or `answer`
4. If not `answer`, the tool executes and result is fed back to Claude
5. Loop repeats until Claude provides a final `answer`

**Agent constants** in `agent.py`:
- `MAX_TURNS = 10` - Maximum conversation turns before forcing an answer
- `MAX_RETRIES = 3` - Retries for invalid JSON responses before failing

### Tool System

Three tools available to the agent (defined in `schema.py:VALID_ACTIONS`):

- **query** (`database.py`): Executes SQL SELECT queries against SQLite. Restricted to SELECT only for safety.
- **calculate** (`calculator.py`): Evaluates math expressions and statistics. Uses AST parsing for security. Supports +, -, *, /, parentheses, and statistical functions: mean(), median(), mode(), stdev(), range().
- **whatif** (`whatif.py`): Scenario analysis for business planning:
  - `price_change` - Impact of price adjustments (target: "games", "food", "tables", or item name)
  - `volume_change` - Impact of selling more/fewer units of a specific item
  - `expense_change` - Impact of operating cost changes (category: "all", "rent", "labor", "utilities", etc.)
  - `hours_change` - Impact of additional/fewer table rental hours

### Key Files

- `main.py` - Interactive TUI using Rich, handles commands (`/help`, `/tables`, `/quit`)
- `api.py` - FastAPI HTTP server for embedding in other systems
- `agent.py` - Core agent loop, LLM API calls, retry logic for invalid JSON
- `schema.py` - JSON action validation with robustness: handles markdown code blocks, fixes unescaped newlines, extracts first valid JSON object from mixed responses
- `database.py` - SQLite setup, schema, seed data for cafe inventory/sales/rentals
- `calculator.py` - Safe math evaluator using Python AST
- `whatif.py` - Scenario analysis engine for business projections
- `search.py` - Semantic search using ChromaDB (not currently enabled in agent)
- `benchmark.py` - LLM evaluation suite with 13 test cases across 7 categories

### Database Schema

Six tables: `board_games`, `game_sales`, `table_rentals`, `food_bev_items`, `food_bev_orders`, `operating_expenses`. Run `/tables` in the TUI or see `database.py:get_schema()` for full schema.

### LLM Backend Configuration

Configurable at the top of `agent.py`. Change `BACKEND` to switch providers:

- **`ollama`** (default): Local Ollama instance. Default model: `ministral-3:8b` (97.6% benchmark score, ~92s/query).
- **`bedrock`**: AWS Bedrock with Claude 3 Haiku. Requires AWS credentials.

### Benchmarking

Run `python benchmark.py` to evaluate model performance. The benchmark suite tests 13 cases across 7 categories (simple queries, multi-step reasoning, calculations, comparisons, what-if scenarios, follow-ups, edge cases).

Top performing local models (tested March 2026):
| Model | Score | Avg Time |
|-------|-------|----------|
| ministral-3:8b | 97.6% | 92s |
| qwen3.5:4b-fast | 97.6% | 130s |
| gemma3:4b | 89.8% | 110s |
