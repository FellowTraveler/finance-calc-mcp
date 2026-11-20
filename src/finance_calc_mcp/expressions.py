"""Bounded math expression interpreter (no Python execution)."""
import ast
import math
import operator

MAX_EXPRESSION_LENGTH = 4096
MAX_EXPRESSION_NODES = 256
MAX_EXPRESSION_DEPTH = 32


def safe_eval(expr: str) -> float:
    """Interpret a bounded numeric AST; never execute Python user code."""
    if not isinstance(expr, str) or len(expr) > MAX_EXPRESSION_LENGTH:
        raise ValueError(f"Expression must be a string of at most {MAX_EXPRESSION_LENGTH} characters")
    functions = {
        "round": round, "abs": abs, "max": max, "min": min,
        "sum": sum, "sqrt": math.sqrt, "log": math.log,
        "floor": math.floor, "ceil": math.ceil, "pow": math.pow,
    }
    binary = {ast.Add: operator.add, ast.Sub: operator.sub,
              ast.Mult: operator.mul, ast.Div: operator.truediv,
              ast.Mod: operator.mod, ast.Pow: math.pow}

    def number(value):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Only finite real numbers are supported")
        return value

    def visit(node, depth=0):
        if depth > MAX_EXPRESSION_DEPTH:
            raise ValueError("Expression is too deeply nested")
        if isinstance(node, ast.Constant):
            return number(node.value)
        if isinstance(node, ast.Name) and node.id in ("pi", "e"):
            return getattr(math, node.id)
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
            value = number(visit(node.operand, depth + 1))
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in binary:
            left = number(visit(node.left, depth + 1))
            right = number(visit(node.right, depth + 1))
            return number(binary[type(node.op)](left, right))
        if isinstance(node, (ast.List, ast.Tuple)):
            return [number(visit(item, depth + 1)) for item in node.elts]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in functions and not node.keywords):
            args = [visit(arg, depth + 1) for arg in node.args]
            return number(functions[node.func.id](*args))
        raise ValueError("Unsupported expression syntax")

    try:
        tree = ast.parse(expr.strip(), mode="eval")
        if sum(1 for _ in ast.walk(tree)) > MAX_EXPRESSION_NODES:
            raise ValueError("Expression is too complex")
        return float(number(visit(tree.body)))
    except (ValueError, TypeError, ArithmeticError, SyntaxError, RecursionError) as exc:
        raise ValueError(f"Cannot evaluate expression: {exc}") from exc


