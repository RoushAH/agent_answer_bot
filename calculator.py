"""Safe calculator using AST parsing."""

import ast
import operator
from typing import Union

# Allowed operators
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> Union[int, float]:
    """Recursively evaluate an AST node."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
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
    else:
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def calculate(expression: str) -> float:
    """
    Safely evaluate a mathematical expression.

    Supports: +, -, *, /, parentheses, unary minus

    Args:
        expression: A string containing a math expression (e.g., "2 + 3 * 4")

    Returns:
        The result as a float

    Raises:
        ValueError: If the expression is invalid or uses unsupported operations
    """
    try:
        tree = ast.parse(expression, mode='eval')
        result = _eval_node(tree)
        return float(result)
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}")
    except ZeroDivisionError:
        raise ValueError("Division by zero")


if __name__ == "__main__":
    # Test examples
    tests = [
        "2 + 2",
        "10 * 5 + 3",
        "(10 + 5) * 3",
        "100 / 4",
        "-5 + 10",
        "3.14 * 2",
    ]
    for expr in tests:
        print(f"{expr} = {calculate(expr)}")
