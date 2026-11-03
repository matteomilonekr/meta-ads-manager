"""Tests for the v26 audience changes: MAU bounds in the estimate, countryless lookalikes."""

import json
from types import SimpleNamespace

import httpx
import respx

from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.models.common import META_GRAPH_URL
from meta_ads_mcp.tools import audiences
from meta_ads_mcp.utils.safety import safety_guard


def make_ctx() -> SimpleNamespace:
    client = MetaAdsClient(AuthManager(MetaAuthConfig(access_token="test-token")))
    return SimpleNamespace(lifespan_context={"meta_client": client})


def tool_fn(tool):
    return getattr(tool, "fn", tool)


@respx.mock
async def test_estimate_uses_mau_bounds():
    respx.get(f"{META_GRAPH_URL}/act_1/delivery_estimate").mock(
        return_value=httpx.Response(200, json={"data": [{
            "estimate_mau_lower_bound": 120000, "estimate_mau_upper_bound": 150000, "estimate_ready": True,
        }]})
    )
    ctx = make_ctx()
    out = await tool_fn(audiences.estimate_audience_size)("1", targeting={"geo_locations": {"countries": ["IT"]}}, ctx=ctx)
    assert "N/A" not in out
    assert "Monthly Active Audience" in out
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_estimate_without_bounds_is_na():
    respx.get(f"{META_GRAPH_URL}/act_1/delivery_estimate").mock(
        return_value=httpx.Response(200, json={"data": [{"estimate_ready": False}]})
    )
    ctx = make_ctx()
    out = await tool_fn(audiences.estimate_audience_size)("1", targeting="{}", ctx=ctx)
    assert "N/A" in out
    assert "retry" in out
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_lookalike_does_not_send_country(monkeypatch):
    monkeypatch.setattr(safety_guard, "check_write_allowed", lambda *a: None)
    monkeypatch.setattr(safety_guard, "record_write", lambda *a: None)
    route = respx.post(f"{META_GRAPH_URL}/act_1/customaudiences").mock(return_value=httpx.Response(200, json={"id": "LAL1"}))
    ctx = make_ctx()
    # country is still accepted so existing calls keep working, but Meta ignores it
    out = await tool_fn(audiences.create_lookalike)("1", "lal", "999", country="it", ratio=0.02, ctx=ctx)
    assert "LAL1" in out
    sent = httpx.QueryParams(route.calls[0].request.content.decode())
    spec = json.loads(sent["lookalike_spec"])
    assert "country" not in spec
    assert spec["ratio"] == 0.02
    await ctx.lifespan_context["meta_client"].close()
