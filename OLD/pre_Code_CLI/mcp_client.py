"""Thin wrapper around the official `mcp` Python SDK, scoped to what the
test generator needs: spawn the Playwright MCP server, list its tools in a
shape the Anthropic Messages API understands, and execute tool calls on
Claude's behalf.
"""
from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class PlaywrightMCPSession:
    def __init__(self, command: str, args: list[str]):
        self._params = StdioServerParameters(command=command, args=args)
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def __aenter__(self) -> "PlaywrightMCPSession":
        read_stream, write_stream = await self._stack.enter_async_context(
            stdio_client(self._params)
        )
        self.session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._stack.aclose()

    async def anthropic_tools(self) -> list[dict[str, Any]]:
        """Fetch the MCP tool list, reshaped for the Anthropic Messages API `tools` param."""
        assert self.session is not None
        result = await self.session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute an MCP tool call and flatten the result into a string for the model."""
        assert self.session is not None
        result = await self.session.call_tool(name, arguments)
        text_parts = [
            block.text for block in result.content if getattr(block, "type", None) == "text"
        ]
        payload = (
            "\n".join(text_parts)
            if text_parts
            else json.dumps([block.model_dump() for block in result.content])
        )
        return f"TOOL ERROR: {payload}" if result.isError else payload
