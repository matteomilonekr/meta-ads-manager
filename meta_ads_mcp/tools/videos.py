"""Video upload and creative inspection tools for Meta Ads MCP."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastmcp import Context

from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.models.common import META_GRAPH_VIDEO_URL
from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools._helpers import get_client, normalize_account_id
from meta_ads_mcp.utils.errors import MetaAdsMCPError
from meta_ads_mcp.utils.safety import safety_guard

logger = logging.getLogger(__name__)

_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
_MAX_VIDEO_BYTES = 4 * 1024**3  # Meta's limit for ad videos
_CHUNK_RETRIES = 3
_READY_POLL_SECONDS = 10
_READY_TIMEOUT_SECONDS = 20 * 60

_CREATIVE_DETAIL_FIELDS = (
    "id,name,object_type,status,body,title,video_id,instagram_user_id,"
    "object_story_spec,call_to_action_type,effective_object_story_id,"
    "degrees_of_freedom_spec,contextual_multi_ads,url_tags,thumbnail_url"
)


def _validate_video_path(file_path: str) -> Path:
    """Accept only an existing regular video file within Meta's size limit."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise ValueError(f"Video file not found: {file_path}")
    if path.suffix.lower() not in _VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video type {path.suffix!r}. Use one of {sorted(_VIDEO_EXTENSIONS)}.")
    size = path.stat().st_size
    if size == 0 or size > _MAX_VIDEO_BYTES:
        raise ValueError(f"Video size {size} bytes is outside Meta's limit (1 byte to 4 GB).")
    return path


async def upload_video_file(
    client: MetaAdsClient,
    act_id: str,
    path: Path,
    title: str,
) -> str:
    """Upload a local video to the ad account with Meta's resumable upload. Returns the video ID."""
    url = f"{META_GRAPH_VIDEO_URL}/{act_id}/advideos"
    size = path.stat().st_size
    start = await client.post_multipart(
        url, data={"upload_phase": "start", "file_size": str(size)}, account_id=act_id,
    )
    session_id = start["upload_session_id"]
    video_id = start["video_id"]
    start_offset, end_offset = int(start["start_offset"]), int(start["end_offset"])

    with path.open("rb") as fh:
        while start_offset < end_offset:
            fh.seek(start_offset)
            chunk = fh.read(end_offset - start_offset)
            for attempt in range(_CHUNK_RETRIES):
                try:
                    step = await client.post_multipart(
                        url,
                        data={
                            "upload_phase": "transfer",
                            "upload_session_id": session_id,
                            "start_offset": str(start_offset),
                        },
                        files={"video_file_chunk": (path.name, chunk, "application/octet-stream")},
                        account_id=act_id,
                    )
                    break
                except (MetaAdsMCPError, OSError) as exc:
                    if attempt == _CHUNK_RETRIES - 1:
                        raise
                    logger.warning("Chunk at %d failed (%s), retrying", start_offset, type(exc).__name__)
                    await asyncio.sleep(2 ** attempt)
            start_offset, end_offset = int(step["start_offset"]), int(step["end_offset"])

    await client.post_multipart(
        url,
        data={"upload_phase": "finish", "upload_session_id": session_id, "title": title},
        account_id=act_id,
    )
    return str(video_id)


async def wait_until_ready(client: MetaAdsClient, video_id: str) -> dict[str, Any]:
    """Poll the video until Meta has processed it. Returns status and thumbnail URL."""
    waited = 0
    while True:
        info = await client.get(video_id, params={"fields": "status,picture,length"})
        status = (info.get("status") or {}).get("video_status")
        if status == "ready":
            return info
        if status == "error":
            raise MetaAdsMCPError(f"Meta could not process video {video_id}.")
        if waited >= _READY_TIMEOUT_SECONDS:
            return info
        await asyncio.sleep(_READY_POLL_SECONDS)
        waited += _READY_POLL_SECONDS


@mcp.tool()
async def upload_video(
    account_id: str,
    file_path: str,
    title: str | None = None,
    wait_ready: bool = True,
    ctx: Context = None,
) -> str:
    """Upload a local video file (.mp4/.mov) to the ad account for video ads.

    Uses Meta's resumable upload, so large files work. Returns the video ID to
    pass to create_creative, plus a thumbnail URL once Meta has processed it.

    Args:
        account_id: Ad account ID.
        file_path: Absolute path of the video on this computer.
        title: Name shown in the ad account media library (defaults to the file name).
        wait_ready: Wait until Meta finishes processing (needed before creating the ad).
    """
    client = get_client(ctx)
    act_id = normalize_account_id(account_id)
    blocked = safety_guard.check_write_allowed("create", act_id)
    if blocked:
        return f"**Operazione bloccata (protezione anti-ban):** {blocked}"
    path = _validate_video_path(file_path)
    video_id = await upload_video_file(client, act_id, path, title or path.stem)
    safety_guard.record_write("create", act_id)
    lines = ["Video uploaded successfully.", "", f"- **Video ID**: `{video_id}` (use this in create_creative)"]
    if wait_ready:
        info = await wait_until_ready(client, video_id)
        lines.append(f"- **Status**: {(info.get('status') or {}).get('video_status', 'unknown')}")
        if info.get("picture"):
            lines.append(f"- **Thumbnail URL**: {info['picture']}")
    return "\n".join(lines)


@mcp.tool()
async def get_creative(
    creative_id: str,
    response_format: str = "markdown",
    ctx: Context = None,
) -> str:
    """Read one creative in full: page, Instagram account, video, text, CTA and enhancement settings.

    Useful to copy the setup of an existing ad into new ones.

    Args:
        creative_id: Creative ID.
        response_format: markdown or json.
    """
    client = get_client(ctx)
    data = await client.get(creative_id, params={"fields": _CREATIVE_DETAIL_FIELDS})
    if response_format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)
    spec = data.get("object_story_spec") or {}
    video = spec.get("video_data") or {}
    link = spec.get("link_data") or {}
    cta = (video.get("call_to_action") or link.get("call_to_action") or {}).get("type")
    return "\n".join([
        f"## Creative `{data.get('id')}`",
        "",
        f"- **Type**: {data.get('object_type')}",
        f"- **Page**: {spec.get('page_id')}",
        f"- **Instagram account**: {spec.get('instagram_user_id') or data.get('instagram_user_id')}",
        f"- **Video**: {video.get('video_id') or data.get('video_id')}",
        f"- **Headline**: {video.get('title') or link.get('name') or data.get('title')}",
        f"- **CTA**: {cta or data.get('call_to_action_type')}",
        f"- **Link**: {(video.get('call_to_action') or {}).get('value', {}).get('link') or link.get('link')}",
        f"- **Enhancements opted out**: {json.dumps(data.get('degrees_of_freedom_spec'), ensure_ascii=False)}",
        "",
        "**Primary text**:",
        "",
        (video.get("message") or link.get("message") or data.get("body") or ""),
    ])
