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

logger = logging.getLogger(__name__)

# AWS ALB default idle timeout is 60s; ping before that to keep connections alive
DEFAULT_PING_INTERVAL_SECONDS = 50.0
SESSION_KEY_LOG_LENGTH = 8


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
        ping_interval: float = DEFAULT_PING_INTERVAL_SECONDS,
        errlog: TextIO = sys.stderr,
    ) -> None:
        """Initialize the ping-enabled session manager.

        Args:
            connection_params: Parameters for the MCP connection.
            ping_interval: Seconds between keep-alive pings.
            errlog: Stream for error logging.
        """
        super().__init__(connection_params=connection_params, errlog=errlog)
        self._ping_interval = ping_interval
        self._ping_tasks: dict[str, asyncio.Task[Any]] = {}
        self._ping_task_lock = asyncio.Lock()

    async def create_session(
        self, headers: dict[str, str] | None = None
    ) -> ClientSession:
        """Create a session and start a ping task for it."""
        session = await super().create_session(headers=headers)
        session_key = self._get_session_key(headers)
        await self._start_ping_task_if_needed(session, session_key)
        return session

    def _get_session_key(self, headers: dict[str, str] | None) -> str:
        """Generate the session key from headers."""
        merged_headers = self._merge_headers(headers)
        return self._generate_session_key(merged_headers)

    def _short_key(self, session_key: str) -> str:
        """Return truncated session key for logging."""
        return session_key[:SESSION_KEY_LOG_LENGTH]

    async def _start_ping_task_if_needed(
        self, session: ClientSession, session_key: str
    ) -> None:
        """Start a ping task for the session if one isn't already running."""
        async with self._ping_task_lock:
            if session_key not in self._ping_tasks:
                task = asyncio.create_task(
                    self._ping_loop(session, session_key),
                    name=f"ping_loop_{self._short_key(session_key)}",
                )
                self._ping_tasks[session_key] = task
                logger.debug(
                    "Started ping task for session %s (interval: %.1fs)",
                    self._short_key(session_key),
                    self._ping_interval,
                )

    async def _ping_loop(self, session: ClientSession, session_key: str) -> None:
        """Send periodic pings until the session disconnects or is cancelled."""
        short_key = self._short_key(session_key)
        ping_count = 0

        try:
            while True:
                await asyncio.sleep(self._ping_interval)

                if self._is_session_disconnected(session):
                    logger.debug("Session %s disconnected, stopping pings", short_key)
                    break

                ping_count += 1
                await session.send_ping()
                logger.debug("Ping #%d sent for session %s", ping_count, short_key)

        except asyncio.CancelledError:
            logger.debug(
                "Ping loop cancelled for session %s after %d pings",
                short_key,
                ping_count,
            )
            raise
        except Exception as e:
            logger.debug("Ping failed for session %s: %s", short_key, e)
        finally:
            await self._cleanup_ping_task(session_key)

    async def _cleanup_ping_task(self, session_key: str) -> None:
        """Remove the ping task reference for a session."""
        async with self._ping_task_lock:
            self._ping_tasks.pop(session_key, None)

    async def close(self) -> None:
        """Cancel all ping tasks and close sessions."""
        await self._cancel_all_ping_tasks()
        await super().close()  # type: ignore[no-untyped-call]

    async def _cancel_all_ping_tasks(self) -> None:
        """Cancel and await all running ping tasks."""
        # Take snapshot and clear under lock to avoid deadlock with _cleanup_ping_task
        async with self._ping_task_lock:
            tasks_to_cancel = list(self._ping_tasks.items())
            self._ping_tasks.clear()

        # Cancel and await outside the lock
        for session_key, task in tasks_to_cancel:
            task.cancel()
            await self._await_task_cancellation(task, session_key)

    async def _await_task_cancellation(
        self, task: asyncio.Task[Any], session_key: str
    ) -> None:
        """Await a cancelled task, logging any unexpected errors."""
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(
                "Error cancelling ping task for %s: %s",
                self._short_key(session_key),
                e,
            )
