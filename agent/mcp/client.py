"""MCP client adapter.

Connects to MCP servers at startup to discover their tools, then wraps each
tool as a `Tool` subclass compatible with the agent's unified tool interface.

Design note (POC):
  Each tool call opens a fresh connection to the MCP server, executes the call,
  and closes the connection.  This is simple and correct for a proof-of-concept;
  a production implementation would maintain persistent sessions using a
  background asyncio event loop.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import MCPServerConfig

from ..tools.base import Tool, ToolResult


class MCPTool(Tool):
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict,
        server_config: MCPServerConfig,
    ) -> None:
        self._name = name
        self._description = description
        self._input_schema = input_schema
        self._server_config = server_config

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict:
        return self._input_schema

    def execute(self, **kwargs) -> ToolResult:
        try:
            result = asyncio.run(self._async_execute(kwargs))
            content = "\n".join(
                item.text for item in result.content if hasattr(item, "text")
            )
            return ToolResult(success=not result.isError, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _async_execute(self, args: dict):
        cfg = self._server_config
        if cfg.transport == "stdio":
            return await self._call_stdio(args)
        elif cfg.transport == "sse":
            return await self._call_sse(args)
        else:
            raise ValueError(f"Unknown transport: {cfg.transport}")

    async def _call_stdio(self, args: dict):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        cfg = self._server_config
        params = StdioServerParameters(
            command=cfg.command,
            args=cfg.args,
            env=cfg.env or None,
        )
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await session.call_tool(self._name, args)

    async def _call_sse(self, args: dict):
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        cfg = self._server_config
        async with sse_client(cfg.url) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return await session.call_tool(self._name, args)


class MCPManager:
    """Discovers tools from all configured MCP servers at startup."""

    def load_all(self, servers: dict[str, MCPServerConfig]) -> list[Tool]:
        tools: list[Tool] = []
        for name, cfg in servers.items():
            try:
                server_tools = asyncio.run(self._list_tools(name, cfg))
                tools.extend(server_tools)
            except Exception as e:
                print(f"[警告] MCP サーバー '{name}' からのツール取得に失敗: {e}")
        return tools

    async def _list_tools(
        self, server_name: str, cfg: MCPServerConfig
    ) -> list[MCPTool]:
        if cfg.transport == "stdio":
            return await self._list_stdio(server_name, cfg)
        elif cfg.transport == "sse":
            return await self._list_sse(server_name, cfg)
        else:
            raise ValueError(f"Unknown transport: {cfg.transport}")

    async def _list_stdio(
        self, server_name: str, cfg: MCPServerConfig
    ) -> list[MCPTool]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=cfg.command,
            args=cfg.args,
            env=cfg.env or None,
        )
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                response = await session.list_tools()
                return [
                    MCPTool(
                        name=f"{server_name}__{t.name}",
                        description=t.description or "",
                        input_schema=t.inputSchema or {},
                        server_config=cfg,
                    )
                    for t in response.tools
                ]

    async def _list_sse(
        self, server_name: str, cfg: MCPServerConfig
    ) -> list[MCPTool]:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(cfg.url) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                response = await session.list_tools()
                return [
                    MCPTool(
                        name=f"{server_name}__{t.name}",
                        description=t.description or "",
                        input_schema=t.inputSchema or {},
                        server_config=cfg,
                    )
                    for t in response.tools
                ]
