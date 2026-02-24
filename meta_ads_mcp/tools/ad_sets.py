"""Ad Set management tools for Meta Ads MCP."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp_use.server import Context

logger = logging.getLogger(__name__)

from meta_ads_mcp.models.common import (
    DEFAULT_ADSET_FIELDS,
    OptimizationGoal,
    BillingEvent,
)
from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, normalize_account_id, safe_get
from meta_ads_mcp.utils.formatting import format_currency, format_table_markdown
from meta_ads_mcp.utils.pagination import paginate_local


@mcp.tool()
async def list_ad_sets(
    account_id: str | None = None,
    campaign_id: str | None = None,
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """List Meta ad sets by account or campaign.

    Args:
        account_id: Ad account ID. Required if campaign_id not provided.
        campaign_id: Campaign ID to filter ad sets.
        status: Filter: all, ACTIVE, PAUSED.
        limit: Max results (1-500).
        offset: Pagination offset.
        response_format: markdown or json.
    """
    client = get_client(ctx)

    if campaign_id:
        parent = campaign_id
    elif account_id:
        parent = normalize_account_id(account_id)
    else:
        return "Error: provide either account_id or campaign_id."

    params: dict = {"fields": ",".join(DEFAULT_ADSET_FIELDS), "limit": str(limit)}
    if status != "all":
        params["effective_status"] = json.dumps([status.upper()])

    ad_sets = await client.get_paginated(
        f"{parent}/adsets", params=params, account_id=account_id,
    )

    rows = []
    for a in ad_sets:
        rows.append({
            "id": safe_get(a, "id"),
            "name": safe_get(a, "name"),
            "status": safe_get(a, "effective_status"),
            "optimization": safe_get(a, "optimization_goal"),
            "daily_budget": format_currency(safe_get(a, "daily_budget", 0)),
            "billing": safe_get(a, "billing_event"),
        })

    page, info = paginate_local(rows, limit, offset)

    if response_format == "json":
        return json.dumps({"ad_sets": page, "pagination": info.to_dict()}, indent=2, ensure_ascii=False)

    columns = ["id", "name", "status", "optimization", "daily_budget", "billing"]
    headers = {"id": "ID", "name": "Name", "status": "Status", "optimization": "Optimization", "daily_budget": "Budget", "billing": "Billing"}
    table = format_table_markdown(page, columns, headers)
    return f"## Ad Sets ({info.count}/{info.total})\n\n{table}"


@mcp.tool()
async def create_ad_set(
    campaign_id: str,
    account_id: str,
    name: str,
    optimization_goal: str,
    billing_event: str,
    daily_budget: int | None = None,
    lifetime_budget: int | None = None,
    bid_amount: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    targeting: Any | None = None,
    promoted_object: Any | None = None,
    ctx: Context = None,
) -> str:
    """Create a new ad set within a campaign.

    Args:
        campaign_id: Parent campaign ID.
        account_id: Ad account ID.
        name: Ad set name.
        optimization_goal: LINK_CLICKS, IMPRESSIONS, REACH, LEAD_GENERATION, OFFSITE_CONVERSIONS, etc.
        billing_event: IMPRESSIONS, LINK_CLICKS, etc.
        daily_budget: Daily budget in cents (provide either daily or lifetime).
        lifetime_budget: Lifetime budget in cents.
        bid_amount: Bid amount in cents (required for some strategies).
        start_time: ISO 8601 start time.
        end_time: ISO 8601 end time (required for lifetime budget).
        targeting: JSON string with targeting spec (e.g. '{"geo_locations":{"countries":["US"]},"age_min":25,"age_max":55}').
        promoted_object: JSON string with promoted object (e.g. '{"page_id":"123456"}').
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    OptimizationGoal(optimization_goal)
    BillingEvent(billing_event)

    # Check if campaign uses CBO (Campaign Budget Optimization).
    # When CBO is active, budget is managed at campaign level — passing
    # daily_budget or lifetime_budget at ad-set level causes an API error.
    uses_cbo = False
    try:
        campaign_data = await client.get(
            campaign_id, params={"fields": "budget_rebalance_flag,daily_budget,lifetime_budget"},
        )
        has_campaign_budget = bool(
            campaign_data.get("daily_budget") or campaign_data.get("lifetime_budget")
        )
        uses_cbo = campaign_data.get("budget_rebalance_flag", False) or has_campaign_budget
    except Exception as exc:
        logger.warning("CBO check failed for campaign %s: %s", campaign_id, exc)

    payload: dict = {
        "campaign_id": campaign_id,
        "name": name,
        "optimization_goal": optimization_goal,
        "billing_event": billing_event,
        "status": "PAUSED",
    }

    if uses_cbo and (daily_budget is not None or lifetime_budget is not None):
        # CBO active: skip ad-set level budget, campaign controls it
        pass
    else:
        if daily_budget is not None:
            payload["daily_budget"] = str(daily_budget)
        if lifetime_budget is not None:
            payload["lifetime_budget"] = str(lifetime_budget)
    if bid_amount is not None:
        payload["bid_amount"] = str(bid_amount)
    if start_time:
        payload["start_time"] = start_time
    if end_time:
        payload["end_time"] = end_time
    if targeting:
        # Meta API expects targeting as a JSON-encoded string in form data
        if isinstance(targeting, dict):
            targeting = json.dumps(targeting)
        elif isinstance(targeting, str):
            json.loads(targeting)  # validate JSON
        payload["targeting"] = targeting
    if promoted_object:
        if isinstance(promoted_object, dict):
            promoted_object = json.dumps(promoted_object)
        elif isinstance(promoted_object, str):
            json.loads(promoted_object)  # validate JSON
        payload["promoted_object"] = promoted_object

    result = await client.post(f"{act_id}/adsets", data=payload, account_id=act_id)
    adset_id = result.get("id", "unknown")
    cbo_note = "\n- **Note**: Budget managed at campaign level (CBO active)" if uses_cbo else ""
    return (
        f"Ad Set created successfully.\n\n"
        f"- **ID**: {adset_id}\n"
        f"- **Name**: {name}\n"
        f"- **Optimization**: {optimization_goal}\n"
        f"- **Status**: PAUSED{cbo_note}"
    )


@mcp.tool()
async def update_ad_set(
    ad_set_id: str,
    name: str | None = None,
    status: str | None = None,
    daily_budget: int | None = None,
    lifetime_budget: int | None = None,
    bid_amount: int | None = None,
    targeting: Any | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    ctx: Context = None,
) -> str:
    """Update an existing ad set.

    Args:
        ad_set_id: Ad set ID to update.
        name: New name.
        status: ACTIVE, PAUSED, DELETED, ARCHIVED.
        daily_budget: New daily budget in cents.
        lifetime_budget: New lifetime budget in cents.
        bid_amount: New bid amount in cents.
        targeting: New targeting spec (JSON string).
        start_time: New start time.
        end_time: New end time.
    """
    client = get_client(ctx)
    payload: dict = {}

    if name is not None:
        payload["name"] = name
    if status is not None:
        payload["status"] = status
    if daily_budget is not None:
        payload["daily_budget"] = str(daily_budget)
    if lifetime_budget is not None:
        payload["lifetime_budget"] = str(lifetime_budget)
    if bid_amount is not None:
        payload["bid_amount"] = str(bid_amount)
    if targeting:
        if isinstance(targeting, dict):
            targeting = json.dumps(targeting)
        payload["targeting"] = targeting
    if start_time:
        payload["start_time"] = start_time
    if end_time:
        payload["end_time"] = end_time

    if not payload:
        return "No updates specified."

    await client.post(ad_set_id, data=payload)
    updates = ", ".join(f"**{k}**: {v}" for k, v in payload.items())
    return f"Ad Set `{ad_set_id}` updated: {updates}"


@mcp.tool()
async def pause_ad_set(ad_set_id: str, ctx: Context = None) -> str:
    """Pause an ad set.

    Args:
        ad_set_id: Ad set ID to pause.
    """
    client = get_client(ctx)
    await client.post(ad_set_id, data={"status": "PAUSED"})
    return f"Ad Set `{ad_set_id}` paused."


@mcp.tool()
async def delete_ad_set(ad_set_id: str, ctx: Context = None) -> str:
    """Delete an ad set.

    Args:
        ad_set_id: Ad set ID to delete.
    """
    client = get_client(ctx)
    await client.delete(ad_set_id)
    return f"Ad Set `{ad_set_id}` deleted."
