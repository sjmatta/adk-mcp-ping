"""Ping-enabled MCP toolset for Google ADK."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from .session_manager import (
    DEFAULT_PING_INTERVAL_SECONDS,
    PingEnabledSessionManager,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TextIO

    from google.adk.agents.readonly_context import ReadonlyContext
    from google.adk.auth.auth_credential import AuthCredential
    from google.adk.auth.auth_schemes import AuthScheme
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        SseConnectionParams,
        StdioConnectionParams,
        StreamableHTTPConnectionParams,
    )
    from mcp import StdioServerParameters

    ConnectionParams = (
        StdioServerParameters
        | StdioConnectionParams
        | SseConnectionParams
        | StreamableHTTPConnectionParams
    )


class PingEnabledMcpToolset(McpToolset):
    """MCP Toolset with automatic keep-alive pings.

    Drop-in replacement for McpToolset that automatically sends periodic
    ping requests to keep connections alive during long-running operations.
    Essential when running behind load balancers with idle timeouts.

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

    Args:
        connection_params: Parameters for the MCP connection.
        ping_interval: Interval in seconds between keep-alive pings.
                      Default 50s (suitable for AWS ALB's 60s timeout).
        tool_filter: Optional filter for specific tools.
        tool_name_prefix: Prefix for tool names.
        errlog: Stream for error logging.
        auth_scheme: Authentication scheme for tool calling.
        auth_credential: Authentication credentials.
        require_confirmation: Whether tools require user confirmation.
        header_provider: Callable returning headers for MCP sessions.
    """

    def __init__(
        self,
        *,
        connection_params: ConnectionParams,
        ping_interval: float = DEFAULT_PING_INTERVAL_SECONDS,
        tool_filter: list[str] | Callable[..., bool] | None = None,
        tool_name_prefix: str | None = None,
        errlog: TextIO = sys.stderr,
        auth_scheme: AuthScheme | None = None,
        auth_credential: AuthCredential | None = None,
        require_confirmation: bool | Callable[..., bool] = False,
        header_provider: Callable[[ReadonlyContext], dict[str, str]] | None = None,
    ) -> None:
        """Initialize the ping-enabled MCP toolset."""
        self._ping_interval = ping_interval

        super().__init__(
            connection_params=connection_params,
            tool_filter=tool_filter,
            tool_name_prefix=tool_name_prefix,
            errlog=errlog,
            auth_scheme=auth_scheme,
            auth_credential=auth_credential,
            require_confirmation=require_confirmation,
            header_provider=header_provider,
        )

        # Replace the default session manager with our ping-enabled version
        self._mcp_session_manager = PingEnabledSessionManager(
            connection_params=connection_params,
            ping_interval=ping_interval,
            errlog=errlog,
        )
