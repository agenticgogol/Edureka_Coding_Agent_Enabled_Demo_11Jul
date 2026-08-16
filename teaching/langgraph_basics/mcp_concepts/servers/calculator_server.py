"""A minimal MCP server: tools only, no resources or prompts.

Run standalone (stdio transport, the default): `python calculator_server.py`.
Deliberately the simplest possible server in this teaching set -- notebook 01
starts with this one before introducing resources/prompts on a second server.
"""
from fastmcp import FastMCP

mcp = FastMCP("Calculator")


@mcp.tool
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@mcp.tool
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


@mcp.tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@mcp.tool
def divide(a: float, b: float) -> float:
    """Divide a by b. Raises an error if b is zero."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b


@mcp.tool
def percentage_of(part: float, whole: float) -> float:
    """Compute what percentage `part` is of `whole` (e.g. percentage_of(25, 200) -> 12.5)."""
    if whole == 0:
        raise ValueError("Cannot compute a percentage of zero.")
    return (part / whole) * 100


if __name__ == "__main__":
    mcp.run()
