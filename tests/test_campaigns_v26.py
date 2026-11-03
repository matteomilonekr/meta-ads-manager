"""Tests for create_campaign conformity with Marketing API v26.0."""

import json
from types import SimpleNamespace

import httpx
import respx

from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.models.common import META_API_VERSION, META_GRAPH_URL
from meta_ads_mcp.tools import campaigns
from meta_ads_mcp.utils.safety import safety_guard


def make_ctx() -> SimpleNamespace:
    client = MetaAdsClient(AuthManager(MetaAuthConfig(access_token="test-token")))
    return SimpleNamespace(lifespan_context={"meta_client": client})


def tool_fn(tool):
    return getattr(tool, "fn", tool)


def sent_form(route) -> httpx.QueryParams:
    return httpx.QueryParams(route.calls[0].request.content.decode())


def allow_writes(monkeypatch):
    monkeypatch.setattr(safety_guard, "check_write_allowed", lambda *a: None)
    monkeypatch.setattr(safety_guard, "record_write", lambda *a: None)


async def create(ctx, **kwargs):
    return await tool_fn(campaigns.create_campaign)("1", "Camp", "OUTCOME_TRAFFIC", ctx=ctx, **kwargs)


@respx.mock
async def test_request_goes_to_v26(monkeypatch):
    allow_writes(monkeypatch)
    assert META_API_VERSION == "v26.0"
    route = respx.post("https://graph.facebook.com/v26.0/act_1/campaigns").mock(
        return_value=httpx.Response(200, json={"id": "C1"})
    )
    ctx = make_ctx()
    out = await create(ctx, daily_budget=5000)
    assert "C1" in out
    assert route.called
    assert META_GRAPH_URL.endswith("/v26.0")
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_credit_is_mapped_to_financial_products_services(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    out = await create(ctx, daily_budget=5000, special_ad_categories="CREDIT")
    assert "C1" in out
    assert json.loads(sent_form(route)["special_ad_categories"]) == ["FINANCIAL_PRODUCTS_SERVICES"]
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_credit_and_new_name_are_not_duplicated(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    await create(ctx, daily_budget=5000, special_ad_categories="CREDIT,FINANCIAL_PRODUCTS_SERVICES")
    assert json.loads(sent_form(route)["special_ad_categories"]) == ["FINANCIAL_PRODUCTS_SERVICES"]
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_special_ad_category_country_sent_as_json_array(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    await create(ctx, daily_budget=5000, special_ad_categories="HOUSING", special_ad_category_country="IT, de")
    form = sent_form(route)
    assert json.loads(form["special_ad_categories"]) == ["HOUSING"]
    assert json.loads(form["special_ad_category_country"]) == ["IT", "DE"]
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_country_absent_when_not_given(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    await create(ctx, daily_budget=5000, special_ad_categories="HOUSING")
    assert "special_ad_category_country" not in sent_form(route)
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_politics_without_country_errors_without_http_call(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    out = await create(ctx, daily_budget=5000, special_ad_categories="ISSUES_ELECTIONS_POLITICS")
    assert out.startswith("Errore")
    assert "special_ad_category_country" in out
    assert not route.called
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_invalid_country_code_errors_without_http_call(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    for bad in ("ITA", "I1", "1T"):
        out = await create(ctx, daily_budget=5000, special_ad_categories="HOUSING", special_ad_category_country=bad)
        assert out.startswith("Errore")
    assert not route.called
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_adset_budget_sharing_false_by_default_without_campaign_budget(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    await create(ctx)
    assert sent_form(route)["is_adset_budget_sharing_enabled"] == "false"
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_adset_budget_sharing_true_when_requested(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    await create(ctx, adset_budget_sharing=True)
    assert sent_form(route)["is_adset_budget_sharing_enabled"] == "true"
    await ctx.lifespan_context["meta_client"].close()


@respx.mock
async def test_adset_budget_sharing_absent_with_campaign_budget(monkeypatch):
    allow_writes(monkeypatch)
    route = respx.post(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=httpx.Response(200, json={"id": "C1"}))
    ctx = make_ctx()
    await create(ctx, daily_budget=5000, adset_budget_sharing=True)
    assert "is_adset_budget_sharing_enabled" not in sent_form(route)
    route.calls.reset()
    await create(ctx, lifetime_budget=90000, stop_time="2026-12-31T00:00:00+0000", adset_budget_sharing=True)
    assert "is_adset_budget_sharing_enabled" not in sent_form(route)
    await ctx.lifespan_context["meta_client"].close()
