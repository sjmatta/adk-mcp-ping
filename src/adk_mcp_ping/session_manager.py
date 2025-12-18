"""Ping-enabled MCP session manager for keep-alive functionality."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Any

from google.adk.tools.mcp_tool.mcp_session_manager import MCPSessionManager

if TYPE_CHECKING:
    from typing import TextIO

    from google.adk.tools.mcp_tool.mcp_session_manager import (
        SseConnectionParams,
        StdioConnectionParams,
        StreamableHTTPConnectionParams,
    )
    from mcp import ClientSession, StdioServerParameters

    ConnectionParams = (
        StdioServerParameters
        | StdioConnectionParams
        | SseConnectionParams
        | StreamableHTTPConnectionParams
    )

logger = logging.getLogger("adk_mcp_ping." + __name__)


class PingEnabledSessionManager(MCPSessionManager):
    """MCP session manager with automatic keep-alive pings.

    This extends MCPSessionManager to automatically send periodic ping
    requests to keep connections alive during long-running operations.
    This is essential when running behind load balancers (like AWS ALB)
    that have idle connection timeouts.

    The ping interval should be set lower than your load balancer's
    idle timeout (e.g., 50s for AWS ALB's default 60s timeout).
    """

    def __init__(
        self,
        connection_params: ConnectionParams,
        ping_interval: float = 50.0,
        errlog: TextIO = sys.stderr,
    ) -> None:
        """Initialize the ping-enabled session manager.

        Args:
            connection_params: Parameters for the MCP connection.
            ping_interval: Interval in seconds between pings. Default 50s
                          (suitable for AWS ALB's 60s default timeout).
            errlog: TextIO stream for error logging.
        """
        super().__init__(connection_params=connection_params, errlog=errlog)
        self._ping_interval = ping_interval
        self._ping_tasks: dict[str, asyncio.Task[Any]] = {}
        self._ping_task_lock = asyncio.Lock()

    async def create_session(
        self, headers: dict[str, str] | None = None
    ) -> ClientSession:
        """Create a session and start a ping task for it.

        Args:
            headers: Optional headers to include in the session.

        Returns:
            ClientSession: The initialized MCP client session.
        """
        # Call parent to create/get the session
        session = await super().create_session(headers=headers)

        # Generate the session key to track the ping task
        merged_headers = self._merge_headers(headers)
        session_key = self._generate_session_key(merged_headers)

        # Start ping task if not already running for this session
        async with self._ping_task_lock:
            if session_key not in self._ping_tasks:
                task = asyncio.create_task(
                    self._ping_loop(session, session_key),
                    name=f"ping_loop_{session_key[:8]}",
                )
                self._ping_tasks[session_key] = task
                logger.debug(
                    "Started ping task for session %s (interval: %.1fs)",
                    session_key[:8],
                    self._ping_interval,
                )

        return session

    async def _ping_loop(self, session: ClientSession, session_key: str) -> None:
        """Background task that sends periodic pings to keep the connection alive.

        Args:
            session: The MCP client session to ping.
            session_key: Key identifying this session for logging.
        """
        ping_count = 0
        while True:
            try:
                await asyncio.sleep(self._ping_interval)

                # Check if session is still connected
                if self._is_session_disconnected(session):
                    logger.debug(
                        "Session %s disconnected, stopping ping loop",
                        session_key[:8],
                    )
                    break

                # Send ping
                ping_count += 1
                await session.send_ping()
                logger.debug(
                    "Ping #%d sent for session %s",
                    ping_count,
                    session_key[:8],
                )

            except asyncio.CancelledError:
                logger.debug(
                    "Ping loop cancelled for session %s after %d pings",
                    session_key[:8],
                    ping_count,
                )
                raise
            except Exception as e:
                # Log error but don't crash - session might be closing
                logger.debug(
                    "Ping failed for session %s: %s",
                    session_key[:8],
                    e,
                )
                break

        # Clean up task reference
        async with self._ping_task_lock:
            self._ping_tasks.pop(session_key, None)

    async def close(self) -> None:
        """Close all sessions and cancel all ping tasks."""
        # Cancel all ping tasks first
        async with self._ping_task_lock:
            for session_key, task in list(self._ping_tasks.items()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(
                        "Error cancelling ping task for %s: %s",
                        session_key[:8],
                        e,
                    )
            self._ping_tasks.clear()

        # Then close sessions via parent
        await super().close()  # type: ignore[no-untyped-call]
