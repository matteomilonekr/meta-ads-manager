"""Ad management tools for Meta Ads MCP."""

from __future__ import annotations

import json
import logging

from mcp_use.server import Context

logger = logging.getLogger(__name__)

from meta_ads_mcp.models.common import DEFAULT_AD_FIELDS
from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, normalize_account_id, safe_get
from meta_ads_mcp.utils.formatting import format_table_markdown
from meta_ads_mcp.utils.pagination import paginate_local


@mcp.tool()
async def list_ads(
    account_id: str | None = None,
    campaign_id: str | None = None,
    ad_set_id: str | None = None,
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """List Meta ads by account, campaign, or ad set.

    Args:
        account_id: Ad account ID.
        campaign_id: Filter by campaign.
        ad_set_id: Filter by ad set.
        status: Filter: all, ACTIVE, PAUSED.
        limit: Max results (1-500).
        offset: Pagination offset.
        response_format: markdown or json.
    """
    client = get_client(ctx)

    if ad_set_id:
        parent = ad_set_id
    elif campaign_id:
        parent = campaign_id
    elif account_id:
        parent = normalize_account_id(account_id)
    else:
        return "Error: provide account_id, campaign_id, or ad_set_id."

    params: dict = {"fields": ",".join(DEFAULT_AD_FIELDS), "limit": str(limit)}
    if status != "all":
        params["effective_status"] = json.dumps([status.upper()])

    ads = await client.get_paginated(
        f"{parent}/ads", params=params, account_id=account_id,
    )

    rows = []
    for ad in ads:
        creative = ad.get("creative", {})
        rows.append({
            "id": safe_get(ad, "id"),
            "name": safe_get(ad, "name"),
            "status": safe_get(ad, "effective_status"),
            "adset_id": safe_get(ad, "adset_id"),
            "creative_id": safe_get(creative, "id"),
        })

    page, info = paginate_local(rows, limit, offset)

    if response_format == "json":
        return json.dumps({"ads": page, "pagination": info.to_dict()}, indent=2, ensure_ascii=False)

    columns = ["id", "name", "status", "adset_id", "creative_id"]
    headers = {"id": "ID", "name": "Name", "status": "Status", "adset_id": "Ad Set", "creative_id": "Creative"}
    table = format_table_markdown(page, columns, headers)
    return f"## Ads ({info.count}/{info.total})\n\n{table}"


@mcp.tool()
async def create_ad(
    ad_set_id: str,
    account_id: str,
    name: str,
    creative_id: str,
    ctx: Context = None,
) -> str:
    """Create a new ad by linking a creative to an ad set.

    Args:
        ad_set_id: Ad set ID where the ad will be placed.
        account_id: Ad account ID.
        name: Ad name.
        creative_id: ID of the creative to use.
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    payload = {
        "name": name,
        "adset_id": ad_set_id,
        "creative": json.dumps({"creative_id": creative_id}),
        "status": "PAUSED",
    }

    result = await client.post(f"{act_id}/ads", data=payload, account_id=act_id)
    ad_id = result.get("id", "unknown")
    return (
        f"Ad created successfully.\n\n"
        f"- **ID**: {ad_id}\n"
        f"- **Name**: {name}\n"
        f"- **Ad Set**: {ad_set_id}\n"
        f"- **Creative**: {creative_id}\n"
        f"- **Status**: PAUSED"
    )


@mcp.tool()
async def update_ad(
    ad_id: str,
    name: str | None = None,
    status: str | None = None,
    creative_id: str | None = None,
    ctx: Context = None,
) -> str:
    """Update an existing ad.

    Args:
        ad_id: Ad ID to update.
        name: New ad name.
        status: ACTIVE, PAUSED, DELETED, ARCHIVED.
        creative_id: New creative ID to link.
    """
    client = get_client(ctx)
    payload: dict = {}

    if name is not None:
        payload["name"] = name
    if status is not None:
        payload["status"] = status
    if creative_id is not None:
        payload["creative"] = json.dumps({"creative_id": creative_id})

    if not payload:
        return "No updates specified."

    await client.post(ad_id, data=payload)
    updates = ", ".join(f"**{k}**: {v}" for k, v in payload.items())
    return f"Ad `{ad_id}` updated: {updates}"


@mcp.tool()
async def delete_ad(ad_id: str, ctx: Context = None) -> str:
    """Delete an ad.

    Args:
        ad_id: Ad ID to delete.
    """
    client = get_client(ctx)
    await client.delete(ad_id)
    return f"Ad `{ad_id}` deleted."
