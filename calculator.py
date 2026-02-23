"""Safe calculator using AST parsing with statistical functions."""

import ast
import operator
import statistics
from typing import Union

# Allowed binary/unary operators
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _stat_range(values: list) -> float:
    """Calculate range (max - min) of values."""
    if not values:
        raise ValueError("range() requires at least one value")
    return max(values) - min(values)


# Allowed functions (n-ary operations)
FUNCTIONS = {
    "mean": statistics.mean,
    "median": statistics.median,
    "mode": statistics.mode,
    "stdev": statistics.stdev,
    "range": _stat_range,
    # Aliases
    "avg": statistics.mean,
    "average": statistics.mean,
    "std": statistics.stdev,
}


def _eval_node(node: ast.AST) -> Union[int, float, list]:
    """Recursively evaluate an AST node."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    elif isinstance(node, ast.List):
        # Evaluate each element in the list
        return [_eval_node(elem) for elem in node.elts]

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return OPERATORS[op_type](left, right)

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _eval_node(node.operand)
        return OPERATORS[op_type](operand)

    elif isinstance(node, ast.Call):
        # Handle function calls like mean(1, 2, 3) or mean([1, 2, 3])
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function names are allowed")

        func_name = node.func.id.lower()
        if func_name not in FUNCTIONS:
            allowed = ", ".join(sorted(FUNCTIONS.keys()))
            raise ValueError(f"Unknown function: {func_name}. Allowed: {allowed}")

        # Evaluate all arguments
        args = []
        for arg in node.args:
            val = _eval_node(arg)
            if isinstance(val, list):
                args.extend(val)  # Flatten lists
            else:
                args.append(val)

        if not args:
            raise ValueError(f"{func_name}() requires at least one argument")

        # Special case: stdev needs at least 2 values
        if func_name in ("stdev", "std") and len(args) < 2:
            raise ValueError("stdev() requires at least two values")

        return FUNCTIONS[func_name](args)

    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def calculate(expression: str) -> float:
    """
    Safely evaluate a mathematical expression.

    Supports:
        - Arithmetic: +, -, *, /, parentheses, unary minus
        - Statistics: mean(), median(), mode(), stdev(), range()
        - Aliases: avg(), average(), std()

    Examples:
        calculate("2 + 3 * 4")           → 14.0
        calculate("mean(10, 20, 30)")    → 20.0
        calculate("stdev(2, 4, 4, 4, 5, 5, 7, 9)") → 2.138...
        calculate("range(1, 5, 10)")     → 9.0

    Args:
        expression: A string containing a math expression

    Returns:
        The result as a float

    Raises:
        ValueError: If the expression is invalid or uses unsupported operations
    """
    try:
        tree = ast.parse(expression, mode='eval')
        result = _eval_node(tree)
        if isinstance(result, list):
            raise ValueError("Expression must evaluate to a single number, not a list")
        return float(result)
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}")
    except ZeroDivisionError:
        raise ValueError("Division by zero")
    except statistics.StatisticsError as e:
        raise ValueError(f"Statistics error: {e}")


if __name__ == "__main__":
    # Test examples
    tests = [
        # Basic arithmetic
        "2 + 2",
        "10 * 5 + 3",
        "(10 + 5) * 3",
        "100 / 4",
        "-5 + 10",
        "3.14 * 2",
        # Statistical functions
        "mean(10, 20, 30)",
        "mean([10, 20, 30])",
        "median(1, 3, 5, 7, 9)",
        "mode(1, 2, 2, 3, 3, 3)",
        "stdev(2, 4, 4, 4, 5, 5, 7, 9)",
        "range(1, 5, 10, 3)",
        # Aliases
        "avg(100, 200)",
        "std(10, 20, 30, 40)",
        # Combined
        "mean(10, 20, 30) * 2",
        "100 + stdev(2, 4, 4, 4, 5, 5, 7, 9)",
    ]
    for expr in tests:
        try:
            result = calculate(expr)
            print(f"{expr} = {result}")
        except ValueError as e:
            print(f"{expr} → ERROR: {e}")
