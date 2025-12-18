"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_client_session() -> MagicMock:
    """Create a mock MCP ClientSession."""
    session = MagicMock()
    session.send_ping = AsyncMock(return_value=None)
    return session


@pytest.fixture
def mock_connection_params() -> MagicMock:
    """Create mock connection parameters."""
    params = MagicMock()
    params.url = "http://localhost:8000/mcp"
    return params
