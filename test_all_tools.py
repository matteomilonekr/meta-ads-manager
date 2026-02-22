#!/usr/bin/env python3
"""Comprehensive test of all 36 Meta Ads MCP tools against live API."""

import asyncio
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass
from typing import Any

# Suppress HTTP request logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Load env
from dotenv import load_dotenv
load_dotenv("/config/workspace/.env")

from meta_ads_mcp.auth import load_config_from_env, AuthManager
from meta_ads_mcp.client import MetaAdsClient


# ── Mock MCP Context ─────────────────────────────────────────────────
@dataclass
class MockRequestContext:
    lifespan_state: dict

@dataclass
class MockContext:
    request_context: MockRequestContext


async def create_test_context() -> tuple[MockContext, MetaAdsClient]:
    """Create a real client wrapped in a mock MCP context."""
    config = load_config_from_env()
    auth = AuthManager(config)
    client = MetaAdsClient(auth)
    ctx = MockContext(
        request_context=MockRequestContext(
            lifespan_state={"meta_client": client, "auth": auth}
        )
    )
    return ctx, client


# ── Test runner ──────────────────────────────────────────────────────
RESULTS: list[dict[str, Any]] = []

async def run_test(name: str, coro):
    """Run a single test, catch errors, and record result."""
    try:
        result = await coro
        # Truncate long output
        display = str(result)[:300] if result else "(empty)"
        RESULTS.append({"tool": name, "status": "PASS", "output": display})
        print(f"  ✅ {name}")
        return result
    except Exception as exc:
        err = f"{type(exc).__name__}: {str(exc)[:200]}"
        RESULTS.append({"tool": name, "status": "FAIL", "error": err})
        print(f"  ❌ {name} → {err}")
        return None


async def _skip(msg: str) -> str:
    """Return a skip message as a coroutine."""
    return f"SKIPPED - {msg}"


async def main():
    print("=" * 70)
    print("META ADS MCP — FULL TOOL TEST (36 tools)")
    print("=" * 70)

    ctx, client = await create_test_context()

    # Import all tool functions
    from meta_ads_mcp.tools.account import health_check, list_ad_accounts
    from meta_ads_mcp.tools.oauth import (
        generate_auth_url, exchange_code_for_token,
        refresh_to_long_lived_token, get_token_info, validate_token,
    )
    from meta_ads_mcp.tools.campaigns import (
        list_campaigns, create_campaign, update_campaign,
        pause_campaign, resume_campaign, delete_campaign,
    )
    from meta_ads_mcp.tools.ad_sets import (
        list_ad_sets, create_ad_set, update_ad_set,
        pause_ad_set, delete_ad_set,
    )
    from meta_ads_mcp.tools.ads import (
        list_ads, create_ad, update_ad, delete_ad,
    )
    from meta_ads_mcp.tools.analytics import (
        get_insights, compare_performance, export_insights,
        get_daily_trends, get_attribution_data,
    )
    from meta_ads_mcp.tools.audiences import (
        list_audiences, create_custom_audience, create_lookalike,
        estimate_audience_size, delete_audience,
    )
    from meta_ads_mcp.tools.creatives import (
        list_creatives, create_creative, upload_image, preview_ad,
    )

    # ── PHASE 1: Health & Auth (5 tools) ─────────────────────────────
    print("\n📋 PHASE 1: Health & Auth")
    print("-" * 40)

    await run_test("health_check", health_check(ctx=ctx))
    await run_test("validate_token", validate_token(ctx=ctx))
    await run_test("get_token_info", get_token_info(ctx=ctx))

    # generate_auth_url requires META_APP_ID
    await run_test("generate_auth_url", generate_auth_url(scopes="ads_read", ctx=ctx))

    # exchange_code_for_token - test with fake code (will get API error but validates flow)
    await run_test("exchange_code_for_token", exchange_code_for_token(code="FAKE_CODE_TEST", ctx=ctx))

    # refresh_to_long_lived_token - requires app_id/secret
    await run_test("refresh_to_long_lived_token", refresh_to_long_lived_token(ctx=ctx))

    # Small delay between phases to avoid rate limiting
    await asyncio.sleep(2)

    # ── PHASE 2: List Ad Accounts (1 tool) ───────────────────────────
    print("\n📋 PHASE 2: Account Discovery")
    print("-" * 40)

    accounts_result = await run_test("list_ad_accounts (markdown)", list_ad_accounts(response_format="markdown", ctx=ctx))
    accounts_json_result = await run_test("list_ad_accounts (json)", list_ad_accounts(response_format="json", ctx=ctx))

    # Extract first account ID for subsequent tests
    account_id = None
    if accounts_json_result:
        try:
            data = json.loads(accounts_json_result)
            accounts = data.get("accounts", [])
            if accounts:
                account_id = accounts[0]["id"]
                print(f"\n  📌 Using account: {account_id} ({accounts[0].get('name', 'N/A')})")
        except Exception:
            pass

    if not account_id:
        print("\n  ⚠️  No ad accounts found. Skipping account-dependent tests.")
        await client.close()
        print_summary()
        return

    # Clean account_id (remove act_ prefix for tools that add it)
    clean_id = account_id.replace("act_", "")

    await asyncio.sleep(2)

    # ── PHASE 3: Campaign Tools (6 tools) ────────────────────────────
    print("\n📋 PHASE 3: Campaigns")
    print("-" * 40)

    await run_test("list_campaigns (markdown)", list_campaigns(account_id=clean_id, ctx=ctx))
    await run_test("list_campaigns (json)", list_campaigns(account_id=clean_id, response_format="json", ctx=ctx))
    await run_test("list_campaigns (ACTIVE)", list_campaigns(account_id=clean_id, status="ACTIVE", ctx=ctx))
    await run_test("list_campaigns (PAUSED)", list_campaigns(account_id=clean_id, status="PAUSED", ctx=ctx))
    await run_test("list_campaigns (limit=5)", list_campaigns(account_id=clean_id, limit=5, ctx=ctx))

    # Create a test campaign
    test_campaign_id = None
    create_result = await run_test(
        "create_campaign",
        create_campaign(
            account_id=clean_id,
            name="[TEST] MCP Tool Test Campaign - DELETE ME",
            objective="OUTCOME_TRAFFIC",
            daily_budget=500,  # $5.00
            ctx=ctx,
        )
    )
    if create_result and "ID" in str(create_result):
        # Extract campaign ID
        for line in str(create_result).split("\n"):
            if "**ID**:" in line:
                test_campaign_id = line.split("**ID**:")[1].strip()
                print(f"  📌 Created test campaign: {test_campaign_id}")
                break

    if test_campaign_id:
        await run_test("update_campaign", update_campaign(
            campaign_id=test_campaign_id, name="[TEST] Updated Campaign Name", ctx=ctx
        ))
        await run_test("pause_campaign", pause_campaign(campaign_id=test_campaign_id, ctx=ctx))
        # Skip resume to avoid activating a real campaign
        await run_test("resume_campaign (skip - safety)", _skip("safety"))

        # Keep campaign for ad set / ad tests
    else:
        await run_test("update_campaign (skip)", _skip("no campaign"))
        await run_test("pause_campaign (skip)", _skip("no campaign"))
        await run_test("resume_campaign (skip)", _skip("no campaign"))

    await asyncio.sleep(3)

    # ── PHASE 4: Ad Set Tools (5 tools) ──────────────────────────────
    print("\n📋 PHASE 4: Ad Sets")
    print("-" * 40)

    await run_test("list_ad_sets (by account)", list_ad_sets(account_id=clean_id, ctx=ctx))
    await run_test("list_ad_sets (json)", list_ad_sets(account_id=clean_id, response_format="json", ctx=ctx))

    if test_campaign_id:
        await run_test("list_ad_sets (by campaign)", list_ad_sets(campaign_id=test_campaign_id, ctx=ctx))

    # Create test ad set (no daily_budget — campaign uses CBO)
    test_adset_id = None
    if test_campaign_id:
        adset_result = await run_test(
            "create_ad_set",
            create_ad_set(
                campaign_id=test_campaign_id,
                account_id=clean_id,
                name="[TEST] MCP Test Ad Set - DELETE ME",
                optimization_goal="LINK_CLICKS",
                billing_event="IMPRESSIONS",
                targeting='{"geo_locations":{"countries":["IT"]},"age_min":25,"age_max":55}',
                ctx=ctx,
            )
        )
        if adset_result and "ID" in str(adset_result):
            for line in str(adset_result).split("\n"):
                if "**ID**:" in line:
                    test_adset_id = line.split("**ID**:")[1].strip()
                    print(f"  📌 Created test ad set: {test_adset_id}")
                    break

    if test_adset_id:
        await run_test("update_ad_set", update_ad_set(
            ad_set_id=test_adset_id, name="[TEST] Updated Ad Set", ctx=ctx
        ))
        await run_test("pause_ad_set", pause_ad_set(ad_set_id=test_adset_id, ctx=ctx))
    else:
        await run_test("create_ad_set (skip)", _skip("no campaign"))
        await run_test("update_ad_set (skip)", _skip("no ad set"))
        await run_test("pause_ad_set (skip)", _skip("no ad set"))

    await asyncio.sleep(3)

    # ── PHASE 5: Ad Tools (4 tools) ──────────────────────────────────
    print("\n📋 PHASE 5: Ads")
    print("-" * 40)

    await run_test("list_ads (by account)", list_ads(account_id=clean_id, ctx=ctx))
    await run_test("list_ads (json)", list_ads(account_id=clean_id, response_format="json", ctx=ctx))

    # create_ad needs a creative_id, skip actual creation
    await run_test("create_ad (skip - needs creative)", _skip("needs real creative_id"))
    await run_test("update_ad (skip - needs ad)", _skip("needs real ad_id"))

    await asyncio.sleep(3)

    # ── PHASE 6: Creative Tools (4 tools) ────────────────────────────
    print("\n📋 PHASE 6: Creatives")
    print("-" * 40)

    await run_test("list_creatives (markdown)", list_creatives(account_id=clean_id, ctx=ctx))
    await run_test("list_creatives (json)", list_creatives(account_id=clean_id, response_format="json", ctx=ctx))

    # Upload a test image
    await run_test(
        "upload_image",
        upload_image(
            account_id=clean_id,
            image_url="https://via.placeholder.com/1200x628.png?text=MCP+Test",
            ctx=ctx,
        )
    )

    # create_creative needs a valid page_id, test with first available
    await run_test("create_creative (skip - needs page_id)", _skip("needs real page_id"))

    # preview_ad needs creative_id
    # Try to get one from list_creatives
    creatives_json = await list_creatives(account_id=clean_id, response_format="json", ctx=ctx)
    test_creative_id = None
    try:
        cdata = json.loads(creatives_json)
        creatives = cdata.get("creatives", [])
        if creatives:
            test_creative_id = creatives[0]["id"]
    except Exception:
        pass

    if test_creative_id:
        await run_test("preview_ad", preview_ad(creative_id=test_creative_id, ctx=ctx))
    else:
        await run_test("preview_ad (skip - no creative)", _skip("no creative found"))

    await asyncio.sleep(3)

    # ── PHASE 7: Audience Tools (5 tools) ────────────────────────────
    print("\n📋 PHASE 7: Audiences")
    print("-" * 40)

    await run_test("list_audiences (markdown)", list_audiences(account_id=clean_id, ctx=ctx))
    await run_test("list_audiences (json)", list_audiences(account_id=clean_id, response_format="json", ctx=ctx))

    await run_test(
        "estimate_audience_size",
        estimate_audience_size(
            account_id=clean_id,
            targeting='{"geo_locations":{"countries":["IT"]},"age_min":25,"age_max":45}',
            ctx=ctx,
        )
    )

    # Create custom audience (WEBSITE type for testing)
    test_audience_id = None
    audience_result = await run_test(
        "create_custom_audience",
        create_custom_audience(
            account_id=clean_id,
            name="[TEST] MCP Test Audience - DELETE ME",
            subtype="CUSTOM",
            description="Test audience created by MCP tool test",
            customer_file_source="USER_PROVIDED_ONLY",
            ctx=ctx,
        )
    )
    if audience_result and "ID" in str(audience_result):
        for line in str(audience_result).split("\n"):
            if "**ID**:" in line:
                test_audience_id = line.split("**ID**:")[1].strip()
                print(f"  📌 Created test audience: {test_audience_id}")
                break

    # create_lookalike needs a valid source audience
    if test_audience_id:
        await run_test(
            "create_lookalike",
            create_lookalike(
                account_id=clean_id,
                name="[TEST] Lookalike from Test - DELETE ME",
                origin_audience_id=test_audience_id,
                country="IT",
                ratio=0.01,
                ctx=ctx,
            )
        )
    else:
        await run_test("create_lookalike (skip)", _skip("no source audience"))

    await asyncio.sleep(3)

    # ── PHASE 8: Analytics Tools (5 tools) ───────────────────────────
    print("\n📋 PHASE 8: Analytics")
    print("-" * 40)

    # Use account-level insights
    await run_test("get_insights (account, last_30d)", get_insights(object_id=account_id, ctx=ctx))
    await run_test("get_insights (json)", get_insights(object_id=account_id, response_format="json", ctx=ctx))
    await run_test("get_insights (last_7d)", get_insights(object_id=account_id, date_preset="last_7d", ctx=ctx))
    await run_test("get_insights (custom range)", get_insights(
        object_id=account_id,
        date_preset=None,
        time_range_start="2026-01-01",
        time_range_end="2026-01-31",
        ctx=ctx,
    ))
    await run_test("get_insights (breakdown by age)", get_insights(
        object_id=account_id, breakdowns="age", ctx=ctx
    ))

    await run_test("get_daily_trends", get_daily_trends(object_id=account_id, ctx=ctx))
    await run_test("get_daily_trends (last_7d)", get_daily_trends(
        object_id=account_id, date_preset="last_7d", ctx=ctx
    ))

    await run_test("get_attribution_data", get_attribution_data(object_id=account_id, ctx=ctx))

    await run_test("export_insights (csv)", export_insights(object_id=account_id, ctx=ctx))
    await run_test("export_insights (json)", export_insights(
        object_id=account_id, export_format="json", ctx=ctx
    ))

    # compare_performance needs 2+ IDs - use account with itself for testing
    await run_test(
        "compare_performance",
        compare_performance(object_ids=f"{account_id},{account_id}", ctx=ctx)
    )

    # ── PHASE 9: Cleanup ─────────────────────────────────────────────
    print("\n📋 PHASE 9: Cleanup (Delete Test Objects)")
    print("-" * 40)

    if test_audience_id:
        await run_test("delete_audience", delete_audience(audience_id=test_audience_id, ctx=ctx))

    if test_adset_id:
        await run_test("delete_ad_set", delete_ad_set(ad_set_id=test_adset_id, ctx=ctx))

    if test_campaign_id:
        await run_test("delete_campaign", delete_campaign(campaign_id=test_campaign_id, ctx=ctx))

    # delete_ad - skip (no ad created)
    await run_test("delete_ad (skip - no ad)", _skip("no test ad"))

    # Close client
    await client.close()

    # Print summary
    print_summary()


def print_summary():
    """Print final test summary."""
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = [r for r in RESULTS if r["status"] == "PASS"]
    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    skipped = [r for r in RESULTS if "SKIP" in str(r.get("output", ""))]

    # Categorize
    real_passed = [r for r in passed if "SKIP" not in str(r.get("output", ""))]
    real_failed = failed

    print(f"\n  Total tests:     {len(RESULTS)}")
    print(f"  ✅ Passed (live): {len(real_passed)}")
    print(f"  ⏭️  Skipped:      {len(skipped)}")
    print(f"  ❌ Failed:        {len(real_failed)}")

    if real_failed:
        print("\n  FAILURES:")
        for r in real_failed:
            print(f"    ❌ {r['tool']}: {r.get('error', 'unknown')}")

    if real_passed:
        print(f"\n  PASSED TOOLS ({len(real_passed)}):")
        for r in real_passed:
            print(f"    ✅ {r['tool']}")

    if skipped:
        print(f"\n  SKIPPED ({len(skipped)}):")
        for r in skipped:
            print(f"    ⏭️  {r['tool']}")

    print("\n" + "=" * 70)
    rate = len(real_passed) / max(len(real_passed) + len(real_failed), 1) * 100
    print(f"  SUCCESS RATE: {rate:.0f}% ({len(real_passed)}/{len(real_passed) + len(real_failed)} live tests)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
