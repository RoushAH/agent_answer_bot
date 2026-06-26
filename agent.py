"""Core agent loop with configurable LLM backend."""

import json
import logging
import requests
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from database import query_db, get_schema
from calculator import calculate
from schema import validate_action
from cache import make_cache_key, get_llm_response, set_llm_response

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("agent")
logger.setLevel(logging.DEBUG)

# File handler - logs everything to file
file_handler = logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
))
logger.addHandler(file_handler)

# =============================================================================
# LLM CONFIGURATION
# =============================================================================
# Change BACKEND to switch between providers. Options: "bedrock", "ollama"

BACKEND = "ollama"

# AWS Bedrock settings
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Ollama settings (local)
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "ministral-3:8b"

# =============================================================================

MAX_RETRIES = 3
MAX_TURNS = 10

# Callback type for progress updates
ProgressCallback = Callable[[str, str, Optional[str]], None]


def inject_plan_into_messages(messages: list[dict], plan_text: str) -> list[dict]:
    """
    Inject a plan into the message history to maintain context.

    Adds the plan as an assistant message near the beginning of the conversation
    so the LLM has it available for all subsequent turns.

    Args:
        messages: Current message list
        plan_text: The plan text to inject (string or formatted string)

    Returns:
        Updated message list with plan injected
    """
    # Format the plan nicely
    plan_message = f"Plan recorded:\n{plan_text}"

    # Insert after the first user message (or at index 0 if no user messages yet)
    insert_pos = 0
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            insert_pos = i + 1
            break

    # Create a copy and insert the plan
    updated_messages = messages[:insert_pos] + [
        {"role": "assistant", "content": plan_message}
    ] + messages[insert_pos:]

    return updated_messages


def requires_plan(question: str) -> bool:
    """
    Detect if a question requires multi-step planning.

    Returns True if the question appears to need multiple dependent operations.
    Detection criteria:
    - Comparison language (compare, vs, versus, difference between, more than, less than, which is better)
    - Percentage or ratio questions (percentage, percent, %, ratio, proportion)
    - Ranking with context (top X by, best, worst when combined with a second dimension)
    - Compound questions (questions containing "and" paired with numeric intent words)

    Args:
        question: The user's question string

    Returns:
        Boolean indicating whether planning is recommended
    """
    if not question or len(question.strip()) < 10:
        return False

    q_lower = question.lower()

    # Comparison language
    comparison_keywords = [
        "compare", " vs ", " vs. ", "versus", "difference between",
        "more than", "less than", "which is better", "which sells better",
        "which is higher", "which is lower", "which has more", "which has less",
        " or ", "better than", "worse than"
    ]
    has_comparison = any(kw in q_lower for kw in comparison_keywords)

    # Percentage/ratio questions
    percentage_keywords = [
        "percentage", "percent", " % ", "ratio", "proportion",
        "share of", "portion of"
    ]
    has_percentage = any(kw in q_lower for kw in percentage_keywords)

    # Ranking with context (top/best/worst combined with "by" or numeric dimension)
    ranking_keywords = ["top ", "best ", "worst ", "highest ", "lowest "]
    has_ranking = any(kw in q_lower for kw in ranking_keywords)
    has_by_clause = " by " in q_lower
    # Also consider "which X has the best Y" type questions as needing planning
    has_which_best = "which" in q_lower and any(kw in q_lower for kw in ["best ", "worst ", "highest ", "lowest "])
    ranking_with_context = has_ranking and (has_by_clause or has_which_best)

    # Compound questions (multiple numeric intents)
    numeric_intent = ["total", "average", "how many", "sum", "count", "revenue", "profit", "sales"]
    and_present = " and " in q_lower
    numeric_count = sum(1 for kw in numeric_intent if kw in q_lower)
    is_compound = and_present and numeric_count >= 2

    # Pure calculation questions don't need planning
    pure_calc_keywords = ["what is", "calculate"]
    is_pure_calc = any(kw in q_lower for kw in pure_calc_keywords) and not has_comparison
    simple_math = any(op in question for op in ["+", "-", "*", "/", "percent of"])
    if is_pure_calc and simple_math:
        return False

    return has_comparison or has_percentage or ranking_with_context or is_compound


def get_system_prompt(needs_plan: bool = False) -> str:
    """Build the system prompt with tool descriptions and schema.

    Args:
        needs_plan: If True, adds instructions for emitting a plan action first
    """
    schema = get_schema()

    plan_instruction = ""
    if needs_plan:
        plan_instruction = """
MULTI-STEP PLANNING:
This question appears to require multiple steps. Before executing any tools, emit a plan action:
{{"action": "plan", "steps": "1. Query X\\n2. Query Y\\n3. Calculate Z"}}

The plan should be a numbered list of the operations you will perform. Once you emit a plan,
proceed directly to executing the steps - do NOT re-plan. The plan is never the final answer.
"""

    return f"""You are a helpful assistant for a board game cafe/shop. Answer questions using ONLY the data in the database.

TOOLS:
1. query - Execute SQL SELECT queries
2. calculate - Evaluate math expressions and statistics (supports +, -, *, /, mean, median, mode, stdev, range)
3. whatif - Scenario analysis ("what if prices increased 10%?", "what if we sold 20 more Catans?")
4. plan - Create a numbered plan for multi-step questions (use when comparisons, percentages, or multiple queries are needed)
{plan_instruction}
RESPONSE FORMAT:
You must respond with EXACTLY ONE JSON object per message. No other text, no explanations.

{{"action": "plan", "steps": "1. Query A\\n2. Query B\\n3. Compare"}}
{{"action": "query", "sql": "SELECT ..."}}
{{"action": "calculate", "expression": "123.45 + 67.89"}}
{{"action": "whatif", "scenario_type": "price_change", "params": {{"target": "games", "change_percent": 10}}}}
{{"action": "answer", "text": "Your final answer here"}}

ANSWER FORMAT:
The "answer" text MUST be natural language for a human reader, NOT raw JSON or data.
- WRONG: {{"action": "answer", "text": "{{\\"avg\\": 50.99, \\"median\\": 44.99}}"}}
- RIGHT: {{"action": "answer", "text": "The average game price is $50.99, with a median of $44.99."}}

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
5. For comparisons (percentages, ratios, "X vs Y", share of total):
   - You will often need MULTIPLE queries to get all the numbers
   - Example: "What percentage of inventory is Strategy games?" needs TWO queries:
     1. Query for Strategy stock: SELECT SUM(in_stock) FROM board_games WHERE category='Strategy'
     2. Query for total stock: SELECT SUM(in_stock) FROM board_games
     3. Then calculate: strategy_count / total_count * 100
   - Do NOT try to answer comparisons with only one query result

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


def call_ollama(messages: list[dict], system: str, streaming_callback=None) -> str:
    """Call a local Ollama model and return the response text.

    Args:
        messages: List of message dicts with role and content
        system: System prompt string
        streaming_callback: Optional callback function that receives each token as it arrives

    Returns:
        The complete response text
    """
    # Ollama uses OpenAI-style messages with system as first message
    ollama_messages = [{"role": "system", "content": system}] + messages

    request_body = {
        "model": OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": True,  # Enable streaming
        "options": {
            "temperature": 1.0,
            "top_p": 0.8,
            "top_k": 40,
            "num_predict": 4096,
        },
    }

    # Disable thinking mode for Qwen3 models
    if "qwen3" in OLLAMA_MODEL.lower():
        request_body["think"] = False

    # Log the request (just user messages, not system prompt)
    user_msgs = [m for m in messages if m["role"] == "user"]
    logger.debug(f"REQUEST | model={OLLAMA_MODEL} | messages={len(messages)} | last_user={user_msgs[-1]['content'][:200] if user_msgs else 'none'}...")

    start = time.perf_counter()

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=request_body,
            timeout=180,
            stream=True,  # Enable streaming on the request
        )
        response.raise_for_status()

        # Accumulate the full response from streaming chunks
        full_response = ""

        try:
            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    chunk = json.loads(line)

                    # Extract the content token from the chunk
                    if "message" in chunk and "content" in chunk["message"]:
                        token = chunk["message"]["content"]

                        # Only process non-empty tokens
                        if token:
                            full_response += token

                            # Call the streaming callback if provided
                            if streaming_callback is not None:
                                streaming_callback(token)

                    # Check if streaming is done
                    if chunk.get("done", False):
                        break

                except json.JSONDecodeError:
                    # Skip malformed JSON chunks
                    logger.warning(f"Skipping malformed JSON chunk: {line}")
                    continue

        except KeyboardInterrupt:
            # Clean up on interrupt
            response.close()
            raise

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        raise

    elapsed = time.perf_counter() - start

    # Log response with timing
    logger.debug(f"RESPONSE | {elapsed:.2f}s | content={full_response!r}")

    return full_response


def call_llm(messages: list[dict], system: str, streaming_callback=None) -> str:
    """Call the configured LLM backend.

    Args:
        messages: List of message dicts
        system: System prompt
        streaming_callback: Optional callback for streaming tokens (Ollama only)

    Returns:
        The complete response text
    """
    if BACKEND == "bedrock":
        return call_bedrock(messages, system)
    elif BACKEND == "ollama":
        return call_ollama(messages, system, streaming_callback=streaming_callback)
    else:
        raise ValueError(f"Unknown backend: {BACKEND}")


def execute_action(action: dict) -> tuple[str, bool]:
    """
    Execute a validated action and return the result.

    Returns:
        Tuple of (result_string, is_error)
    """
    action_type = action["action"]

    if action_type == "plan":
        # Plan actions are recorded but not "executed"
        # They will be handled specially in the main loop
        steps = action.get("steps", "")
        if isinstance(steps, list):
            steps = "\n".join(steps)
        return f"Plan recorded:\n{steps}", False

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
    streaming_callback=None,
) -> str:
    """
    Run the agent loop to answer a user query.

    Args:
        user_query: The user's question
        on_progress: Callback for progress updates (event, tool, detail)
        debug: If True, print raw model responses
        conversation_history: Optional list of previous Q&A pairs for context
        streaming_callback: Optional callback for streaming tokens (receives each token as string)

    Returns:
        The final answer string
    """
    def emit(event: str, tool: str = "", detail: str = ""):
        if on_progress:
            on_progress(event, tool, detail)

    # Check cache before doing any work
    try:
        cache_key = make_cache_key(user_query, conversation_history)
        cached_response = get_llm_response(cache_key)
        if cached_response is not None:
            emit("cache_hit", "", "Returning cached response")
            return cached_response
    except Exception:
        # Cache failure should not prevent the agent from running
        pass

    # Check if this question needs planning
    needs_plan = requires_plan(user_query)
    system = get_system_prompt(needs_plan=needs_plan)

    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_query})

    # Track whether we've had a successful tool call this query
    has_tool_result = False
    # Track plan state
    current_plan: Optional[str] = None
    plan_recorded = False
    # Track tool turns separately from total iterations
    turns_used = 0

    for turn in range(MAX_TURNS):
        # Call Claude with retry logic for invalid JSON
        response_text = None
        cleaned_response = None
        action = None

        for attempt in range(MAX_RETRIES):
            emit("thinking", "", f"Turn {turn + 1}")
            response_text = call_llm(messages, system, streaming_callback=streaming_callback)

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

        # Handle plan action specially
        if action_type == "plan":
            if plan_recorded:
                # Already have a plan, ignore duplicate plans
                emit("retry", "", "Plan already recorded, skipping duplicate...")
                messages.append({"role": "assistant", "content": cleaned_response})
                messages.append({
                    "role": "user",
                    "content": "You already have a plan. Proceed with executing the steps."
                })
                continue

            # Record the plan
            steps = action.get("steps", "")
            if isinstance(steps, list):
                current_plan = "\n".join(steps)
            else:
                current_plan = steps

            plan_recorded = True
            emit("tool_call", "plan", current_plan[:100])

            # Add plan to messages so it's visible in subsequent turns
            messages.append({"role": "assistant", "content": cleaned_response})
            messages.append({
                "role": "user",
                "content": f"Plan recorded:\n{current_plan}\n\nNow proceed with executing the steps."
            })
            continue

        # Check if this is the final answer
        if action_type == "answer":
            # Guardrail: require at least one successful tool call before answering
            if not has_tool_result:
                emit("guardrail", "", "No tool call yet, forcing query...")
                messages.append({"role": "assistant", "content": cleaned_response})
                messages.append({
                    "role": "user",
                    "content": "You must query the database before answering. Do not answer from memory or conversation history. Use a query action first."
                })
                continue
            emit("answer", "", "")
            # Cache the response before returning
            final_answer = action["text"]
            try:
                set_llm_response(cache_key, user_query, final_answer)
            except Exception:
                # Cache write failure should not prevent returning the answer
                pass
            return final_answer

        # Track tool turns (plan doesn't count)
        turns_used += 1
        if turns_used > MAX_TURNS:
            return "Error: Agent reached maximum turns without providing an answer."

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

        # Track successful tool calls
        if not is_error:
            has_tool_result = True

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
