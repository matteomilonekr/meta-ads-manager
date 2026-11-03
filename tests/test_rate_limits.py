"""Tests for Meta rate limit compliance: usage headers, blocking and retries."""

import json
import logging

import httpx
import pytest
import respx

from meta_ads_mcp import client as client_module
from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.models.common import META_GRAPH_URL
from meta_ads_mcp.utils.errors import (
    MetaAdsMCPError,
    RateLimitError,
    ValidationError,
    classify_meta_error,
)
from meta_ads_mcp.utils.rate_limiter import parse_usage_headers, rate_limiter


@pytest.fixture(autouse=True)
def reset_limiter():
    rate_limiter._accounts.clear()
    yield
    rate_limiter._accounts.clear()


@pytest.fixture
def sleeps(monkeypatch):
    """Replace asyncio.sleep in the client so retries do not really wait."""
    calls: list[float] = []

    async def fake_sleep(delay):
        calls.append(delay)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)
    return calls


@pytest.fixture
async def client():
    c = MetaAdsClient(AuthManager(MetaAuthConfig(access_token="test-token")))
    yield c
    await c.close()


def buc_header(object_id="111", regain=0, call_count=10, tier="standard_access"):
    return {
        "X-Business-Use-Case-Usage": json.dumps({
            object_id: [{
                "type": "ads_management",
                "call_count": call_count,
                "total_cputime": 5,
                "total_time": 7,
                "estimated_time_to_regain_access": regain,
                "ads_api_access_tier": tier,
            }]
        })
    }


def throttle_response(code=80004, subcode=2446079, regain=5, object_id="111"):
    return httpx.Response(
        400,
        json={"error": {"message": "Too many calls", "type": "OAuthException",
                        "code": code, "error_subcode": subcode}},
        headers=buc_header(object_id, regain=regain, call_count=100),
    )


# ── Header parsing ───────────────────────────────────────────────────


def test_parse_buc_header_converts_minutes_to_seconds():
    snap = parse_usage_headers(buc_header("111", regain=5, call_count=80))
    assert snap.regain_seconds == 300
    assert snap.buc_pct == 80
    assert snap.access_tier == "standard_access"
    assert snap.buc_by_object["111"][0] == 300


def test_parse_ad_account_header():
    snap = parse_usage_headers({
        "X-Ad-Account-Usage": json.dumps({
            "acc_id_util_pct": 9.67, "reset_time_duration": 100,
            "ads_api_access_tier": "development_access",
        })
    })
    assert snap.account_pct == 9.67
    assert snap.reset_seconds == 100
    assert snap.access_tier == "development_access"


def test_parse_app_usage_and_insights_throttle():
    snap = parse_usage_headers({
        "X-App-Usage": json.dumps({"call_count": 28, "total_time": 25, "total_cputime": 40}),
        "X-FB-Ads-Insights-Throttle": json.dumps(
            {"app_id_util_pct": 12, "acc_id_util_pct": 33, "ads_api_access_tier": "standard_access"}
        ),
    })
    assert snap.app_pct == 40
    assert snap.account_pct == 33
    assert snap.access_tier == "standard_access"


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", '{"a": ', "null", '{"111": "x"}', '{"111": [1, "a"]}', ""])
def test_parse_malformed_headers_are_ignored(raw):
    headers = {
        "X-Business-Use-Case-Usage": raw,
        "X-Ad-Account-Usage": raw,
        "X-App-Usage": raw,
        "X-FB-Ads-Insights-Throttle": raw,
    }
    snap = parse_usage_headers(headers)
    assert not snap.has_data


def test_parse_ignores_non_numeric_values():
    snap = parse_usage_headers({
        "X-Ad-Account-Usage": json.dumps({"acc_id_util_pct": "abc", "reset_time_duration": -5})
    })
    assert snap.account_pct is None
    assert snap.reset_seconds is None


@respx.mock
async def test_malformed_header_does_not_break_request(client):
    respx.get(f"{META_GRAPH_URL}/me").mock(
        return_value=httpx.Response(200, json={"id": "1"}, headers={"X-App-Usage": "{broken"})
    )
    assert await client.get("me", account_id="act_1") == {"id": "1"}


@respx.mock
async def test_success_response_records_utilization_and_tier(client):
    headers = {"X-Ad-Account-Usage": json.dumps(
        {"acc_id_util_pct": 42.5, "reset_time_duration": 100, "ads_api_access_tier": "development_access"})}
    respx.get(f"{META_GRAPH_URL}/act_1/campaigns").mock(
        return_value=httpx.Response(200, json={"data": []}, headers=headers)
    )
    await client.get("act_1/campaigns", account_id="act_1")
    assert rate_limiter.get_reported_utilization("1") == 42.5
    assert rate_limiter.get_access_tier("act_1") == "development_access"
    assert rate_limiter.blocked_seconds("1") == 0


@respx.mock
async def test_high_utilization_logs_warning_without_blocking(client, caplog):
    headers = {"X-Ad-Account-Usage": json.dumps({"acc_id_util_pct": 95, "reset_time_duration": 50})}
    respx.get(f"{META_GRAPH_URL}/me").mock(return_value=httpx.Response(200, json={}, headers=headers))
    with caplog.at_level(logging.WARNING, logger="meta_ads_mcp.client"):
        await client.get("me", account_id="act_1")
    assert any("usage high" in r.getMessage() for r in caplog.records)
    assert rate_limiter.blocked_seconds("1") == 0
    assert "test-token" not in caplog.text


# ── Throttling errors ────────────────────────────────────────────────


@pytest.mark.parametrize("code", [4, 17, 32, 613, 80000, 80001, 80002, 80003, 80004, 80005, 80006, 80008, 80009, 80014])
def test_documented_throttling_codes_are_rate_limit_errors(code):
    assert isinstance(classify_meta_error({"code": code, "message": "x"}), RateLimitError)


@pytest.mark.parametrize("subcode", [1487742, 2446079])
def test_throttling_subcodes_are_rate_limit_errors(subcode):
    err = classify_meta_error({"code": 999, "error_subcode": subcode, "message": "x"})
    assert isinstance(err, RateLimitError)


def test_classify_attaches_retry_after_and_keeps_other_errors():
    err = classify_meta_error({"code": 80004, "message": "x"}, retry_after_seconds=300)
    assert isinstance(err, RateLimitError)
    assert err.retry_after_seconds == 300
    assert "5 minuti" in str(err)
    assert classify_meta_error({"code": 80004, "message": "x"}).retry_after_seconds is None
    assert isinstance(classify_meta_error({"code": 100, "message": "x"}), ValidationError)


@respx.mock
async def test_80004_with_regain_time_raises_without_retry(client, sleeps):
    route = respx.get(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=throttle_response(regain=5))
    with pytest.raises(RateLimitError) as exc_info:
        await client.get("act_1/campaigns", account_id="act_1")
    assert route.call_count == 1
    assert sleeps == []
    assert exc_info.value.retry_after_seconds == pytest.approx(300)
    assert exc_info.value.code == 80004
    assert "test-token" not in str(exc_info.value)
    assert rate_limiter.blocked_seconds("act_1") == pytest.approx(300, abs=2)


@respx.mock
async def test_blocked_account_is_short_circuited_without_http_call(client, sleeps):
    route = respx.get(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=throttle_response(regain=5))
    with pytest.raises(RateLimitError):
        await client.get("act_1/campaigns", account_id="act_1")
    assert route.call_count == 1

    with pytest.raises(RateLimitError) as exc_info:
        await client.get("act_1/campaigns", account_id="1")  # same account, other spelling
    with pytest.raises(RateLimitError):
        await client.post("act_1/campaigns", data={"name": "x"}, account_id="act_1")
    assert route.call_count == 1  # no further HTTP calls
    message = str(exc_info.value)
    assert "5 minuti" in message
    assert "test-token" not in message
    assert exc_info.value.retry_after_seconds == pytest.approx(300, abs=2)


@respx.mock
async def test_other_account_is_not_blocked(client, sleeps):
    respx.get(f"{META_GRAPH_URL}/act_1/campaigns").mock(return_value=throttle_response(regain=5))
    other = respx.get(f"{META_GRAPH_URL}/act_2/campaigns").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "c"}]})
    )
    with pytest.raises(RateLimitError):
        await client.get("act_1/campaigns", account_id="act_1")
    result = await client.get("act_2/campaigns", account_id="act_2")
    assert result == {"data": [{"id": "c"}]}
    assert other.call_count == 1


@respx.mock
async def test_block_expires(client, sleeps, monkeypatch):
    respx.get(f"{META_GRAPH_URL}/act_1/campaigns").mock(
        side_effect=[throttle_response(regain=5), httpx.Response(200, json={"ok": True})]
    )
    with pytest.raises(RateLimitError):
        await client.get("act_1/campaigns", account_id="act_1")
    rate_limiter._get_state("act_1").blocked_until -= 301  # time passes
    assert await client.get("act_1/campaigns", account_id="act_1") == {"ok": True}


@respx.mock
async def test_short_wait_is_retried_honoring_retry_after(client, sleeps):
    # 0.5 minutes = 30 s, below the retry threshold
    route = respx.get(f"{META_GRAPH_URL}/act_1/campaigns").mock(
        side_effect=[throttle_response(regain=0.5), httpx.Response(200, json={"ok": True})]
    )
    result = await client.get("act_1/campaigns", account_id="act_1")
    assert result == {"ok": True}
    assert route.call_count == 2
    assert sleeps == [30]  # the wait from Meta, not the fixed 4 s backoff


@respx.mock
async def test_ad_account_reset_time_used_when_no_buc_header(client, sleeps):
    throttled = httpx.Response(
        400,
        json={"error": {"message": "limit", "code": 17, "error_subcode": 2446079}},
        headers={"X-Ad-Account-Usage": json.dumps({"acc_id_util_pct": 100, "reset_time_duration": 20})},
    )
    route = respx.get(f"{META_GRAPH_URL}/act_1/campaigns").mock(
        side_effect=[throttled, httpx.Response(200, json={"ok": True})]
    )
    assert await client.get("act_1/campaigns", account_id="act_1") == {"ok": True}
    assert route.call_count == 2
    assert sleeps == [20]


@respx.mock
async def test_unknown_wait_keeps_exponential_backoff(client, sleeps):
    err = httpx.Response(400, json={"error": {"message": "limit", "code": 4}})
    route = respx.get(f"{META_GRAPH_URL}/me").mock(side_effect=[err, err, httpx.Response(200, json={"ok": 1})])
    assert await client.get("me") == {"ok": 1}
    assert route.call_count == 3
    assert sleeps == [4.0, 8.0]


@respx.mock
async def test_unknown_wait_gives_up_after_max_retries(client, sleeps):
    err = httpx.Response(400, json={"error": {"message": "limit", "code": 4}})
    route = respx.get(f"{META_GRAPH_URL}/me").mock(return_value=err)
    with pytest.raises(RateLimitError):
        await client.get("me")
    assert route.call_count == 4
    assert sleeps == [4.0, 8.0, 16.0]


@respx.mock
async def test_buc_regain_zero_on_success_clears_block(client, sleeps):
    respx.get(f"{META_GRAPH_URL}/act_1/campaigns").mock(
        return_value=httpx.Response(200, json={"ok": True}, headers=buc_header("1", regain=0))
    )
    rate_limiter.block("act_1", 30)
    await client.get("act_1/campaigns", account_id="act_1")  # waits the short block (mock sleep)
    assert sleeps == [pytest.approx(30, abs=2)]
    assert rate_limiter.blocked_seconds("act_1") == 0


# ── Transient errors unchanged ───────────────────────────────────────


@respx.mock
async def test_5xx_non_json_is_not_retried_as_before(client, sleeps):
    route = respx.get(f"{META_GRAPH_URL}/me").mock(return_value=httpx.Response(503, text="oops"))
    with pytest.raises(MetaAdsMCPError):
        await client.get("me")
    assert route.call_count == 1
    assert sleeps == []


@respx.mock
async def test_timeouts_are_retried_with_exponential_backoff(client, sleeps):
    route = respx.get(f"{META_GRAPH_URL}/me").mock(
        side_effect=[httpx.ReadTimeout("t"), httpx.ConnectError("c"), httpx.Response(200, json={"ok": 1})]
    )
    assert await client.get("me") == {"ok": 1}
    assert route.call_count == 3
    assert sleeps == [1.0, 2.0]


@respx.mock
async def test_timeouts_exhaust_retries(client, sleeps):
    route = respx.get(f"{META_GRAPH_URL}/me").mock(side_effect=httpx.ReadTimeout("t"))
    with pytest.raises(MetaAdsMCPError, match="after 4 attempts"):
        await client.get("me")
    assert route.call_count == 4
    assert sleeps == [1.0, 2.0, 4.0]
