"""Tests for numeric IDs in create_creative and local images in upload_image."""

import json
from types import SimpleNamespace

import httpx
import respx

from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.models.common import META_GRAPH_URL
from meta_ads_mcp.tools import creatives
from meta_ads_mcp.utils.safety import safety_guard


def make_ctx() -> SimpleNamespace:
    client = MetaAdsClient(AuthManager(MetaAuthConfig(access_token="test-token")))
    return SimpleNamespace(lifespan_context={"meta_client": client})


def tool_fn(tool):
    return getattr(tool, "fn", tool)


@respx.mock
async def test_create_creative_accepts_numeric_ids(monkeypatch):
    monkeypatch.setattr(safety_guard, "check_write_allowed", lambda *a: None)
    monkeypatch.setattr(safety_guard, "record_write", lambda *a: None)
    route = respx.post(f"{META_GRAPH_URL}/act_1/adcreatives").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    out = await tool_fn(creatives.create_creative)(
        "1", "n", 196159300254689, video_id=1726926608411185, instagram_user_id=17841401998, image_hash="H", ctx=ctx,
    )
    assert "C1" in out
    sent = httpx.QueryParams(route.calls[0].request.content.decode())
    spec = json.loads(sent["object_story_spec"])
    assert spec["page_id"] == "196159300254689"
    assert spec["instagram_user_id"] == "17841401998"
    assert spec["video_data"]["video_id"] == "1726926608411185"
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_upload_image_from_local_file(tmp_path):
    img = tmp_path / "cover.jpg"
    img.write_bytes(b"\xff\xd8jpeg")
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(
        return_value=httpx.Response(200, json={"images": {"cover.jpg": {"hash": "HASH1", "url": "https://u"}}})
    )
    ctx = make_ctx()
    out = await tool_fn(creatives.upload_image)("1", file_path=str(img), ctx=ctx)
    assert "HASH1" in out
    assert "bytes=" in route.calls[0].request.content.decode()
    await ctx.lifespan_context["meta_client"].close()


async def test_upload_image_rejects_other_files(tmp_path):
    txt = tmp_path / "a.txt"
    txt.write_text("x")
    ctx = make_ctx()
    out = await tool_fn(creatives.upload_image)("1", file_path=str(txt), ctx=ctx)
    assert out.startswith("Error")
    out = await tool_fn(creatives.upload_image)("1", ctx=ctx)
    assert out.startswith("Error")
    await ctx.lifespan_context["meta_client"].close()
