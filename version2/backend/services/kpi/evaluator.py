"""
Safe Arithmetic Evaluator
========================
AST-based formula evaluator — no eval(), no exec(), no arbitrary code.
"""

import ast
from typing import Callable


_SAFE_OPS: dict[
    type[ast.operator], Callable[[float], float] | Callable[[float, float], float]
] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.USub: lambda a: -a,
}


def _eval_node(n: ast.expr) -> float:
    if isinstance(n, ast.Constant):
        v = n.value
        if isinstance(v, (int, float)):
            return float(v)
        raise ValueError(f"Unsupported constant type: {type(v)}")
    if isinstance(n, ast.BinOp):
        op = _SAFE_OPS.get(type(n.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(n.op)}")
        return op(_eval_node(n.left), _eval_node(n.right))
    if isinstance(n, ast.UnaryOp):
        op = _SAFE_OPS.get(type(n.op))
        if op is None:
            raise ValueError(f"Unsupported unary operator: {type(n.op)}")
        return op(_eval_node(n.operand))
    raise ValueError(f"Unsupported node type: {type(n)}")


def safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body)
