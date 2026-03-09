"""Shared helpers for Meta Ads MCP tools."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Context

logger = logging.getLogger(__name__)

from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.auth import AuthManager


def get_client(ctx: Context | None) -> MetaAdsClient:
    """Extract MetaAdsClient from MCP context."""
    if ctx is None:
        raise RuntimeError("MCP context required — cannot get Meta client")
    return ctx.lifespan_context["meta_client"]


def get_auth(ctx: Context | None) -> AuthManager:
    """Extract AuthManager from MCP context."""
    if ctx is None:
        raise RuntimeError("MCP context required — cannot get auth manager")
    return ctx.lifespan_context["auth"]


def normalize_account_id(account_id: str) -> str:
    """Ensure account ID has 'act_' prefix and numeric body."""
    account_id = account_id.strip()
    if account_id.startswith("act_"):
        numeric = account_id[4:]
    else:
        numeric = account_id
    if not numeric or not numeric.isdigit():
        raise ValueError(f"Invalid account ID — expected numeric value, got: {account_id!r}")
    return f"act_{numeric}"


def safe_get(data: dict[str, Any], key: str, default: Any = "") -> Any:
    """Safely get a value from a dict."""
    value = data.get(key)
    return value if value is not None else default
