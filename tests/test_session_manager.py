"""Tests for PingEnabledSessionManager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adk_mcp_ping.session_manager import PingEnabledSessionManager


class TestPingEnabledSessionManager:
    """Tests for PingEnabledSessionManager class."""

    def test_init_default_ping_interval(
        self, mock_connection_params: MagicMock
    ) -> None:
        """Test default ping interval is 50 seconds."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
        )
        assert manager._ping_interval == 50.0

    def test_init_custom_ping_interval(self, mock_connection_params: MagicMock) -> None:
        """Test custom ping interval is respected."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=30.0,
        )
        assert manager._ping_interval == 30.0

    def test_init_creates_empty_ping_tasks(
        self, mock_connection_params: MagicMock
    ) -> None:
        """Test ping tasks dict is initialized empty."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
        )
        assert manager._ping_tasks == {}

    @pytest.mark.asyncio
    async def test_create_session_starts_ping_task(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that create_session starts a ping task."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=0.1,  # Fast for testing
        )

        # Mock parent's create_session
        with patch.object(
            PingEnabledSessionManager.__bases__[0],
            "create_session",
            new_callable=AsyncMock,
            return_value=mock_client_session,
        ):
            # Mock helper methods
            manager._merge_headers = MagicMock(return_value={})
            manager._generate_session_key = MagicMock(return_value="test_session_key")
            manager._is_session_disconnected = MagicMock(return_value=False)

            session = await manager.create_session()

            assert session == mock_client_session
            assert "test_session_key" in manager._ping_tasks
            assert isinstance(manager._ping_tasks["test_session_key"], asyncio.Task)

            # Clean up
            manager._ping_tasks["test_session_key"].cancel()
            try:
                await manager._ping_tasks["test_session_key"]
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_ping_loop_sends_pings(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that ping loop sends pings at the specified interval."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=0.05,  # 50ms for fast testing
        )
        manager._is_session_disconnected = MagicMock(return_value=False)

        # Start ping loop in background
        task = asyncio.create_task(manager._ping_loop(mock_client_session, "test_key"))

        # Wait for a few pings
        await asyncio.sleep(0.15)

        # Cancel and verify
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have sent 2-3 pings in 150ms with 50ms interval
        assert mock_client_session.send_ping.call_count >= 2

    @pytest.mark.asyncio
    async def test_ping_loop_stops_on_disconnect(
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
            return call_count > 1  # Disconnected after first ping attempt

        manager._is_session_disconnected = check_disconnected

        # Run ping loop - should exit on its own
        await asyncio.wait_for(
            manager._ping_loop(mock_client_session, "test_key"),
            timeout=1.0,
        )

        # Should have only attempted one ping before detecting disconnect
        assert mock_client_session.send_ping.call_count <= 1

    @pytest.mark.asyncio
    async def test_ping_loop_stops_on_error(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that ping loop stops on ping error."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=0.05,
        )
        manager._is_session_disconnected = MagicMock(return_value=False)

        # Make ping raise an error
        mock_client_session.send_ping.side_effect = Exception("Connection lost")

        # Run ping loop - should exit on its own due to error
        await asyncio.wait_for(
            manager._ping_loop(mock_client_session, "test_key"),
            timeout=1.0,
        )

        # Should have tried to send exactly one ping before error
        assert mock_client_session.send_ping.call_count == 1

    @pytest.mark.asyncio
    async def test_close_cancels_all_ping_tasks(
        self, mock_connection_params: MagicMock, mock_client_session: MagicMock
    ) -> None:
        """Test that close() cancels all running ping tasks."""
        manager = PingEnabledSessionManager(
            connection_params=mock_connection_params,
            ping_interval=10.0,  # Long interval so task stays running
        )
        manager._is_session_disconnected = MagicMock(return_value=False)

        # Create multiple ping tasks
        task1 = asyncio.create_task(manager._ping_loop(mock_client_session, "key1"))
        task2 = asyncio.create_task(manager._ping_loop(mock_client_session, "key2"))
        manager._ping_tasks = {"key1": task1, "key2": task2}

        # Mock parent close
        with patch.object(
            PingEnabledSessionManager.__bases__[0],
            "close",
            new_callable=AsyncMock,
        ):
            await manager.close()

        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()
        assert manager._ping_tasks == {}


class TestPingEnabledSessionManagerIntegration:
    """Integration tests that don't mock the parent class."""

    def test_inheritance(self) -> None:
        """Test that PingEnabledSessionManager inherits from MCPSessionManager."""
        from google.adk.tools.mcp_tool.mcp_session_manager import MCPSessionManager

        assert issubclass(PingEnabledSessionManager, MCPSessionManager)
