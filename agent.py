"""Core agent loop with configurable LLM backend."""

import json
from datetime import date
from typing import Callable, Optional

from database import query_db, get_schema
from calculator import calculate
from schema import validate_action

# =============================================================================
# LLM CONFIGURATION
# =============================================================================
# Change BACKEND to switch between providers. Options: "bedrock", "ollama"

BACKEND = "bedrock"

# AWS Bedrock settings
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Ollama settings (local)
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3"  # Options: llama3, mistral, mixtral, phi3, codellama, etc.

# =============================================================================

MAX_RETRIES = 3
MAX_TURNS = 10

# Callback type for progress updates
ProgressCallback = Callable[[str, str, Optional[str]], None]


def get_system_prompt() -> str:
    """Build the system prompt with tool descriptions and schema."""
    schema = get_schema()
    return f"""You are a helpful assistant for a board game cafe/shop. Answer questions using ONLY the data in the database.

TOOLS:
1. query - Execute SQL SELECT queries
2. calculate - Evaluate math expressions and statistics (supports +, -, *, /, mean, median, mode, stdev, range)
3. search - Semantic search for board games (finds similar matches, not exact)
4. whatif - Scenario analysis ("what if prices increased 10%?", "what if we sold 20 more Catans?")

RESPONSE FORMAT:
You must respond with EXACTLY ONE JSON object per message. No other text, no explanations.

{{"action": "query", "sql": "SELECT ..."}}
{{"action": "calculate", "expression": "123.45 + 67.89"}}
{{"action": "search", "query": "cooperative family games", "n": 5}}
{{"action": "whatif", "scenario_type": "price_change", "params": {{"target": "games", "change_percent": 10}}}}
{{"action": "answer", "text": "Your final answer here"}}

ANSWER FORMAT:
The "answer" text MUST be natural language for a human reader, NOT raw JSON or data.
- WRONG: {{"action": "answer", "text": "{{\\"avg\\": 50.99, \\"median\\": 44.99}}"}}
- RIGHT: {{"action": "answer", "text": "The average game price is $50.99, with a median of $44.99."}}

WHEN TO USE SEARCH VS QUERY:
- Use "search" when looking for games by description/vibe (e.g., "games about building", "fun party games")
- Use "query" when you need exact data (e.g., prices, stock levels, sales figures)

WHAT-IF SCENARIOS (use "whatif" action):
- scenario_type: "price_change" - params: {{"target": "games"|"food"|"tables"|item_name, "change_percent": number}}
- scenario_type: "volume_change" - params: {{"target": item_name, "quantity_change": number}}
- scenario_type: "expense_change" - params: {{"category": "all"|"rent"|"labor"|etc, "change_percent": number, "month": "2026-01"|"january"|optional}}
- scenario_type: "hours_change" - params: {{"hours_change": number}}
Example: "What if game prices increased 15%?" → {{"action": "whatif", "scenario_type": "price_change", "params": {{"target": "games", "change_percent": 15}}}}

ONE action at a time. You will see the result, then can do the next action.

CRITICAL RULES:
1. ONLY use data that exists in the schema below. If asked about data we don't have (e.g., labour costs, employee data, expenses), say "We don't have that data in our system."
2. NEVER guess or make up numbers. Every number in your answer must come from a query result.
3. Final answers MUST be conversational natural language, NOT raw data or JSON. Explain the results clearly.
4. For multi-step math:
   - FIRST: use query to get the numbers you need
   - THEN: use calculate with those ACTUAL numbers (e.g., "553.19 - 92")
   - The calculate tool accepts: numbers, +, -, *, /, parentheses
   - Statistical functions: mean(), median(), mode(), stdev(), range()
   - Example: {{"action": "calculate", "expression": "mean(49.99, 39.99, 44.99)"}}
   - WRONG: {{"action": "calculate", "expression": "SELECT ... - 92"}}
   - RIGHT: {{"action": "calculate", "expression": "553.19 - 92"}}

DATA WE HAVE:
- Board game inventory (names, prices, wholesale costs, stock levels)
- Game sales (what we sold, when, at what price, online vs in-store)
- Table rentals (what we CHARGE customers for table time - this is REVENUE)
- Food & beverage items (menu items with sell prices AND costs)
- Food & beverage orders (what customers ordered during rentals)
- Operating expenses (rent, utilities, labor, insurance, marketing, supplies by month)

PROFIT CALCULATIONS:
- Game profit = (unit_price - board_games.cost) * quantity
- Food/bev profit = (unit_price - food_bev_items.cost) * quantity (join on item_name)
- Table rental revenue is pure profit (no direct costs)
- Net profit = total revenue - total costs - operating expenses

INTERPRETING COMMON TERMS (use averages, not specific dates):
- "daily" = average per day (total / number of distinct days), NOT "today"
- "weekly" = average per week or total for a week period
- "monthly" = average per month or total for a specific month
- "typical" or "usual" = use mean or median of historical data
- "how much do we make" = use historical averages, not a single day
When asked about rates (daily/weekly/monthly), calculate from ALL available data unless a specific date range is mentioned.

Today's date is {date.today().isoformat()}

{schema}"""


def call_bedrock(messages: list[dict], system: str) -> str:
    """Call Claude via AWS Bedrock and return the response text."""
    import boto3

    client = boto3.client("bedrock-runtime")

    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": system,
            "messages": messages,
        }),
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def call_ollama(messages: list[dict], system: str) -> str:
    """Call a local Ollama model and return the response text."""
    import requests

    # Ollama uses OpenAI-style messages with system as first message
    ollama_messages = [{"role": "system", "content": system}] + messages

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()

    return response.json()["message"]["content"]


def call_llm(messages: list[dict], system: str) -> str:
    """Call the configured LLM backend."""
    if BACKEND == "bedrock":
        return call_bedrock(messages, system)
    elif BACKEND == "ollama":
        return call_ollama(messages, system)
    else:
        raise ValueError(f"Unknown backend: {BACKEND}")


def execute_action(action: dict) -> tuple[str, bool]:
    """
    Execute a validated action and return the result.

    Returns:
        Tuple of (result_string, is_error)
    """
    action_type = action["action"]

    if action_type == "query":
        try:
            results = query_db(action["sql"])
            if not results:
                return "Query returned no results.", False
            return json.dumps(results, indent=2), False
        except Exception as e:
            return f"Query error: {e}", True

    elif action_type == "calculate":
        try:
            result = calculate(action["expression"])
            return f"Result: {result}", False
        except ValueError as e:
            return f"Calculation error: {e}. Remember: calculator only supports numbers and +, -, *, /, parentheses. Try a different approach.", True

    elif action_type == "search":
        try:
            from search import search_games
            n = action.get("n", 5)
            results = search_games(action["query"], n=n)
            if not results:
                return "No matching games found.", False
            return json.dumps(results, indent=2), False
        except Exception as e:
            return f"Search error: {e}", True

    elif action_type == "whatif":
        try:
            from whatif import run_scenario
            result = run_scenario(action["scenario_type"], **action["params"])
            if "error" in result:
                return f"Scenario error: {result['error']}", True
            return json.dumps(result, indent=2), False
        except Exception as e:
            return f"What-if error: {e}", True

    return "Unknown action type.", True


def run_agent(
    user_query: str,
    on_progress: Optional[ProgressCallback] = None,
    debug: bool = False,
    conversation_history: Optional[list[dict]] = None,
) -> str:
    """
    Run the agent loop to answer a user query.

    Args:
        user_query: The user's question
        on_progress: Callback for progress updates (event, tool, detail)
        debug: If True, print raw model responses
        conversation_history: Optional list of previous Q&A pairs for context

    Returns:
        The final answer string
    """
    def emit(event: str, tool: str = "", detail: str = ""):
        if on_progress:
            on_progress(event, tool, detail)

    system = get_system_prompt()
    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_query})

    for turn in range(MAX_TURNS):
        # Call Claude with retry logic for invalid JSON
        response_text = None
        cleaned_response = None
        action = None

        for attempt in range(MAX_RETRIES):
            emit("thinking", "", f"Turn {turn + 1}")
            response_text = call_llm(messages, system)

            if debug:
                print(f"[DEBUG] Turn {turn+1}, Attempt {attempt+1}:")
                print(f"[DEBUG] Response: {response_text!r}")

            action, cleaned_response = validate_action(response_text)

            if action is not None:
                break

            # Invalid JSON - add error message and retry
            emit("retry", "", f"Attempt {attempt + 1} failed, retrying...")
            if attempt < MAX_RETRIES - 1:
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": "Invalid format. Respond with EXACTLY ONE JSON object, nothing else. Example: {\"action\": \"query\", \"sql\": \"SELECT ...\"}"
                })

        if action is None:
            return "Error: Agent failed to produce valid JSON after multiple attempts."

        action_type = action["action"]

        # Check if this is the final answer
        if action_type == "answer":
            emit("answer", "", "")
            return action["text"]

        # Show what tool is being used
        if action_type == "query":
            sql = action["sql"].strip().replace("\n", " ")
            # Truncate long SQL for display
            if len(sql) > 80:
                sql = sql[:77] + "..."
            emit("tool_call", "query", sql)
        elif action_type == "calculate":
            emit("tool_call", "calculate", action["expression"])
        elif action_type == "search":
            emit("tool_call", "search", action["query"])
        elif action_type == "whatif":
            emit("tool_call", "whatif", f"{action['scenario_type']}: {action['params']}")

        # Execute the action and get result
        result, is_error = execute_action(action)

        # Show result summary
        if is_error:
            # Truncate error message for display
            error_display = result.split(".")[0] if "." in result else result
            if len(error_display) > 60:
                error_display = error_display[:57] + "..."
            emit("error", action_type, error_display)
        elif action_type == "query":
            try:
                data = json.loads(result)
                emit("result", "query", f"{len(data)} row(s) returned")
            except (json.JSONDecodeError, TypeError):
                emit("result", "query", result[:50])
        elif action_type == "search":
            try:
                data = json.loads(result)
                emit("result", "search", f"{len(data)} game(s) found")
            except (json.JSONDecodeError, TypeError):
                emit("result", "search", result[:50])
        elif action_type == "whatif":
            try:
                data = json.loads(result)
                scenario = data.get("scenario", "Scenario calculated")
                emit("result", "whatif", scenario[:60])
            except (json.JSONDecodeError, TypeError):
                emit("result", "whatif", result[:50])
        elif action_type == "calculate":
            emit("result", "calculate", result)

        # Add assistant response and tool result to conversation
        # Use cleaned_response (single JSON object) to prevent model from "remembering" predictions
        messages.append({"role": "assistant", "content": cleaned_response})
        messages.append({"role": "user", "content": f"Tool result:\n{result}"})

    return "Error: Agent reached maximum turns without providing an answer."


if __name__ == "__main__":
    # Quick test with progress output
    from database import init_db
    init_db()

    def print_progress(event, tool, detail):
        print(f"  [{event}] {tool}: {detail}" if tool else f"  [{event}] {detail}")

    answer = run_agent(
        "How many board games do we have in total?",
        on_progress=print_progress
    )
    print(f"Answer: {answer}")
