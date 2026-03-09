"""Analytics and insights tools for Meta Ads MCP."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging

from fastmcp import Context

logger = logging.getLogger(__name__)

from meta_ads_mcp.models.common import (
    DEFAULT_INSIGHTS_FIELDS,
    DatePreset,
    InsightsLevel,
)
from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, safe_get
from meta_ads_mcp.utils.formatting import (
    currency_symbol,
    format_currency,
    format_number,
    format_percentage,
    format_table_markdown,
)


def _build_insights_params(
    date_preset: str | None,
    time_range_start: str | None,
    time_range_end: str | None,
    fields: str | None,
    breakdowns: str | None,
    level: str | None,
    limit: int = 100,
) -> dict:
    """Build query params for insights endpoint."""
    params: dict = {
        "fields": fields or ",".join(DEFAULT_INSIGHTS_FIELDS),
        "limit": str(limit),
    }
    if date_preset:
        DatePreset(date_preset)
        params["date_preset"] = date_preset
    elif time_range_start and time_range_end:
        params["time_range"] = json.dumps({
            "since": time_range_start,
            "until": time_range_end,
        })
    else:
        params["date_preset"] = "last_30d"

    if breakdowns:
        params["breakdowns"] = breakdowns
    if level:
        InsightsLevel(level)
        params["level"] = level

    return params


def _format_insight_row(row: dict, sym: str = "$") -> dict:
    """Format a single insight row for display."""
    spend = safe_get(row, "spend", "0")
    actions = row.get("actions", [])
    conversions = 0
    for action in actions:
        if action.get("action_type") in ("offsite_conversion", "lead", "purchase"):
            conversions += int(action.get("value", 0))

    return {
        "impressions": format_number(safe_get(row, "impressions", 0)),
        "clicks": format_number(safe_get(row, "clicks", 0)),
        "spend": f"{sym}{float(spend):,.2f}" if spend else f"{sym}0.00",
        "ctr": format_percentage(safe_get(row, "ctr")),
        "cpc": f"{sym}{float(safe_get(row, 'cpc', 0)):,.2f}",
        "cpm": f"{sym}{float(safe_get(row, 'cpm', 0)):,.2f}",
        "reach": format_number(safe_get(row, "reach", 0)),
        "frequency": f"{float(safe_get(row, 'frequency', 0)):.2f}",
        "conversions": str(conversions),
    }


@mcp.tool()
async def get_insights(
    object_id: str,
    date_preset: str | None = "last_30d",
    time_range_start: str | None = None,
    time_range_end: str | None = None,
    fields: str | None = None,
    breakdowns: str | None = None,
    level: str | None = None,
    limit: int = 100,
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """Get performance insights for a campaign, ad set, ad, or account.

    Args:
        object_id: Campaign/AdSet/Ad/Account ID to get insights for.
        date_preset: Date range preset (today, yesterday, last_7d, last_14d, last_28d, last_30d, last_90d, this_month, last_month, this_quarter, last_quarter, this_year, last_year, maximum).
        time_range_start: Custom start date YYYY-MM-DD (use instead of date_preset).
        time_range_end: Custom end date YYYY-MM-DD.
        fields: Comma-separated fields (default: impressions, clicks, spend, ctr, cpc, cpm, reach, frequency, actions).
        breakdowns: Optional breakdown: age, gender, country, publisher_platform, device_platform.
        level: Aggregation level: account, campaign, adset, ad.
        limit: Max results.
        response_format: markdown or json.
    """
    client = get_client(ctx)
    params = _build_insights_params(
        date_preset, time_range_start, time_range_end, fields, breakdowns, level, limit,
    )

    result = await client.get(f"{object_id}/insights", params=params)
    data = result.get("data", [])

    if not data:
        return f"No insights data found for `{object_id}` with the specified filters."

    if response_format == "json":
        return json.dumps({"insights": data}, indent=2, ensure_ascii=False)

    sym = currency_symbol(data[0].get("account_currency", "USD"))
    rows = [_format_insight_row(row, sym) for row in data]
    columns = ["impressions", "clicks", "spend", "ctr", "cpc", "cpm", "reach", "conversions"]
    headers = {
        "impressions": "Impr.", "clicks": "Clicks", "spend": "Spend",
        "ctr": "CTR", "cpc": "CPC", "cpm": "CPM", "reach": "Reach", "conversions": "Conv.",
    }
    table = format_table_markdown(rows, columns, headers)
    period = date_preset or f"{time_range_start} to {time_range_end}"
    return f"## Insights for `{object_id}` ({period})\n\n{table}"


@mcp.tool()
async def compare_performance(
    object_ids: str,
    date_preset: str = "last_30d",
    metrics: str = "impressions,clicks,spend,ctr,cpc,conversions",
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """Compare performance across multiple campaigns/ad sets/ads in parallel.

    Args:
        object_ids: Comma-separated IDs to compare (e.g. '123,456,789').
        date_preset: Date range preset.
        metrics: Comma-separated metrics to compare.
        response_format: markdown or json.
    """
    client = get_client(ctx)
    ids = [oid.strip() for oid in object_ids.split(",") if oid.strip()]

    if len(ids) < 2:
        return "Provide at least 2 object IDs to compare."

    DatePreset(date_preset)

    # Fetch all insights in PARALLEL (fix: original was sequential O(n))
    async def fetch_one(oid: str) -> dict:
        params = {
            "fields": metrics,
            "date_preset": date_preset,
        }
        result = await client.get(f"{oid}/insights", params=params)
        data = result.get("data", [{}])
        row = data[0] if data else {}
        row["object_id"] = oid
        return row

    results = await asyncio.gather(*[fetch_one(oid) for oid in ids])

    if response_format == "json":
        return json.dumps({"comparison": results}, indent=2, ensure_ascii=False)

    metric_list = [m.strip() for m in metrics.split(",")]
    columns = ["object_id", *metric_list]
    headers = {"object_id": "ID"}
    headers.update({m: m.replace("_", " ").title() for m in metric_list})

    rows = []
    for r in results:
        row = {"object_id": safe_get(r, "object_id")}
        for m in metric_list:
            row[m] = safe_get(r, m, "N/A")
        rows.append(row)

    table = format_table_markdown(rows, columns, headers)
    return f"## Performance Comparison ({date_preset})\n\n{table}"


@mcp.tool()
async def export_insights(
    object_id: str,
    export_format: str = "csv",
    date_preset: str = "last_30d",
    fields: str | None = None,
    breakdowns: str | None = None,
    level: str | None = None,
    ctx: Context = None,
) -> str:
    """Export insights data as CSV or JSON.

    Args:
        object_id: Campaign/AdSet/Ad/Account ID.
        export_format: csv or json.
        date_preset: Date range preset.
        fields: Comma-separated fields.
        breakdowns: Optional breakdown field.
        level: Aggregation level.
    """
    client = get_client(ctx)
    params = _build_insights_params(date_preset, None, None, fields, breakdowns, level)

    result = await client.get(f"{object_id}/insights", params=params)
    data = result.get("data", [])

    if not data:
        return f"No data to export for `{object_id}`."

    if export_format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)

    # CSV export
    output = io.StringIO()
    if data:
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        for row in data:
            flat_row = {}
            for k, v in row.items():
                flat_row[k] = json.dumps(v) if isinstance(v, (list, dict)) else v
            writer.writerow(flat_row)

    return output.getvalue()


@mcp.tool()
async def get_daily_trends(
    object_id: str,
    date_preset: str = "last_30d",
    fields: str | None = None,
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """Get daily breakdown with trend direction for a campaign/ad set.

    Args:
        object_id: Campaign/AdSet/Ad/Account ID.
        date_preset: Date range preset.
        fields: Comma-separated metrics (default: impressions, clicks, spend, ctr).
        response_format: markdown or json.
    """
    client = get_client(ctx)
    used_fields = fields or "impressions,clicks,spend,ctr"
    params = {
        "fields": used_fields,
        "date_preset": date_preset,
        "time_increment": "1",
    }

    result = await client.get(f"{object_id}/insights", params=params)
    data = result.get("data", [])

    if not data:
        return f"No trend data for `{object_id}`."

    if response_format == "json":
        return json.dumps({"trends": data}, indent=2, ensure_ascii=False)

    # Compute trend direction
    field_list = [f.strip() for f in used_fields.split(",")]
    rows = []
    for day in data:
        row = {"date": safe_get(day, "date_start", "N/A")}
        for f in field_list:
            val = safe_get(day, f, "0")
            row[f] = val
        rows.append(row)

    # Calculate trend for spend
    if len(rows) >= 2:
        try:
            first_val = float(safe_get(data[0], "spend", 0))
            last_val = float(safe_get(data[-1], "spend", 0))
            if first_val > 0:
                change = ((last_val - first_val) / first_val) * 100
                trend = "increasing" if change > 5 else ("decreasing" if change < -5 else "stable")
            else:
                trend = "stable"
        except (ValueError, ZeroDivisionError):
            trend = "unknown"
    else:
        trend = "insufficient data"

    columns = ["date", *field_list]
    headers = {"date": "Date"}
    headers.update({f: f.replace("_", " ").title() for f in field_list})
    table = format_table_markdown(rows[-14:], columns, headers)  # Last 14 days
    return f"## Daily Trends for `{object_id}` ({date_preset})\n\nTrend: **{trend}**\n\n{table}\n\n_Showing last {min(14, len(rows))} days_"


@mcp.tool()
async def get_attribution_data(
    object_id: str,
    date_preset: str = "last_30d",
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """Get attribution data with different attribution windows.

    Args:
        object_id: Campaign/AdSet/Ad ID.
        date_preset: Date range preset.
        response_format: markdown or json.
    """
    client = get_client(ctx)
    params = {
        "fields": "impressions,clicks,spend,actions,action_values,cost_per_action_type",
        "date_preset": date_preset,
        "action_attribution_windows": json.dumps(["1d_click", "7d_click", "1d_view"]),
    }

    result = await client.get(f"{object_id}/insights", params=params)
    data = result.get("data", [])

    if not data:
        return f"No attribution data for `{object_id}`."

    if response_format == "json":
        return json.dumps({"attribution": data}, indent=2, ensure_ascii=False)

    row = data[0]
    sym = currency_symbol(row.get("account_currency", "USD"))
    actions = row.get("actions", [])
    summary_lines = [
        f"## Attribution Data for `{object_id}` ({date_preset})",
        "",
        f"- **Impressions**: {format_number(safe_get(row, 'impressions', 0))}",
        f"- **Clicks**: {format_number(safe_get(row, 'clicks', 0))}",
        f"- **Spend**: {sym}{float(safe_get(row, 'spend', 0)):,.2f}",
        "",
        "### Actions by Type",
        "",
    ]

    for action in actions:
        action_type = action.get("action_type", "unknown")
        value = action.get("value", 0)
        summary_lines.append(f"- **{action_type}**: {value}")

    return "\n".join(summary_lines)
