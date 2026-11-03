"""Creative management tools for Meta Ads MCP."""

from __future__ import annotations

import ipaddress
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

from fastmcp import Context
from pydantic import BeforeValidator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSRF protection for user-supplied URLs
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}
_LOCAL_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
_MAX_LOCAL_IMAGE_BYTES = 10 * 1024 * 1024  # base64 + urlencoding swell the request body to ~1.5x
_IMAGE_MAGIC_BYTES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")  # JPEG, PNG
_MAX_SAFE_INT = 2**53 - 1  # above this a JSON number can arrive already rounded (JS clients)


def _coerce_id(value: Any) -> str:
    """Accept a Meta ID as a digit string; tolerate JSON integers only when they are exact."""
    if isinstance(value, bool):
        raise ValueError("ID non valido: un booleano non è un ID. Passalo come stringa tra virgolette.")
    if isinstance(value, float):
        raise ValueError(
            "ID non valido: un numero decimale può aver perso cifre. Passa l'ID come stringa tra virgolette."
        )
    if isinstance(value, int):
        if not 0 < value <= _MAX_SAFE_INT:
            raise ValueError(
                "ID non valido: i numeri così grandi arrivano arrotondati. Passa l'ID come stringa tra virgolette."
            )
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isascii() and text.isdigit():
            return text
        raise ValueError("ID non valido: deve contenere solo cifre (es. \"17841401998000123\").")
    raise ValueError("ID non valido: passalo come stringa di sole cifre.")


# Schema stays "string" for MCP clients; safe integers are still accepted
MetaId = Annotated[str, BeforeValidator(_coerce_id)]


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


def build_creative_payload(
    name: str,
    page_id: str,
    message: str | None = None,
    link: str | None = None,
    image_hash: str | None = None,
    video_id: str | None = None,
    headline: str | None = None,
    description: str | None = None,
    call_to_action_type: str = "LEARN_MORE",
    instagram_user_id: str | None = None,
    thumbnail_url: str | None = None,
    opt_out_enhancements: bool = False,
) -> dict[str, str]:
    """Build the form payload for POST act_X/adcreatives."""
    story_spec: dict = {"page_id": page_id}
    if instagram_user_id:
        story_spec["instagram_user_id"] = instagram_user_id

    if video_id:
        # Video ad. Meta wants a thumbnail: an image hash or a URL.
        video_data: dict = {"video_id": video_id}
        if image_hash:
            video_data["image_hash"] = image_hash
        elif thumbnail_url:
            video_data["image_url"] = thumbnail_url
        if link:
            video_data["call_to_action"] = {"type": call_to_action_type, "value": {"link": link}}
        if message:
            video_data["message"] = message
        if headline:
            video_data["title"] = headline
        if description:
            video_data["link_description"] = description
        story_spec["video_data"] = video_data
    elif link:
        # Link ad, with or without image
        link_data: dict = {
            "link": link,
            "call_to_action": {"type": call_to_action_type, "value": {"link": link}},
        }
        if image_hash:
            link_data["image_hash"] = image_hash
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

    payload = {"name": name, "object_story_spec": json.dumps(story_spec)}
    if opt_out_enhancements:
        # Same opt-outs Ads Manager sets when Advantage+ creative extras are turned off
        payload["degrees_of_freedom_spec"] = json.dumps(
            {"creative_features_spec": {"product_browsing": {"enroll_status": "OPT_OUT"}}}
        )
        payload["contextual_multi_ads"] = json.dumps({"enroll_status": "OPT_OUT"})
    return payload


@mcp.tool()
async def create_creative(
    account_id: str,
    name: str,
    page_id: MetaId,
    message: str | None = None,
    link: str | None = None,
    image_hash: str | None = None,
    video_id: MetaId | None = None,
    headline: str | None = None,
    description: str | None = None,
    call_to_action_type: str = "LEARN_MORE",
    instagram_user_id: MetaId | None = None,
    thumbnail_url: str | None = None,
    opt_out_enhancements: bool = False,
    ctx: Context = None,
) -> str:
    """Create an ad creative with object_story_spec.

    Args:
        account_id: Ad account ID.
        name: Creative name.
        page_id: Facebook Page ID for the ad (pass it as a string, IDs can exceed what JSON numbers hold).
        message: Primary text (post body).
        link: Destination URL for the ad (optional for video ads).
        image_hash: Hash of uploaded image (from upload_image tool); for video ads it is the thumbnail.
        video_id: Video ID for video ads (from upload_video tool).
        headline: Ad headline.
        description: Ad description (link description).
        call_to_action_type: CTA type: LEARN_MORE, SHOP_NOW, SIGN_UP, DOWNLOAD, CONTACT_US, SUBSCRIBE, GET_OFFER, etc. Used only with a link.
        instagram_user_id: Instagram account that runs the ad (see get_creative on an existing ad).
        thumbnail_url: Thumbnail URL for video ads when no image_hash is given (upload_video returns one).
        opt_out_enhancements: Turn off Advantage+ creative extras (product browsing, multi-ads).
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    blocked = safety_guard.check_write_allowed("create", act_id)
    if blocked:
        return f"**Operazione bloccata (protezione anti-ban):** {blocked}"

    payload = build_creative_payload(
        name, page_id, message, link, image_hash, video_id, headline, description,
        call_to_action_type, instagram_user_id, thumbnail_url, opt_out_enhancements,
    )
    result = await client.post(f"{act_id}/adcreatives", data=payload, account_id=act_id)
    safety_guard.record_write("create", act_id)
    creative_id = result.get("id", "unknown")
    return (
        f"Creative created successfully.\n\n"
        f"- **ID**: {creative_id}\n"
        f"- **Name**: {name}\n"
        f"- **Page**: {page_id}\n"
        f"- **CTA**: {call_to_action_type if link else 'none'}"
    )


@mcp.tool()
async def upload_image(
    account_id: str,
    image_url: str | None = None,
    file_path: str | None = None,
    ctx: Context = None,
) -> str:
    """Upload an image to Meta for use in ad creatives, from a public URL or a local file.

    Returns the image hash needed for create_creative (for video ads it is the thumbnail).
    With a URL it tries URL upload first, then falls back to downloading and uploading as base64 bytes.

    Args:
        account_id: Ad account ID.
        image_url: Public URL of the image to upload.
        file_path: Absolute path of a local .jpg or .png image (used instead of image_url).
    """
    import base64
    import httpx as _httpx

    client = get_client(ctx)
    act_id = normalize_account_id(account_id)

    if file_path and image_url:
        return "Error: pass either image_url or file_path, not both."
    if not file_path and not image_url:
        return "Error: pass image_url or file_path."

    blocked = safety_guard.check_write_allowed("create", act_id)
    if blocked:
        return f"**Operazione bloccata (protezione anti-ban):** {blocked}"

    if file_path:
        try:
            path = _validate_image_path(file_path)
        except ValueError as exc:
            return f"Error: {exc}"
        try:
            b64 = base64.b64encode(path.read_bytes()).decode()
            result = await client.post(f"{act_id}/adimages", data={"bytes": b64}, account_id=act_id)
        except MetaAdsMCPError as exc:
            logger.error("File image upload failed (%s)", type(exc).__name__)
            return f"Error uploading image: {exc}"
        except (httpx.HTTPError, OSError) as exc:
            logger.error("File image upload failed (%s)", type(exc).__name__)
            return "Error uploading image from file. Check the file is readable and try again."
        safety_guard.record_write("create", act_id)
        return _format_image_result(result)

    # Validate URL before any network request (SSRF protection)
    _validate_image_url(image_url)

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

    safety_guard.record_write("create", act_id)
    return _format_image_result(result)


def _validate_image_path(file_path: str) -> Path:
    """Accept only a real, non-empty JPEG/PNG file within the size limit (and META_UPLOAD_DIR, if set)."""
    raw = Path(file_path).expanduser()
    if raw.is_symlink():
        raise ValueError("file_path must not be a symbolic link.")
    try:
        path = raw.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("image file not found.") from None
    if not path.is_file():
        raise ValueError("file_path must be an existing .jpg, .jpeg or .png file.")
    upload_dir = os.environ.get("META_UPLOAD_DIR")
    if upload_dir:
        try:
            allowed = Path(upload_dir).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError("META_UPLOAD_DIR is set but does not exist.") from None
        if not path.is_relative_to(allowed):
            raise ValueError("file_path is outside the allowed upload folder (META_UPLOAD_DIR).")
    if path.suffix.lower() not in _LOCAL_IMAGE_SUFFIXES:
        raise ValueError("file_path must be an existing .jpg, .jpeg or .png file.")
    size = path.stat().st_size
    if size == 0:
        raise ValueError("image file is empty.")
    if size > _MAX_LOCAL_IMAGE_BYTES:
        raise ValueError("image larger than 10 MB.")
    with path.open("rb") as fh:
        head = fh.read(8)
    if not head.startswith(_IMAGE_MAGIC_BYTES):
        raise ValueError("file is not a valid JPEG or PNG image.")
    return path


def _format_image_result(result: dict) -> str:
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
