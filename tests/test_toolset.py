"""Tests for PingEnabledMcpToolset."""

from __future__ import annotations

from unittest.mock import MagicMock

from adk_mcp_ping.session_manager import PingEnabledSessionManager
from adk_mcp_ping.toolset import PingEnabledMcpToolset


class TestPingEnabledMcpToolset:
    """Tests for PingEnabledMcpToolset class."""

    def test_inheritance(self) -> None:
        """Test that PingEnabledMcpToolset inherits from McpToolset."""
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

        assert issubclass(PingEnabledMcpToolset, McpToolset)

    def test_init_creates_ping_enabled_session_manager(
        self, mock_connection_params: MagicMock
    ) -> None:
        """Test that init creates a PingEnabledSessionManager."""
        toolset = PingEnabledMcpToolset(
            connection_params=mock_connection_params,
            ping_interval=30.0,
        )

        assert isinstance(toolset._mcp_session_manager, PingEnabledSessionManager)
        assert toolset._mcp_session_manager._ping_interval == 30.0

    def test_init_default_ping_interval(
        self, mock_connection_params: MagicMock
    ) -> None:
        """Test that default ping interval is 50 seconds."""
        toolset = PingEnabledMcpToolset(
            connection_params=mock_connection_params,
        )

        assert toolset._mcp_session_manager._ping_interval == 50.0

    def test_init_custom_ping_interval(self, mock_connection_params: MagicMock) -> None:
        """Test that custom ping interval is passed through."""
        toolset = PingEnabledMcpToolset(
            connection_params=mock_connection_params,
            ping_interval=25.0,
        )

        assert toolset._mcp_session_manager._ping_interval == 25.0

    def test_stores_ping_interval(self, mock_connection_params: MagicMock) -> None:
        """Test that ping_interval is stored on the toolset."""
        toolset = PingEnabledMcpToolset(
            connection_params=mock_connection_params,
            ping_interval=42.0,
        )

        assert toolset._ping_interval == 42.0


class TestPingEnabledMcpToolsetExports:
    """Test that all expected classes are exported."""

    def test_exports_from_package(self) -> None:
        """Test that classes are exported from the package."""
        from adk_mcp_ping import PingEnabledMcpToolset, PingEnabledSessionManager

        assert PingEnabledMcpToolset is not None
        assert PingEnabledSessionManager is not None

    def test_version_exported(self) -> None:
        """Test that version is exported."""
        from adk_mcp_ping import __version__

        assert __version__ == "0.1.0"

    def test_all_exports(self) -> None:
        """Test __all__ contains expected exports."""
        from adk_mcp_ping import __all__

        assert "PingEnabledMcpToolset" in __all__
        assert "PingEnabledSessionManager" in __all__
