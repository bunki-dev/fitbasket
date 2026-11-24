"""Expose FitBasket's tools over the Model Context Protocol.

Any MCP client (Claude Desktop, Claude Code, an Azure AI Foundry agent...) can plan meals,
build the basket and create workouts with the same typed tools the built-in agent uses.

    fitbasket-mcp                         # stdio (for desktop clients)
    fitbasket-mcp --transport streamable-http
"""

from __future__ import annotations

import argparse
import inspect
import json

from mcp.server.mcpserver import MCPServer

from .store import UserState, reference_data
from .tools import TOOLS, Tool, ToolError

# One user per MCP server process; state lives as long as the session.
STATE = UserState.demo()


def _make_handler(tool: Tool):
    """Build a function whose signature mirrors the tool's pydantic args, so MCP derives the schema."""
    fields = tool.args_model.model_fields
    params = [
        inspect.Parameter(
            name,
            inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty if f.is_required() else f.get_default(call_default_factory=True),
            annotation=f.annotation,
        )
        for name, f in fields.items()
    ]

    def handler(**kwargs) -> str:
        try:
            return json.dumps(tool.run(STATE, kwargs, reference_data()), default=str)
        except ToolError as e:
            # Raising makes the MCP client see an isError result with this message.
            raise ValueError(str(e)) from e

    handler.__name__ = tool.name
    handler.__doc__ = tool.description
    handler.__signature__ = inspect.Signature(params, return_annotation=str)
    handler.__annotations__ = {**{n: f.annotation for n, f in fields.items()}, "return": str}
    return handler


def build_server() -> MCPServer:
    server = MCPServer(
        name="fitbasket",
        instructions="Meal planning, deal-aware grocery baskets and workout plans. Create a meal plan before "
        "building the shopping basket.",
    )
    for tool in TOOLS:
        server.add_tool(_make_handler(tool), name=tool.name, description=tool.description)
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="FitBasket MCP server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    args = parser.parse_args()
    build_server().run(transport=args.transport)


if __name__ == "__main__":
    main()
