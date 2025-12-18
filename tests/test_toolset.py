"""Tests for PingEnabledMcpToolset."""

from __future__ import annotations

from unittest.mock import MagicMock

from adk_mcp_ping.session_manager import (
    DEFAULT_PING_INTERVAL_SECONDS,
    PingEnabledSessionManager,
)
from adk_mcp_ping.toolset import PingEnabledMcpToolset


class TestPingEnabledMcpToolset:
    """Tests for PingEnabledMcpToolset class."""

    def test_inherits_from_mcp_toolset(self) -> None:
        """Verify proper inheritance from McpToolset."""
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

        assert issubclass(PingEnabledMcpToolset, McpToolset)

    def test_uses_ping_enabled_session_manager(
        self, mock_connection_params: MagicMock
    ) -> None:
        """Verify toolset creates a PingEnabledSessionManager."""
        toolset = PingEnabledMcpToolset(
            connection_params=mock_connection_params,
        )

        assert isinstance(toolset._mcp_session_manager, PingEnabledSessionManager)

    def test_passes_ping_interval_to_session_manager(
        self, mock_connection_params: MagicMock
    ) -> None:
        """Verify custom ping interval is passed to the session manager."""
        custom_interval = 25.0
        toolset = PingEnabledMcpToolset(
            connection_params=mock_connection_params,
            ping_interval=custom_interval,
        )

        # The session manager should receive the custom interval
        assert toolset._mcp_session_manager._ping_interval == custom_interval

    def test_uses_default_ping_interval(
        self, mock_connection_params: MagicMock
    ) -> None:
        """Verify default ping interval matches the constant."""
        toolset = PingEnabledMcpToolset(
            connection_params=mock_connection_params,
        )

        assert (
            toolset._mcp_session_manager._ping_interval == DEFAULT_PING_INTERVAL_SECONDS
        )


class TestPingEnabledMcpToolsetExports:
    """Test that all expected classes are exported from the package."""

    def test_exports_main_classes(self) -> None:
        """Verify main classes are exported from the package."""
        from adk_mcp_ping import PingEnabledMcpToolset, PingEnabledSessionManager

        assert PingEnabledMcpToolset is not None
        assert PingEnabledSessionManager is not None

    def test_exports_version(self) -> None:
        """Verify version is exported."""
        from adk_mcp_ping import __version__

        assert __version__ == "0.1.0"

    def test_all_contains_expected_exports(self) -> None:
        """Verify __all__ contains expected exports."""
        from adk_mcp_ping import __all__

        assert "PingEnabledMcpToolset" in __all__
        assert "PingEnabledSessionManager" in __all__
