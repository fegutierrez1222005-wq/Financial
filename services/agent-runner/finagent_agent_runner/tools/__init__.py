"""Tool registry construction."""

from finagent_agent_runner.tools.base import Tool, ToolPermission, ToolRegistry, ToolResult
from finagent_agent_runner.tools.compute import CalculatorTool, PythonTool, evaluate_expression
from finagent_agent_runner.tools.market import FinancialStatementsTool, MarketDataTool
from finagent_agent_runner.tools.quant import BacktestTool, PortfolioAnalysisTool
from finagent_agent_runner.tools.research import DocumentSearchTool, SecSearchTool


def build_default_tool_registry() -> ToolRegistry:
    """The V1 tool set. Additional tools register here without touching the runner."""
    return ToolRegistry(
        [
            DocumentSearchTool(),
            SecSearchTool(),
            MarketDataTool(),
            FinancialStatementsTool(),
            CalculatorTool(),
            PythonTool(),
            BacktestTool(),
            PortfolioAnalysisTool(),
        ]
    )


__all__ = [
    "Tool",
    "ToolPermission",
    "ToolRegistry",
    "ToolResult",
    "CalculatorTool",
    "PythonTool",
    "evaluate_expression",
    "FinancialStatementsTool",
    "MarketDataTool",
    "BacktestTool",
    "PortfolioAnalysisTool",
    "DocumentSearchTool",
    "SecSearchTool",
    "build_default_tool_registry",
]
