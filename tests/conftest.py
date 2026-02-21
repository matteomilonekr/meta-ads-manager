"""Shared test fixtures for Meta Ads MCP."""

from __future__ import annotations

import pytest
import httpx
import respx

from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.client import MetaAdsClient


@pytest.fixture
def auth_config() -> MetaAuthConfig:
    return MetaAuthConfig(
        access_token="test_token_123",
        app_id="test_app_id",
        app_secret="test_app_secret",
    )


@pytest.fixture
def auth_manager(auth_config: MetaAuthConfig) -> AuthManager:
    return AuthManager(auth_config)


@pytest.fixture
def mock_api():
    """Activate respx mock for all httpx requests."""
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.fixture
async def meta_client(auth_manager: AuthManager) -> MetaAdsClient:
    client = MetaAdsClient(auth_manager)
    yield client
    await client.close()
