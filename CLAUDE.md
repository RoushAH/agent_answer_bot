# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Board Game Cafe Assistant - An AI-powered assistant that answers natural language questions about a board game cafe's data using Claude 3 Haiku via AWS Bedrock.

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
```

**Prerequisites:** Python 3.10+, plus either AWS credentials (for Bedrock) or Ollama running locally.

## Architecture

### Agentic Loop Pattern

The core architecture is an agentic loop in `agent.py` where Claude autonomously decides which tool to use:

1. User asks a question
2. Claude receives the question + system prompt with tool definitions
3. Claude responds with exactly one JSON action: `query`, `calculate`, or `answer`
4. If not `answer`, the tool executes and result is fed back to Claude
5. Loop repeats until Claude provides a final `answer` (max 10 turns)

### Tool System

Three tools available to the agent:

- **query** (`database.py`): Executes SQL SELECT queries against SQLite. Restricted to SELECT only for safety.
- **calculate** (`calculator.py`): Evaluates math expressions. Uses AST parsing for security - only allows numbers and basic operators (+, -, *, /, parentheses).
- **search** (`search.py`): Semantic search over board games using ChromaDB. Finds similar matches without requiring exact text.

### Key Files

- `main.py` - Interactive TUI using Rich, handles commands (`/help`, `/tables`, `/quit`)
- `api.py` - FastAPI HTTP server for embedding in other systems
- `agent.py` - Core agent loop, LLM API calls, retry logic for invalid JSON
- `schema.py` - JSON action validation, extracts first valid JSON object from response
- `database.py` - SQLite setup, schema, seed data for cafe inventory/sales/rentals
- `calculator.py` - Safe math evaluator using Python AST
- `search.py` - Semantic search using ChromaDB with local embeddings

### Database Schema

Six tables: `board_games`, `game_sales`, `table_rentals`, `food_bev_items`, `food_bev_orders`, `operating_expenses`. Run `/tables` in the TUI or see `database.py:get_schema()` for full schema.

### LLM Backend Configuration

Configurable at the top of `agent.py`. Change `BACKEND` to switch providers:

- **`bedrock`** (default): AWS Bedrock with Claude 3 Haiku. Requires AWS credentials.
- **`ollama`**: Local Ollama instance. Set `OLLAMA_MODEL` to your preferred model (llama3, mistral, mixtral, phi3, etc.).
