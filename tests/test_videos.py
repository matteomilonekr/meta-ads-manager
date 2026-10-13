"""Tests for video upload and video creative payloads."""

import json

import httpx
import pytest
import respx

from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.models.common import META_GRAPH_URL, META_GRAPH_VIDEO_URL
from meta_ads_mcp.tools.creatives import build_creative_payload
from meta_ads_mcp.tools.videos import (
    _validate_video_path,
    upload_video_file,
    wait_until_ready,
)


def make_client() -> MetaAdsClient:
    return MetaAdsClient(AuthManager(MetaAuthConfig(access_token="test-token")))


def test_video_creative_without_link_has_no_cta():
    payload = build_creative_payload(
        "aaw_lungo_2", "PAGE", message="testo", video_id="V1",
        instagram_user_id="IG", thumbnail_url="https://example.com/t.jpg", opt_out_enhancements=True,
    )
    spec = json.loads(payload["object_story_spec"])
    assert spec["instagram_user_id"] == "IG"
    assert spec["video_data"] == {"video_id": "V1", "image_url": "https://example.com/t.jpg", "message": "testo"}
    assert json.loads(payload["contextual_multi_ads"]) == {"enroll_status": "OPT_OUT"}


def test_video_creative_with_link_adds_cta():
    payload = build_creative_payload("n", "PAGE", video_id="V1", image_hash="H", link="https://x.it", call_to_action_type="SIGN_UP")
    video = json.loads(payload["object_story_spec"])["video_data"]
    assert video["image_hash"] == "H"
    assert video["call_to_action"] == {"type": "SIGN_UP", "value": {"link": "https://x.it"}}


def test_link_ad_unchanged():
    payload = build_creative_payload("n", "PAGE", message="m", link="https://x.it", image_hash="H", headline="T")
    link = json.loads(payload["object_story_spec"])["link_data"]
    assert link["image_hash"] == "H" and link["name"] == "T" and link["message"] == "m"
    assert "degrees_of_freedom_spec" not in payload


def test_validate_video_path_rejects_missing_and_wrong_type(tmp_path):
    with pytest.raises(ValueError):
        _validate_video_path(str(tmp_path / "nope.mp4"))
    txt = tmp_path / "a.txt"
    txt.write_text("x")
    with pytest.raises(ValueError):
        _validate_video_path(str(txt))


@respx.mock
async def test_resumable_upload_sends_all_chunks(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"a" * 10)
    url = f"{META_GRAPH_VIDEO_URL}/act_1/advideos"
    sent = []

    def handler(request: httpx.Request):
        body = request.content
        if b'name="upload_phase"\r\n\r\nstart' in body or b"upload_phase=start" in body:
            return httpx.Response(200, json={"upload_session_id": "S", "video_id": "V", "start_offset": "0", "end_offset": "6"})
        if b"transfer" in body:
            sent.append(body)
            nxt = {1: ("6", "10"), 2: ("10", "10")}[len(sent)]
            return httpx.Response(200, json={"start_offset": nxt[0], "end_offset": nxt[1]})
        return httpx.Response(200, json={"success": True})

    respx.post(url).mock(side_effect=handler)
    client = make_client()
    assert await upload_video_file(client, "act_1", video, "clip") == "V"
    assert len(sent) == 2
    await client.close()


@respx.mock
async def test_wait_until_ready_returns_thumbnail():
    respx.get(f"{META_GRAPH_URL}/V").mock(
        return_value=httpx.Response(200, json={"status": {"video_status": "ready"}, "picture": "https://p"})
    )
    client = make_client()
    info = await wait_until_ready(client, "V")
    assert info["picture"] == "https://p"
    await client.close()
