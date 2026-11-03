"""Tests for ID handling in create_creative (string schema, exact IDs)."""

import json
from types import SimpleNamespace

import httpx
import pytest
import respx
from fastmcp.exceptions import ValidationError

from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.models.common import META_GRAPH_URL
from meta_ads_mcp.server import mcp
from meta_ads_mcp.tools import creatives
from meta_ads_mcp.utils.safety import safety_guard

IG_ID = "17841401998000123"  # 17 digits: above 2**53, a float would round it
ID_PARAMS = ("page_id", "video_id", "instagram_user_id")


def make_ctx() -> SimpleNamespace:
    client = MetaAdsClient(AuthManager(MetaAuthConfig(access_token="test-token")))
    return SimpleNamespace(lifespan_context={"meta_client": client})


@pytest.fixture(autouse=True)
def no_safety_guard(monkeypatch):
    monkeypatch.setattr(safety_guard, "check_write_allowed", lambda *a: None)
    monkeypatch.setattr(safety_guard, "record_write", lambda *a: None)


@pytest.fixture
async def tool_ctx(monkeypatch):
    """Run create_creative through FastMCP, so parameter validation applies."""
    ctx = make_ctx()
    monkeypatch.setattr(creatives, "get_client", lambda _ctx: ctx.lifespan_context["meta_client"])
    yield ctx
    await ctx.lifespan_context["meta_client"].close()


async def call_create(**overrides) -> str:
    args = {"account_id": "1", "name": "n", "page_id": "196159300254689", "image_hash": "H", **overrides}
    tool = await mcp.get_tool("create_creative")
    result = await tool.run(args)
    return result.content[0].text


@respx.mock
async def test_ids_passed_as_strings_arrive_exactly(tool_ctx):
    route = respx.post(f"{META_GRAPH_URL}/act_1/adcreatives").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    out = await call_create(video_id="1726926608411185", instagram_user_id=IG_ID)
    assert "C1" in out
    sent = httpx.QueryParams(route.calls[0].request.content.decode())
    spec = json.loads(sent["object_story_spec"])
    assert spec["page_id"] == "196159300254689"
    assert spec["instagram_user_id"] == IG_ID
    assert spec["video_data"]["video_id"] == "1726926608411185"


@respx.mock
async def test_safe_integers_are_accepted(tool_ctx):
    route = respx.post(f"{META_GRAPH_URL}/act_1/adcreatives").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    await call_create(page_id=196159300254689, video_id=1726926608411185, instagram_user_id=2**53 - 1)
    spec = json.loads(httpx.QueryParams(route.calls[0].request.content.decode())["object_story_spec"])
    assert spec["page_id"] == "196159300254689"
    assert spec["video_data"]["video_id"] == "1726926608411185"
    assert spec["instagram_user_id"] == str(2**53 - 1)


@respx.mock
async def test_whitespace_around_string_id_is_stripped(tool_ctx):
    route = respx.post(f"{META_GRAPH_URL}/act_1/adcreatives").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    await call_create(page_id=" 196159300254689 ")
    spec = json.loads(httpx.QueryParams(route.calls[0].request.content.decode())["object_story_spec"])
    assert spec["page_id"] == "196159300254689"


@respx.mock
@pytest.mark.parametrize("param", ID_PARAMS)
@pytest.mark.parametrize(
    "bad, hint",
    [
        (int(IG_ID), "stringa"),  # int above 2**53 already arrived rounded
        (2**53, "stringa"),
        (17841401998000123.0, "stringa"),  # float
        (1.5, "stringa"),
        (True, "booleano"),
        (0, "stringa"),
        (-5, "stringa"),
        ("12a", "cifre"),
        ("", "cifre"),
        ("1e5", "cifre"),
        ("-12", "cifre"),
    ],
)
async def test_invalid_ids_are_rejected_without_http_call(tool_ctx, param, bad, hint):
    route = respx.post(f"{META_GRAPH_URL}/act_1/adcreatives").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    with pytest.raises(ValidationError, match="ID non valido") as exc:
        await call_create(**{param: bad})
    assert hint in str(exc.value)
    assert not route.called


async def test_id_params_are_plain_strings_in_tool_schema():
    tool = await mcp.get_tool("create_creative")
    props = tool.parameters["properties"]
    assert props["page_id"]["type"] == "string"
    assert "page_id" in tool.parameters["required"]
    for name in ("video_id", "instagram_user_id"):
        types = {branch["type"] for branch in props[name]["anyOf"]}
        assert types == {"string", "null"}
    assert "integer" not in json.dumps(props)
