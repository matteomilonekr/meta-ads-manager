"""OAuth and token management tools for Meta Ads MCP."""

from __future__ import annotations

import json
import logging

from mcp_use.server import Context

logger = logging.getLogger(__name__)

from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, get_auth


@mcp.tool()
async def generate_auth_url(
    scopes: str | None = None,
    state: str | None = None,
    ctx: Context = None,
) -> str:
    """Generate Facebook OAuth authorization URL for connecting Meta Ads.

    Open this URL in a browser to authorize access.

    Args:
        scopes: Comma-separated OAuth scopes (default: ads_management, ads_read, business_management).
        state: Optional CSRF state parameter.
    """
    auth = get_auth(ctx)
    scope_list = [s.strip() for s in scopes.split(",")] if scopes else None
    url = auth.generate_oauth_url(scopes=scope_list, state=state)
    return (
        f"## OAuth Authorization\n\n"
        f"Open this URL in your browser to authorize:\n\n"
        f"```\n{url}\n```\n\n"
        f"After authorization, you'll be redirected with a `code` parameter. "
        f"Use `exchange_code_for_token` with that code."
    )


@mcp.tool()
async def exchange_code_for_token(
    code: str,
    ctx: Context = None,
) -> str:
    """Exchange an OAuth authorization code for an access token.

    Args:
        code: The authorization code from the OAuth redirect.
    """
    client = get_client(ctx)
    auth = get_auth(ctx)
    params = auth.get_token_exchange_params(code)
    result = await client.get("oauth/access_token", params=params)

    token = result.get("access_token", "")
    token_type = result.get("token_type", "bearer")
    expires_in = result.get("expires_in", "unknown")

    # Mask token for display
    masked = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "***"

    return (
        f"Token obtained successfully.\n\n"
        f"- **Token**: `{masked}`\n"
        f"- **Type**: {token_type}\n"
        f"- **Expires in**: {expires_in} seconds\n\n"
        f"Set this as your `META_ACCESS_TOKEN` environment variable.\n"
        f"Use `refresh_to_long_lived_token` to extend to 60 days."
    )


@mcp.tool()
async def refresh_to_long_lived_token(
    short_lived_token: str | None = None,
    ctx: Context = None,
) -> str:
    """Convert a short-lived token to a long-lived (60-day) token.

    Args:
        short_lived_token: Short-lived token to exchange. Uses current token if not provided.
    """
    client = get_client(ctx)
    auth = get_auth(ctx)
    params = auth.get_long_lived_token_params(short_lived_token)
    result = await client.get("oauth/access_token", params=params)

    token = result.get("access_token", "")
    token_type = result.get("token_type", "bearer")
    expires_in = result.get("expires_in", "unknown")

    masked = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "***"

    return (
        f"Long-lived token obtained.\n\n"
        f"- **Token**: `{masked}`\n"
        f"- **Type**: {token_type}\n"
        f"- **Expires in**: {expires_in} seconds (~60 days)\n\n"
        f"Update your `META_ACCESS_TOKEN` with this new token."
    )


@mcp.tool()
async def get_token_info(ctx: Context = None) -> str:
    """Get information about the current access token (validity, scopes, expiry).
    """
    client = get_client(ctx)
    auth = get_auth(ctx)

    if not auth.app_id or not auth.app_secret:
        # Fallback: just validate with /me
        result = await client.get("me")
        name = result.get("name", "Unknown")
        user_id = result.get("id", "Unknown")
        return (
            f"## Token Info (basic)\n\n"
            f"- **User**: {name} ({user_id})\n"
            f"- **Status**: Valid\n\n"
            f"_Set META_APP_ID and META_APP_SECRET for full token debug info._"
        )

    params = {
        "input_token": auth.access_token,
        "access_token": f"{auth.app_id}|{auth.app_secret}",
    }
    result = await client.get("debug_token", params=params)
    data = result.get("data", {})

    is_valid = data.get("is_valid", False)
    app_id = data.get("app_id", "N/A")
    scopes = ", ".join(data.get("scopes", []))
    expires_at = data.get("expires_at", 0)
    user_id = data.get("user_id", "N/A")

    import datetime
    if expires_at:
        expiry = datetime.datetime.fromtimestamp(expires_at, tz=datetime.timezone.utc).isoformat()
    else:
        expiry = "Never (system token)"

    return (
        f"## Token Debug Info\n\n"
        f"- **Valid**: {'Yes' if is_valid else 'No'}\n"
        f"- **App ID**: {app_id}\n"
        f"- **User ID**: {user_id}\n"
        f"- **Scopes**: {scopes}\n"
        f"- **Expires**: {expiry}"
    )


@mcp.tool()
async def validate_token(ctx: Context = None) -> str:
    """Quick validation — check if the current token works.
    """
    client = get_client(ctx)
    try:
        result = await client.validate_token()
        name = result.get("name", "Unknown")
        user_id = result.get("id", "Unknown")
        return f"Token is valid. User: **{name}** (ID: {user_id})"
    except Exception as exc:
        logger.error("Token validation failed: %s", exc)
        return f"Token is **invalid** or expired: {exc}"
