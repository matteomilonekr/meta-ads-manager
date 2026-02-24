"""Shared helpers for Meta Ads MCP tools."""

from __future__ import annotations

import logging
from typing import Any

from mcp_use.server import Context

logger = logging.getLogger(__name__)

from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.auth import AuthManager


def get_client(ctx: Context | None) -> MetaAdsClient:
    """Extract MetaAdsClient from MCP context."""
    if ctx is None:
        raise RuntimeError("MCP context required — cannot get Meta client")
    return ctx.request_context.lifespan_context["meta_client"]


def get_auth(ctx: Context | None) -> AuthManager:
    """Extract AuthManager from MCP context."""
    if ctx is None:
        raise RuntimeError("MCP context required — cannot get auth manager")
    return ctx.request_context.lifespan_context["auth"]


def normalize_account_id(account_id: str) -> str:
    """Ensure account ID has 'act_' prefix."""
    account_id = account_id.strip()
    if not account_id.startswith("act_"):
        return f"act_{account_id}"
    return account_id


def safe_get(data: dict[str, Any], key: str, default: Any = "") -> Any:
    """Safely get a value from a dict."""
    value = data.get(key)
    return value if value is not None else default
