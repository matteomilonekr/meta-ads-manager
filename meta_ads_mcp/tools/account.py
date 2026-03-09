"""Account management tools for Meta Ads MCP."""

from __future__ import annotations

import json
import logging

from fastmcp import Context

logger = logging.getLogger(__name__)

from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, safe_get
from meta_ads_mcp.utils.formatting import format_table_markdown


@mcp.tool()
async def list_ad_accounts(
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """List all Meta ad accounts accessible with the current token.

    Args:
        response_format: markdown or json.
    """
    client = get_client(ctx)
    accounts = await client.get_ad_accounts()

    rows = []
    for a in accounts:
        status_code = safe_get(a, "account_status", 0)
        status_map = {1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW", 8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE", 101: "CLOSED", 201: "ANY_ACTIVE", 202: "ANY_CLOSED"}
        status = status_map.get(int(status_code), f"UNKNOWN ({status_code})")

        rows.append({
            "id": safe_get(a, "id"),
            "name": safe_get(a, "name"),
            "status": status,
            "currency": safe_get(a, "currency"),
            "timezone": safe_get(a, "timezone_name"),
        })

    if response_format == "json":
        return json.dumps({"accounts": rows}, indent=2, ensure_ascii=False)

    columns = ["id", "name", "status", "currency", "timezone"]
    headers = {"id": "ID", "name": "Name", "status": "Status", "currency": "Currency", "timezone": "Timezone"}
    table = format_table_markdown(rows, columns, headers)
    return f"## Ad Accounts ({len(rows)})\n\n{table}"


@mcp.tool()
async def health_check(ctx: Context = None) -> str:
    """Check Meta Ads MCP server health and API connectivity.
    """
    client = get_client(ctx)
    try:
        result = await client.validate_token()
        name = result.get("name", "Unknown")
        user_id = result.get("id", "Unknown")

        accounts = await client.get_ad_accounts()
        account_count = len(accounts)

        return (
            f"## Server Health\n\n"
            f"- **Status**: Healthy\n"
            f"- **API**: Connected\n"
            f"- **User**: {name} ({user_id})\n"
            f"- **Accounts**: {account_count} accessible\n"
            f"- **API Version**: v23.0"
        )
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return (
            f"## Server Health\n\n"
            f"- **Status**: Unhealthy\n"
            f"- **Error**: {exc}"
        )
