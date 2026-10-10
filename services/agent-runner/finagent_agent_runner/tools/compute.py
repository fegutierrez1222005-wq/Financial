"""Calculation tools: a deterministic calculator and the sandboxed Python tool.

Financial claims must be recomputable. The calculator returns the formula alongside the
value so the evaluation engine can re-derive and verify every number the agent asserts.
"""

from __future__ import annotations

import ast
import math
import statistics
from typing import Any

from finagent_core.errors import ToolFailedError, ValidationFailedError
from finagent_core.numeric import Unit, cagr, percent_change, safe_div

from finagent_agent_runner.context import ToolContext
from finagent_agent_runner.tools.base import Tool, ToolPermission, ToolResult

_ALLOWED_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "sum": sum,
    "len": len,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "pow": pow,
    "mean": statistics.fmean,
    "median": statistics.median,
    "stdev": lambda values: statistics.stdev(values) if len(values) > 1 else 0.0,
}

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
    ast.List, ast.Tuple, ast.Compare, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
    ast.IfExp,
)


def evaluate_expression(expression: str, variables: dict[str, float] | None = None) -> float:
    """Evaluate an arithmetic expression with no name resolution beyond ``variables``."""
    variables = variables or {}
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValidationFailedError(f"invalid expression: {exc.msg}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValidationFailedError(
                f"expression contains an unsupported construct: {type(node).__name__}"
            )
        if isinstance(node, ast.Name) and node.id not in variables and node.id not in _ALLOWED_FUNCTIONS:
            raise ValidationFailedError(f"unknown name in expression: {node.id}")
        if isinstance(node, ast.Call) and not (
            isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCTIONS
        ):
            raise ValidationFailedError("only whitelisted numeric functions may be called")

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            raise ValidationFailedError("only numeric literals are allowed")
        if isinstance(node, ast.Name):
            return variables[node.id] if node.id in variables else _ALLOWED_FUNCTIONS[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [_eval(element) for element in node.elts]
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            return -operand if isinstance(node.op, ast.USub) else +operand
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            for node_type, handler in {
                ast.Add: lambda: left + right,
                ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right,
                ast.Div: lambda: left / right,
                ast.FloorDiv: lambda: left // right,
                ast.Mod: lambda: left % right,
                ast.Pow: lambda: left**right,
            }.items():
                if isinstance(node.op, node_type):
                    return handler()
        if isinstance(node, ast.Call):
            return _eval(node.func)(*[_eval(argument) for argument in node.args])
        if isinstance(node, ast.Compare):
            left, right = _eval(node.left), _eval(node.comparators[0])
            for node_type, value in {
                ast.Lt: left < right,
                ast.LtE: left <= right,
                ast.Gt: left > right,
                ast.GtE: left >= right,
                ast.Eq: left == right,
                ast.NotEq: left != right,
            }.items():
                if isinstance(node.ops[0], node_type):
                    return value
        if isinstance(node, ast.IfExp):
            return _eval(node.body) if _eval(node.test) else _eval(node.orelse)
        raise ValidationFailedError(f"unsupported expression node: {type(node).__name__}")

    try:
        value = _eval(tree)
    except ZeroDivisionError as exc:
        raise ValidationFailedError("division by zero") from exc
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationFailedError("expression did not evaluate to a number")
    return float(value)


class CalculatorTool(Tool):
    name = "CALCULATOR"
    description = (
        "Perform an auditable financial calculation. Supported operations: percent_change, cagr, "
        "margin, ratio, sum, mean, median, stdev, expression. Returns the value, the unit and the "
        "formula used, so the calculation can be independently re-derived."
    )
    required_permissions = (ToolPermission.COMPUTE,)
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "percent_change", "cagr", "margin", "ratio", "sum", "mean", "median", "stdev",
                    "expression",
                ],
                "default": "expression",
            },
            "new_value": {"type": "number"},
            "old_value": {"type": "number"},
            "numerator": {"type": "number"},
            "denominator": {"type": "number"},
            "begin_value": {"type": "number"},
            "end_value": {"type": "number"},
            "years": {"type": "number"},
            "values": {"type": "array", "items": {"type": "number"}},
            "expression": {"type": "string"},
            "variables": {"type": "object"},
            "label": {"type": "string", "description": "Name for the result, e.g. 'revenue_growth_pct'."},
        },
    }

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:  # noqa: ARG002
        operation = str(arguments.get("operation") or "expression")
        try:
            value, unit, formula = self._compute(operation, arguments)
        except (ValidationFailedError, ToolFailedError):
            raise
        except (TypeError, ValueError, KeyError, statistics.StatisticsError) as exc:
            raise ValidationFailedError(f"calculation failed: {exc}") from exc

        return ToolResult(
            payload={
                "operation": operation,
                "label": str(arguments.get("label") or operation),
                "value": round(float(value), 6),
                "unit": unit.value,
                "formula": formula,
                "inputs": {
                    key: arguments[key]
                    for key in arguments
                    if key not in {"operation", "label"} and arguments[key] is not None
                },
            }
        )

    def _compute(self, operation: str, arguments: dict[str, Any]) -> tuple[float, Unit, str]:
        if operation == "percent_change":
            new_value = _required_number(arguments, "new_value")
            old_value = _required_number(arguments, "old_value")
            if old_value == 0:
                raise ValidationFailedError("percent_change requires a non-zero old_value")
            return (
                percent_change(new_value, old_value),
                Unit.PERCENT,
                f"({new_value} - {old_value}) / |{old_value}| * 100",
            )
        if operation == "cagr":
            begin = _required_number(arguments, "begin_value")
            end = _required_number(arguments, "end_value")
            years = _required_number(arguments, "years")
            return cagr(begin, end, years), Unit.PERCENT, f"(({end} / {begin}) ^ (1 / {years}) - 1) * 100"
        if operation == "margin":
            numerator = _required_number(arguments, "numerator")
            denominator = _required_number(arguments, "denominator")
            if denominator == 0:
                raise ValidationFailedError("margin requires a non-zero denominator")
            return (
                safe_div(numerator, denominator) * 100.0,
                Unit.PERCENT,
                f"{numerator} / {denominator} * 100",
            )
        if operation == "ratio":
            numerator = _required_number(arguments, "numerator")
            denominator = _required_number(arguments, "denominator")
            if denominator == 0:
                raise ValidationFailedError("ratio requires a non-zero denominator")
            return safe_div(numerator, denominator), Unit.RATIO, f"{numerator} / {denominator}"
        if operation in {"sum", "mean", "median", "stdev"}:
            values = arguments.get("values") or []
            if not values:
                raise ValidationFailedError(f"{operation} requires a non-empty 'values' array")
            numbers = [float(value) for value in values]
            computed = {
                "sum": sum(numbers),
                "mean": statistics.fmean(numbers),
                "median": statistics.median(numbers),
                "stdev": statistics.stdev(numbers) if len(numbers) > 1 else 0.0,
            }[operation]
            return computed, Unit.NUMBER, f"{operation}({numbers})"

        expression = str(arguments.get("expression") or "").strip()
        if not expression:
            raise ValidationFailedError("expression operation requires an 'expression'")
        variables = {
            str(key): float(value)
            for key, value in (arguments.get("variables") or {}).items()
            if isinstance(value, (int, float))
        }
        return evaluate_expression(expression, variables), Unit.NUMBER, expression


def _required_number(arguments: dict[str, Any], key: str) -> float:
    value = arguments.get(key)
    if value is None:
        raise ValidationFailedError(f"missing required numeric argument: {key}")
    return float(value)


class PythonTool(Tool):
    name = "PYTHON"
    description = (
        "Execute Python in an isolated sandbox (no network, CPU/memory/time limited, allow-listed "
        "imports including numpy, pandas, math and statistics). Assign a dict to a variable named "
        "`results` to return structured values; stdout is captured."
    )
    required_permissions = (ToolPermission.EXECUTE_CODE,)
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source to execute."},
            "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 60, "default": 20},
            "purpose": {"type": "string", "description": "Why this runs (recorded in the trace)."},
        },
        "required": ["code"],
    }

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        if context.sandbox is None:
            raise ToolFailedError("the Python sandbox is not available in this environment")
        result = context.sandbox.run(
            str(arguments["code"]), timeout_seconds=float(arguments.get("timeout_seconds") or 20.0)
        )
        context.record_usage(
            "PYTHON_SECONDS", result.execution_time_ms / 1000.0, purpose=arguments.get("purpose")
        )
        return ToolResult(
            payload={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "results": result.results,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
                "succeeded": result.succeeded,
            },
            warnings=(["The submitted code raised an exception; see 'error'."] if result.error else []),
            detail={"purpose": arguments.get("purpose")},
        )
