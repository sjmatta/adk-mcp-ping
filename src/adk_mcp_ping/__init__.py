"""ADK MCP Ping - Keep-alive pings for Google ADK MCP connections.

This package provides a drop-in replacement for McpToolset that automatically
sends periodic ping requests to keep connections alive during long-running
operations. Essential when running behind load balancers with idle timeouts.

Usage::

    from adk_mcp_ping import PingEnabledMcpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    agent = LlmAgent(
        name="my_agent",
        model=LiteLlm(model="openai/gpt-4"),
        tools=[
            PingEnabledMcpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url="http://server:8000/mcp",
                ),
                ping_interval=50.0,  # Ping every 50s (< ALB 60s timeout)
            )
        ],
    )
"""

from .session_manager import PingEnabledSessionManager
from .toolset import PingEnabledMcpToolset

__version__ = "0.1.0"

__all__ = [
    "PingEnabledMcpToolset",
    "PingEnabledSessionManager",
]
