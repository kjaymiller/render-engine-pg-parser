"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_connection(mocker):
    """Create a mock database connection."""
    mock_conn = mocker.MagicMock()
    mock_conn.autocommit = True
    return mock_conn
