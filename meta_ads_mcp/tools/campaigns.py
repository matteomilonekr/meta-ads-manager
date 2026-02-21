"""Campaign management tools for Meta Ads MCP."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from meta_ads_mcp.models.common import (
    DEFAULT_CAMPAIGN_FIELDS,
    CampaignObjective,
    CampaignStatus,
    BidStrategy,
)
from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, normalize_account_id, safe_get
from meta_ads_mcp.utils.formatting import format_currency, format_table_markdown
from meta_ads_mcp.utils.pagination import paginate_local


@mcp.tool()
async def list_campaigns(
    account_id: str,
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """List Meta/Facebook ad campaigns with optional status filter.

    Args:
        account_id: Ad account ID (e.g. '123456789' or 'act_123456789').
        status: Filter: all, ACTIVE, PAUSED, DELETED, ARCHIVED.
        limit: Max results (1-500, default 50).
        offset: Starting offset for pagination.
        response_format: Output format: markdown or json.
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    params: dict = {"fields": ",".join(DEFAULT_CAMPAIGN_FIELDS), "limit": str(limit)}
    if status != "all":
        params["effective_status"] = json.dumps([status.upper()])

    campaigns = await client.get_paginated(
        f"{act_id}/campaigns", params=params, account_id=act_id,
    )

    rows = []
    for c in campaigns:
        rows.append({
            "id": safe_get(c, "id"),
            "name": safe_get(c, "name"),
            "objective": safe_get(c, "objective"),
            "status": safe_get(c, "effective_status"),
            "daily_budget": format_currency(safe_get(c, "daily_budget", 0)),
            "lifetime_budget": format_currency(safe_get(c, "lifetime_budget", 0)),
        })

    page, info = paginate_local(rows, limit, offset)

    if response_format == "json":
        return json.dumps({"campaigns": page, "pagination": info.to_dict()}, indent=2, ensure_ascii=False)

    columns = ["id", "name", "objective", "status", "daily_budget"]
    headers = {"id": "ID", "name": "Name", "objective": "Objective", "status": "Status", "daily_budget": "Daily Budget"}
    table = format_table_markdown(page, columns, headers)
    return f"## Campaigns ({info.count}/{info.total})\n\n{table}\n\n_Showing {info.count} of {info.total}{' (more available)' if info.has_more else ''}_"


@mcp.tool()
async def create_campaign(
    account_id: str,
    name: str,
    objective: str,
    daily_budget: int | None = None,
    lifetime_budget: int | None = None,
    bid_strategy: str = "LOWEST_COST_WITHOUT_CAP",
    special_ad_categories: str = "NONE",
    start_time: str | None = None,
    stop_time: str | None = None,
    ctx: Context = None,
) -> str:
    """Create a new Meta ad campaign (created as PAUSED by default).

    Args:
        account_id: Ad account ID.
        name: Campaign name.
        objective: Campaign objective (OUTCOME_AWARENESS, OUTCOME_ENGAGEMENT, OUTCOME_LEADS, OUTCOME_SALES, OUTCOME_TRAFFIC, OUTCOME_APP_PROMOTION).
        daily_budget: Daily budget in cents (e.g., 5000 = $50.00). Provide either daily or lifetime.
        lifetime_budget: Lifetime budget in cents.
        bid_strategy: LOWEST_COST_WITHOUT_CAP, LOWEST_COST_WITH_BID_CAP, COST_CAP, LOWEST_COST_WITH_MIN_ROAS.
        special_ad_categories: NONE, EMPLOYMENT, HOUSING, CREDIT, ISSUES_ELECTIONS_POLITICS (comma-separated if multiple).
        start_time: ISO 8601 start time.
        stop_time: ISO 8601 stop time (required for lifetime budget).
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    # Validate objective
    CampaignObjective(objective)
    BidStrategy(bid_strategy)

    payload: dict = {
        "name": name,
        "objective": objective,
        "status": "PAUSED",
        "bid_strategy": bid_strategy,
        "special_ad_categories": json.dumps(
            [c.strip() for c in special_ad_categories.split(",") if c.strip() != "NONE"]
        ),
    }
    if daily_budget is not None:
        payload["daily_budget"] = str(daily_budget)
    if lifetime_budget is not None:
        payload["lifetime_budget"] = str(lifetime_budget)
    if start_time:
        payload["start_time"] = start_time
    if stop_time:
        payload["stop_time"] = stop_time

    result = await client.post(f"{act_id}/campaigns", data=payload, account_id=act_id)
    campaign_id = result.get("id", "unknown")
    return f"Campaign created successfully.\n\n- **ID**: {campaign_id}\n- **Name**: {name}\n- **Objective**: {objective}\n- **Status**: PAUSED\n- **Budget**: {format_currency(daily_budget or lifetime_budget or 0)}"


@mcp.tool()
async def update_campaign(
    campaign_id: str,
    name: str | None = None,
    status: str | None = None,
    daily_budget: int | None = None,
    lifetime_budget: int | None = None,
    start_time: str | None = None,
    stop_time: str | None = None,
    ctx: Context = None,
) -> str:
    """Update an existing Meta ad campaign.

    Args:
        campaign_id: Campaign ID to update.
        name: New campaign name.
        status: New status (ACTIVE, PAUSED, DELETED, ARCHIVED).
        daily_budget: New daily budget in cents.
        lifetime_budget: New lifetime budget in cents.
        start_time: New start time (ISO 8601).
        stop_time: New stop time (ISO 8601).
    """
    client = get_client(ctx)
    payload: dict = {}

    if name is not None:
        payload["name"] = name
    if status is not None:
        CampaignStatus(status)
        payload["status"] = status
    if daily_budget is not None:
        payload["daily_budget"] = str(daily_budget)
    if lifetime_budget is not None:
        payload["lifetime_budget"] = str(lifetime_budget)
    if start_time:
        payload["start_time"] = start_time
    if stop_time:
        payload["stop_time"] = stop_time

    if not payload:
        return "No updates specified."

    await client.post(campaign_id, data=payload)
    updates = ", ".join(f"**{k}**: {v}" for k, v in payload.items())
    return f"Campaign `{campaign_id}` updated: {updates}"


@mcp.tool()
async def pause_campaign(campaign_id: str, ctx: Context = None) -> str:
    """Pause a Meta ad campaign.

    Args:
        campaign_id: Campaign ID to pause.
    """
    client = get_client(ctx)
    await client.post(campaign_id, data={"status": "PAUSED"})
    return f"Campaign `{campaign_id}` paused."


@mcp.tool()
async def resume_campaign(campaign_id: str, ctx: Context = None) -> str:
    """Resume (activate) a paused Meta ad campaign.

    Args:
        campaign_id: Campaign ID to activate.
    """
    client = get_client(ctx)
    await client.post(campaign_id, data={"status": "ACTIVE"})
    return f"Campaign `{campaign_id}` resumed (ACTIVE)."


@mcp.tool()
async def delete_campaign(campaign_id: str, ctx: Context = None) -> str:
    """Delete a Meta ad campaign.

    Args:
        campaign_id: Campaign ID to delete.
    """
    client = get_client(ctx)
    await client.delete(campaign_id)
    return f"Campaign `{campaign_id}` deleted."
