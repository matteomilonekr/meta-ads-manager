"""Tests for MetaAdsClient."""

from __future__ import annotations

import pytest
import httpx
import respx

from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.models.common import META_GRAPH_URL
from meta_ads_mcp.utils.errors import (
    AuthenticationError,
    MetaAdsMCPError,
    RateLimitError,
    ValidationError,
)


@pytest.fixture
def client() -> MetaAdsClient:
    config = MetaAuthConfig(access_token="test_token")
    auth = AuthManager(config)
    return MetaAdsClient(auth)


@pytest.mark.asyncio
@respx.mock
async def test_get_success(client: MetaAdsClient):
    """Test successful GET request."""
    respx.get(f"{META_GRAPH_URL}/me").mock(
        return_value=httpx.Response(200, json={"id": "123", "name": "Test User"})
    )
    result = await client.get("me")
    assert result["id"] == "123"
    assert result["name"] == "Test User"


@pytest.mark.asyncio
@respx.mock
async def test_post_success(client: MetaAdsClient):
    """Test successful POST request."""
    respx.post(f"{META_GRAPH_URL}/act_123/campaigns").mock(
        return_value=httpx.Response(200, json={"id": "camp_456"})
    )
    result = await client.post("act_123/campaigns", data={"name": "Test"}, account_id="act_123")
    assert result["id"] == "camp_456"


@pytest.mark.asyncio
@respx.mock
async def test_delete_success(client: MetaAdsClient):
    """Test successful DELETE request."""
    respx.delete(f"{META_GRAPH_URL}/camp_456").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    result = await client.delete("camp_456")
    assert result["success"] is True


@pytest.mark.asyncio
@respx.mock
async def test_auth_error(client: MetaAdsClient):
    """Test authentication error handling."""
    respx.get(f"{META_GRAPH_URL}/me").mock(
        return_value=httpx.Response(401, json={
            "error": {
                "message": "Invalid token",
                "type": "OAuthException",
                "code": 190,
            }
        })
    )
    with pytest.raises(AuthenticationError, match="Invalid token"):
        await client.get("me")


@pytest.mark.asyncio
@respx.mock
async def test_validation_error(client: MetaAdsClient):
    """Test validation error handling."""
    respx.post(f"{META_GRAPH_URL}/act_123/campaigns").mock(
        return_value=httpx.Response(400, json={
            "error": {
                "message": "Invalid parameter",
                "type": "FacebookApiException",
                "code": 100,
            }
        })
    )
    with pytest.raises(ValidationError, match="Invalid parameter"):
        await client.post("act_123/campaigns", data={"name": "Test"})


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_error_with_retry(client: MetaAdsClient):
    """Test rate limit error triggers retry and eventually succeeds."""
    respx.get(f"{META_GRAPH_URL}/me").mock(
        side_effect=[
            httpx.Response(429, json={
                "error": {"message": "Rate limit", "type": "OAuthException", "code": 4}
            }),
            httpx.Response(200, json={"id": "123"}),
        ]
    )
    result = await client.get("me")
    assert result["id"] == "123"


@pytest.mark.asyncio
@respx.mock
async def test_get_paginated(client: MetaAdsClient):
    """Test paginated response collection."""
    respx.get(f"{META_GRAPH_URL}/act_123/campaigns").mock(
        side_effect=[
            httpx.Response(200, json={
                "data": [{"id": "1"}, {"id": "2"}],
                "paging": {"cursors": {"after": "cursor_abc"}},
            }),
            httpx.Response(200, json={
                "data": [{"id": "3"}],
                "paging": {"cursors": {}},
            }),
        ]
    )
    items = await client.get_paginated("act_123/campaigns", account_id="act_123")
    assert len(items) == 3
    assert items[0]["id"] == "1"
    assert items[2]["id"] == "3"


@pytest.mark.asyncio
@respx.mock
async def test_get_ad_accounts(client: MetaAdsClient):
    """Test listing ad accounts."""
    respx.get(f"{META_GRAPH_URL}/me/adaccounts").mock(
        return_value=httpx.Response(200, json={
            "data": [
                {"id": "act_111", "name": "Account 1", "account_status": 1},
            ],
            "paging": {},
        })
    )
    accounts = await client.get_ad_accounts()
    assert len(accounts) == 1
    assert accounts[0]["name"] == "Account 1"


@pytest.mark.asyncio
@respx.mock
async def test_validate_token(client: MetaAdsClient):
    """Test token validation."""
    respx.get(f"{META_GRAPH_URL}/me").mock(
        return_value=httpx.Response(200, json={"id": "123", "name": "Test"})
    )
    result = await client.validate_token()
    assert result["id"] == "123"


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_transient_error(client: MetaAdsClient):
    """Test retry on connection errors."""
    respx.get(f"{META_GRAPH_URL}/me").mock(
        side_effect=[
            httpx.ConnectError("Connection refused"),
            httpx.Response(200, json={"id": "123"}),
        ]
    )
    result = await client.get("me")
    assert result["id"] == "123"
