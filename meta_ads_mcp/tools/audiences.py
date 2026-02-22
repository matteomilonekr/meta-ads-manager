"""Audience management tools for Meta Ads MCP."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from meta_ads_mcp.models.common import DEFAULT_AUDIENCE_FIELDS, AudienceSubtype
from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, normalize_account_id, safe_get
from meta_ads_mcp.utils.formatting import format_number, format_table_markdown
from meta_ads_mcp.utils.pagination import paginate_local


@mcp.tool()
async def list_audiences(
    account_id: str,
    subtype: str | None = None,
    limit: int = 50,
    offset: int = 0,
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """List custom and lookalike audiences for an ad account.

    Args:
        account_id: Ad account ID.
        subtype: Filter by type: CUSTOM, WEBSITE, APP, LOOKALIKE, VIDEO, ENGAGEMENT.
        limit: Max results.
        offset: Pagination offset.
        response_format: markdown or json.
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    params: dict = {"fields": ",".join(DEFAULT_AUDIENCE_FIELDS), "limit": str(limit)}
    if subtype:
        AudienceSubtype(subtype)
        params["filtering"] = json.dumps([{
            "field": "subtype",
            "operator": "EQUAL",
            "value": subtype,
        }])

    audiences = await client.get_paginated(
        f"{act_id}/customaudiences", params=params, account_id=act_id,
    )

    rows = []
    for a in audiences:
        lower = safe_get(a, "approximate_count_lower_bound", 0)
        upper = safe_get(a, "approximate_count_upper_bound", 0)
        if lower and upper:
            size = f"{format_number(lower)}-{format_number(upper)}"
        elif lower:
            size = f"{format_number(lower)}+"
        else:
            size = "N/A"
        rows.append({
            "id": safe_get(a, "id"),
            "name": safe_get(a, "name"),
            "subtype": safe_get(a, "subtype"),
            "size": size,
            "status": str(safe_get(a, "operation_status", {}).get("status", "N/A")),
        })

    page, info = paginate_local(rows, limit, offset)

    if response_format == "json":
        return json.dumps({"audiences": page, "pagination": info.to_dict()}, indent=2, ensure_ascii=False)

    columns = ["id", "name", "subtype", "size", "status"]
    headers = {"id": "ID", "name": "Name", "subtype": "Type", "size": "Size", "status": "Status"}
    table = format_table_markdown(page, columns, headers)
    return f"## Audiences ({info.count}/{info.total})\n\n{table}"


@mcp.tool()
async def create_custom_audience(
    account_id: str,
    name: str,
    subtype: str,
    description: str = "",
    customer_file_source: str | None = None,
    retention_days: int | None = None,
    rule: str | None = None,
    ctx: Context = None,
) -> str:
    """Create a custom audience.

    Args:
        account_id: Ad account ID.
        name: Audience name.
        subtype: CUSTOM, WEBSITE, APP, OFFLINE, VIDEO, ENGAGEMENT.
        description: Optional description.
        customer_file_source: Source for customer file (USER_PROVIDED_ONLY, PARTNER_PROVIDED_ONLY, BOTH_USER_AND_PARTNER_PROVIDED).
        retention_days: Days to retain audience members (for WEBSITE/APP subtypes).
        rule: JSON rule for website/app audiences (e.g. '{"url":{"i_contains":"checkout"}}').
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)
    AudienceSubtype(subtype)

    payload: dict = {
        "name": name,
        "subtype": subtype,
        "description": description,
    }
    if customer_file_source:
        payload["customer_file_source"] = customer_file_source
    if retention_days is not None:
        payload["retention_days"] = str(retention_days)
    if rule:
        payload["rule"] = rule

    result = await client.post(f"{act_id}/customaudiences", data=payload, account_id=act_id)
    audience_id = result.get("id", "unknown")
    return (
        f"Custom audience created.\n\n"
        f"- **ID**: {audience_id}\n"
        f"- **Name**: {name}\n"
        f"- **Type**: {subtype}"
    )


@mcp.tool()
async def create_lookalike(
    account_id: str,
    name: str,
    origin_audience_id: str,
    country: str,
    ratio: float = 0.01,
    description: str = "",
    ctx: Context = None,
) -> str:
    """Create a lookalike audience from a source audience.

    Args:
        account_id: Ad account ID.
        name: Lookalike audience name.
        origin_audience_id: Source custom audience ID.
        country: Target country code (e.g. 'US', 'IT').
        ratio: Lookalike ratio 0.01-0.20 (1%-20% of country population).
        description: Optional description.
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    if not 0.01 <= ratio <= 0.20:
        return "Error: ratio must be between 0.01 (1%) and 0.20 (20%)."

    payload = {
        "name": name,
        "subtype": "LOOKALIKE",
        "description": description,
        "origin_audience_id": origin_audience_id,
        "lookalike_spec": json.dumps({
            "type": "similarity",
            "country": country.upper(),
            "ratio": ratio,
        }),
    }

    result = await client.post(f"{act_id}/customaudiences", data=payload, account_id=act_id)
    audience_id = result.get("id", "unknown")
    return (
        f"Lookalike audience created.\n\n"
        f"- **ID**: {audience_id}\n"
        f"- **Name**: {name}\n"
        f"- **Source**: {origin_audience_id}\n"
        f"- **Country**: {country.upper()}\n"
        f"- **Ratio**: {ratio:.0%}"
    )


@mcp.tool()
async def estimate_audience_size(
    account_id: str,
    targeting: str,
    optimization_goal: str = "LINK_CLICKS",
    ctx: Context = None,
) -> str:
    """Estimate reach for a targeting specification.

    Args:
        account_id: Ad account ID.
        targeting: JSON targeting spec (e.g. '{"geo_locations":{"countries":["US"]},"age_min":25,"age_max":55,"genders":[1]}').
        optimization_goal: LINK_CLICKS, IMPRESSIONS, REACH, etc.
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    params = {
        "targeting_spec": targeting,
        "optimization_goal": optimization_goal,
    }

    result = await client.get(f"{act_id}/delivery_estimate", params=params, account_id=act_id)
    data = result.get("data", [{}])
    estimate = data[0] if data else {}

    daily_reach = safe_get(estimate, "daily_outcomes_curve", [])
    if daily_reach:
        first = daily_reach[0]
        reach = format_number(safe_get(first, "reach", 0))
        impressions = format_number(safe_get(first, "impressions", 0))
        spend = safe_get(first, "spend", 0)
    else:
        reach = "N/A"
        impressions = "N/A"
        spend = 0

    return (
        f"## Audience Size Estimate\n\n"
        f"- **Estimated Daily Reach**: {reach}\n"
        f"- **Estimated Daily Impressions**: {impressions}\n"
        f"- **Estimated Daily Spend**: ${float(spend):,.2f}\n"
        f"- **Optimization Goal**: {optimization_goal}"
    )


@mcp.tool()
async def delete_audience(
    audience_id: str,
    ctx: Context = None,
) -> str:
    """Delete a custom or lookalike audience (REAL delete, not a stub).

    Args:
        audience_id: Audience ID to delete.
    """
    client = get_client(ctx)
    await client.delete(audience_id)
    return f"Audience `{audience_id}` deleted."
