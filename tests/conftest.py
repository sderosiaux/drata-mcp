"""Pytest configuration and fixtures."""

import pytest

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture
def mock_api_key(monkeypatch):
    """Set fake API key for tests."""
    monkeypatch.setenv("DRATA_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("DRATA_REGION", "us")
