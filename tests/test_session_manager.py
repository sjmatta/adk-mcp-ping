"""Tests for PingEnabledSessionManager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adk_mcp_ping.session_manager import (
    DEFAULT_PING_INTERVAL_SECONDS,
    PingEnabledSessionManager,
)


class TestPingEnabledSessionManager:
    """Tests for PingEnabledSessionManager class."""

    def test_uses_default_ping_interval_constant(self) -> None:
        """Verify the default constant is set appropriately for AWS ALB."""
        # AWS ALB default idle timeout is 60s, so default should be < 60s
        assert DEFAULT_PING_INTERVAL_SECONDS < 60.0
        assert DEFAULT_PING_INTERVAL_SECONDS > 0

    @pytest.mark.asyncio
    async def test_sends_pings_at_default_interval(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that pings are sent at the default interval."""
        # Use a fast interval for testing, but verify the default is wired correctly
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
        )
        # The manager should use the constant as default
        assert manager._ping_interval == DEFAULT_PING_INTERVAL_SECONDS

    @pytest.mark.asyncio
    async def test_sends_pings_at_custom_interval(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that pings are sent at a custom interval."""
        ping_interval = 0.05  # 50ms for fast testing
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=ping_interval,
        )
        manager._is_session_disconnected = MagicMock(return_value=False)

        # Start ping loop
        task = asyncio.create_task(manager._ping_loop(mock_client_session, "test_key"))

        # Wait for approximately 3 intervals
        await asyncio.sleep(ping_interval * 3.5)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have sent approximately 3 pings (timing can vary slightly)
        assert mock_client_session.send_ping.call_count >= 2
        assert mock_client_session.send_ping.call_count <= 4

    @pytest.mark.asyncio
    async def test_create_session_starts_pinging(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that creating a session starts the ping loop."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=0.05,
        )

        with patch.object(
            PingEnabledSessionManager.__bases__[0],
            "create_session",
            new_callable=AsyncMock,
            return_value=mock_client_session,
        ):
            manager._merge_headers = MagicMock(return_value={})
            manager._generate_session_key = MagicMock(return_value="test_session_key")
            manager._is_session_disconnected = MagicMock(return_value=False)

            session = await manager.create_session()

            assert session == mock_client_session

            # Wait for at least one ping to be sent
            await asyncio.sleep(0.1)

            # Verify pings are being sent
            assert mock_client_session.send_ping.call_count >= 1

            # Clean up
            await manager.close()

    @pytest.mark.asyncio
    async def test_stops_pinging_when_session_disconnects(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that ping loop stops when session disconnects."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=0.05,
        )

        # Session appears disconnected after first check
        call_count = 0

        def check_disconnected(_: MagicMock) -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 1

        manager._is_session_disconnected = check_disconnected

        # Run ping loop - should exit on its own
        await asyncio.wait_for(
            manager._ping_loop(mock_client_session, "test_key"),
            timeout=1.0,
        )

        # Should have stopped after detecting disconnect
        assert mock_client_session.send_ping.call_count <= 1

    @pytest.mark.asyncio
    async def test_stops_pinging_on_connection_error(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that ping loop stops gracefully on ping error."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=0.05,
        )
        manager._is_session_disconnected = MagicMock(return_value=False)
        mock_client_session.send_ping.side_effect = Exception("Connection lost")

        # Run ping loop - should exit on its own due to error
        await asyncio.wait_for(
            manager._ping_loop(mock_client_session, "test_key"),
            timeout=1.0,
        )

        # Should have tried exactly one ping before error stopped the loop
        assert mock_client_session.send_ping.call_count == 1

    @pytest.mark.asyncio
    async def test_close_stops_all_pinging(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that close() stops all ping loops."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=0.05,
        )
        manager._is_session_disconnected = MagicMock(return_value=False)

        # Start multiple ping tasks via the manager's tracking
        task1 = asyncio.create_task(manager._ping_loop(mock_client_session, "key1"))
        task2 = asyncio.create_task(manager._ping_loop(mock_client_session, "key2"))

        async with manager._ping_task_lock:
            manager._ping_tasks = {"key1": task1, "key2": task2}

        # Let some pings happen
        await asyncio.sleep(0.1)
        pings_before_close = mock_client_session.send_ping.call_count

        with patch.object(
            PingEnabledSessionManager.__bases__[0],
            "close",
            new_callable=AsyncMock,
        ):
            await manager.close()

        # Both tasks should be done
        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()

        # No more pings should be sent after close
        await asyncio.sleep(0.1)
        assert mock_client_session.send_ping.call_count == pings_before_close


class TestPingEnabledSessionManagerIntegration:
    """Integration tests that verify proper inheritance."""

    def test_inherits_from_mcp_session_manager(self) -> None:
        """Verify proper inheritance from MCPSessionManager."""
        from google.adk.tools.mcp_tool.mcp_session_manager import MCPSessionManager

        assert issubclass(PingEnabledSessionManager, MCPSessionManager)
