"""Creative management tools for Meta Ads MCP."""

from __future__ import annotations

import ipaddress
import json
import logging
from urllib.parse import urlparse

from fastmcp import Context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSRF protection for user-supplied URLs
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def _validate_image_url(url: str) -> None:
    """Validate a user-supplied image URL to prevent SSRF attacks."""
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme not allowed: {parsed.scheme!r}. Use http or https.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("URL must include a valid hostname.")

    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Blocked hostname: {hostname}")

    # Block private / loopback IP ranges
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise ValueError(f"Private/reserved IP addresses are not allowed: {ip}")
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise
        # hostname is a domain, not a raw IP — that's fine

import httpx

from meta_ads_mcp.models.common import DEFAULT_CREATIVE_FIELDS, META_GRAPH_URL
from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, normalize_account_id, safe_get
from meta_ads_mcp.utils.errors import MetaAdsMCPError
from meta_ads_mcp.utils.formatting import format_table_markdown
from meta_ads_mcp.utils.pagination import paginate_local
from meta_ads_mcp.utils.safety import safety_guard


@mcp.tool()
async def list_creatives(
    account_id: str,
    limit: int = 25,
    offset: int = 0,
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """List ad creatives for an account.

    Args:
        account_id: Ad account ID.
        limit: Max results (default 25 to avoid Meta API data-size limits).
        offset: Pagination offset.
        response_format: markdown or json.
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    params = {"fields": ",".join(DEFAULT_CREATIVE_FIELDS), "limit": str(limit)}
    creatives = await client.get_paginated(
        f"{act_id}/adcreatives", params=params, account_id=act_id,
    )

    rows = []
    for c in creatives:
        rows.append({
            "id": safe_get(c, "id"),
            "name": safe_get(c, "name"),
            "title": safe_get(c, "title"),
            "status": safe_get(c, "status"),
            "image": "Yes" if safe_get(c, "image_url") else "No",
        })

    page, info = paginate_local(rows, limit, offset)

    if response_format == "json":
        return json.dumps({"creatives": page, "pagination": info.to_dict()}, indent=2, ensure_ascii=False)

    columns = ["id", "name", "title", "status", "image"]
    headers = {"id": "ID", "name": "Name", "title": "Title", "status": "Status", "image": "Image"}
    table = format_table_markdown(page, columns, headers)
    return f"## Ad Creatives ({info.count}/{info.total})\n\n{table}"


@mcp.tool()
async def create_creative(
    account_id: str,
    name: str,
    page_id: str,
    message: str | None = None,
    link: str | None = None,
    image_hash: str | None = None,
    video_id: str | None = None,
    headline: str | None = None,
    description: str | None = None,
    call_to_action_type: str = "LEARN_MORE",
    ctx: Context = None,
) -> str:
    """Create an ad creative with object_story_spec.

    Args:
        account_id: Ad account ID.
        name: Creative name.
        page_id: Facebook Page ID for the ad.
        message: Primary text (post body).
        link: Destination URL for the ad.
        image_hash: Hash of uploaded image (from upload_image tool).
        video_id: Video ID for video ads.
        headline: Ad headline.
        description: Ad description (link description).
        call_to_action_type: CTA type: LEARN_MORE, SHOP_NOW, SIGN_UP, DOWNLOAD, CONTACT_US, SUBSCRIBE, GET_OFFER, etc.
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    blocked = safety_guard.check_write_allowed("create", act_id)
    if blocked:
        return f"**Operazione bloccata (protezione anti-ban):** {blocked}"

    # Build object_story_spec
    story_spec: dict = {"page_id": page_id}

    if link and image_hash:
        # Link ad with image
        link_data: dict = {
            "link": link,
            "image_hash": image_hash,
            "call_to_action": {"type": call_to_action_type, "value": {"link": link}},
        }
        if message:
            link_data["message"] = message
        if headline:
            link_data["name"] = headline
        if description:
            link_data["description"] = description
        story_spec["link_data"] = link_data
    elif link and video_id:
        # Video ad
        video_data: dict = {
            "video_id": video_id,
            "call_to_action": {"type": call_to_action_type, "value": {"link": link}},
        }
        if message:
            video_data["message"] = message
        if headline:
            video_data["title"] = headline
        if description:
            video_data["description"] = description
        story_spec["video_data"] = video_data
    elif link:
        # Link ad without image — Meta requires link_data with a valid link
        link_data = {
            "link": link,
            "call_to_action": {"type": call_to_action_type, "value": {"link": link}},
        }
        if message:
            link_data["message"] = message
        if headline:
            link_data["name"] = headline
        if description:
            link_data["description"] = description
        story_spec["link_data"] = link_data
    elif message:
        # Text-only post (no link) — still needs link_data wrapper for Meta API
        story_spec["link_data"] = {"message": message}

    payload = {
        "name": name,
        "object_story_spec": json.dumps(story_spec),
    }

    result = await client.post(f"{act_id}/adcreatives", data=payload, account_id=act_id)
    safety_guard.record_write("create", act_id)
    creative_id = result.get("id", "unknown")
    return (
        f"Creative created successfully.\n\n"
        f"- **ID**: {creative_id}\n"
        f"- **Name**: {name}\n"
        f"- **Page**: {page_id}\n"
        f"- **CTA**: {call_to_action_type}"
    )


@mcp.tool()
async def upload_image(
    account_id: str,
    image_url: str,
    ctx: Context = None,
) -> str:
    """Upload an image from URL to Meta for use in ad creatives.

    Returns the image hash needed for create_creative.
    Tries URL upload first, falls back to downloading and uploading as base64 bytes.

    Args:
        account_id: Ad account ID.
        image_url: Public URL of the image to upload.
    """
    import base64
    import httpx as _httpx

    # Validate URL before any network request (SSRF protection)
    _validate_image_url(image_url)

    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    # Try URL-based upload first
    try:
        result = await client.post(f"{act_id}/adimages", data={"url": image_url}, account_id=act_id)
    except (httpx.HTTPError, MetaAdsMCPError) as url_err:
        # Fallback: download image and upload as base64 bytes
        logger.warning("URL upload failed (%s), falling back to bytes upload", type(url_err).__name__)
        try:
            async with _httpx.AsyncClient(timeout=30.0) as http:
                img_resp = await http.get(image_url, follow_redirects=False)
                img_resp.raise_for_status()
                b64 = base64.b64encode(img_resp.content).decode()
            result = await client.post(f"{act_id}/adimages", data={"bytes": b64}, account_id=act_id)
        except Exception:
            logger.error("Image upload failed (both url and bytes methods)")
            return "Error uploading image. Verify the URL is publicly accessible and points to a valid image."

    images = result.get("images", {})
    if images:
        first_key = next(iter(images))
        image_data = images[first_key]
        image_hash = image_data.get("hash", "unknown")
        url = image_data.get("url", "N/A")
        return (
            f"Image uploaded successfully.\n\n"
            f"- **Hash**: `{image_hash}` (use this in create_creative)\n"
            f"- **URL**: {url}"
        )

    return f"Image upload response: {json.dumps(result, indent=2)}"


@mcp.tool()
async def preview_ad(
    creative_id: str,
    ad_format: str = "DESKTOP_FEED_STANDARD",
    ctx: Context = None,
) -> str:
    """Preview an ad creative in various formats.

    Args:
        creative_id: Creative ID to preview.
        ad_format: Preview format: DESKTOP_FEED_STANDARD, MOBILE_FEED_STANDARD, INSTAGRAM_STANDARD, INSTAGRAM_STORY, RIGHT_COLUMN_STANDARD, MARKETPLACE_MOBILE.
    """
    client = get_client(ctx)
    params = {"ad_format": ad_format}
    result = await client.get(f"{creative_id}/previews", params=params)

    data = result.get("data", [])
    if not data:
        return f"No preview available for creative `{creative_id}` in format `{ad_format}`."

    preview = data[0]
    body = preview.get("body", "No preview body available")
    return (
        f"## Ad Preview ({ad_format})\n\n"
        f"Creative: `{creative_id}`\n\n"
        f"```html\n{body}\n```"
    )
