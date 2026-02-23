"""JSON action schema and validation."""

import json
import re
from typing import Optional

VALID_ACTIONS = {"query", "calculate", "answer"}


def _fix_json_newlines(s: str) -> str:
    """Escape unescaped newlines inside JSON string values."""
    result = []
    in_string = False
    i = 0
    while i < len(s):
        char = s[i]
        if char == '\\' and in_string and i + 1 < len(s):
            # Keep escape sequence as-is
            result.append(char)
            result.append(s[i + 1])
            i += 2
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
        elif char == '\n' and in_string:
            result.append('\\n')
        elif char == '\r' and in_string:
            result.append('\\r')
        elif char == '\t' and in_string:
            result.append('\\t')
        else:
            result.append(char)
        i += 1
    return ''.join(result)


def _validate_fields(data: dict) -> Optional[dict]:
    """Validate the fields of a parsed action dict."""
    if not isinstance(data, dict):
        return None

    action = data.get("action")
    if action not in VALID_ACTIONS:
        return None

    if action == "query":
        if "sql" not in data or not isinstance(data["sql"], str):
            return None
        sql = data["sql"].strip().upper()
        if not sql.startswith("SELECT"):
            return None
    elif action == "calculate":
        if "expression" not in data or not isinstance(data["expression"], str):
            return None
    elif action == "answer":
        if "text" not in data or not isinstance(data["text"], str):
            return None

    return data


def validate_action(json_str: str) -> tuple[Optional[dict], str]:
    """
    Validate a JSON action string against the schema.

    Valid action formats:
        {"action": "query", "sql": "SELECT ..."}
        {"action": "calculate", "expression": "2 + 2"}
        {"action": "answer", "text": "The answer is..."}

    Args:
        json_str: A JSON string to validate

    Returns:
        Tuple of (parsed dict or None, cleaned JSON string for conversation)
    """
    # Try to extract JSON from the string (handle markdown code blocks)
    json_str = json_str.strip()

    # Remove markdown code blocks if present
    if json_str.startswith("```"):
        # Find content between code fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", json_str, re.DOTALL)
        if match:
            json_str = match.group(1).strip()

    # Try to parse the string as-is first (only if it's a single JSON object)
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            result = _validate_fields(data)
            if result:
                return result, json_str
    except json.JSONDecodeError:
        pass

    # Try fixing unescaped newlines in JSON strings
    fixed = _fix_json_newlines(json_str)
    if fixed != json_str:
        try:
            data = json.loads(fixed)
            if isinstance(data, dict):
                result = _validate_fields(data)
                if result:
                    return result, fixed
        except json.JSONDecodeError:
            pass

    # Try to extract FIRST JSON object using brace matching
    start = json_str.find('{')
    if start == -1:
        return None, json_str

    # Find matching closing brace
    depth = 0
    end = -1
    in_string = False
    escape_next = False

    for i, char in enumerate(json_str[start:], start):
        if escape_next:
            escape_next = False
            continue
        if char == '\\' and in_string:
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        return None, json_str

    extracted = json_str[start:end]

    # Fix newlines in extracted JSON
    fixed_extracted = _fix_json_newlines(extracted)

    try:
        data = json.loads(fixed_extracted)
    except json.JSONDecodeError:
        return None, json_str

    result = _validate_fields(data)
    if result:
        # Return the cleaned single-object JSON (not the original with multiple objects)
        return result, fixed_extracted
    return None, json_str


if __name__ == "__main__":
    # Test examples
    tests = [
        '{"action": "query", "sql": "SELECT * FROM board_games"}',
        '{"action": "calculate", "expression": "2 + 2"}',
        '{"action": "answer", "text": "There are 15 games."}',
        '{"action": "invalid"}',
        'not json',
        '```json\n{"action": "answer", "text": "Hello"}\n```',
        # Multi-JSON test
        '{"action": "query", "sql": "SELECT 1"}\n\n{"action": "calculate", "expression": "fake"}',
    ]
    for test in tests:
        result, cleaned = validate_action(test)
        print(f"{test[:50]!r}...")
        print(f"  -> {result}")
        if cleaned != test:
            print(f"  cleaned: {cleaned!r}")
