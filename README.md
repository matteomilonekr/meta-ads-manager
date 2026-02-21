# Meta Ads MCP Server

MCP (Model Context Protocol) server for Meta/Facebook Ads API. Manage campaigns, analytics, audiences, and creatives directly from Claude.

Built for **Scalers+** community. Python rewrite of [brijr/meta-mcp](https://github.com/brijr/meta-mcp) with 15+ bug fixes, async support, and typed models.

## Features

| Category | Tools | Description |
|----------|-------|-------------|
| **Campaigns** | 6 | List, create, update, pause, resume, delete |
| **Ad Sets** | 5 | List, create, update, pause, delete |
| **Ads** | 4 | List, create, update, delete |
| **Analytics** | 5 | Insights, compare (parallel), export CSV/JSON, daily trends, attribution |
| **Audiences** | 5 | Custom, lookalike, estimate size, delete |
| **Creatives** | 4 | List, create, upload image, preview |
| **OAuth** | 5 | Auth URL, code exchange, long-lived token, token info, validate |
| **Account** | 2 | List ad accounts, health check |

**36 tools total.**

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

```bash
export META_ACCESS_TOKEN="your_token_here"

# Optional (for OAuth flows)
export META_APP_ID="your_app_id"
export META_APP_SECRET="your_app_secret"
```

### 3. Run

```bash
python -m meta_ads_mcp.server
```

### 4. Connect to Claude

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "python",
      "args": ["-m", "meta_ads_mcp.server"],
      "env": {
        "META_ACCESS_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Getting a Meta Access Token

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create an app (Business type)
3. Add **Marketing API** product
4. Generate a User Access Token with `ads_management` and `ads_read` permissions
5. Use `refresh_to_long_lived_token` tool to extend it to 60 days

Or use the built-in OAuth tools:

```
generate_auth_url → open in browser → exchange_code_for_token → refresh_to_long_lived_token
```

## Tools Reference

### Campaigns

| Tool | Description |
|------|-------------|
| `list_campaigns` | List campaigns with status/objective filters |
| `create_campaign` | Create campaign (PAUSED by default) |
| `update_campaign` | Update name, status, budget, schedule |
| `pause_campaign` | Pause a campaign |
| `resume_campaign` | Activate a paused campaign |
| `delete_campaign` | Delete a campaign |

### Ad Sets

| Tool | Description |
|------|-------------|
| `list_ad_sets` | List ad sets by account or campaign |
| `create_ad_set` | Create ad set with targeting, budget, optimization |
| `update_ad_set` | Update targeting, budget, schedule |
| `pause_ad_set` | Pause an ad set |
| `delete_ad_set` | Delete an ad set |

### Ads

| Tool | Description |
|------|-------------|
| `list_ads` | List ads by account, campaign, or ad set |
| `create_ad` | Create ad linking creative to ad set |
| `update_ad` | Update ad status/name/creative |
| `delete_ad` | Delete an ad |

### Analytics

| Tool | Description |
|------|-------------|
| `get_insights` | Performance metrics with date ranges and breakdowns |
| `compare_performance` | Compare multiple objects side-by-side (async parallel) |
| `export_insights` | Export data as CSV or JSON |
| `get_daily_trends` | Daily breakdown with trend direction |
| `get_attribution_data` | Attribution window analysis |

### Audiences

| Tool | Description |
|------|-------------|
| `list_audiences` | List custom/lookalike audiences |
| `create_custom_audience` | Create custom audience (website, app, video, etc.) |
| `create_lookalike` | Create lookalike from source audience |
| `estimate_audience_size` | Estimate reach for targeting spec |
| `delete_audience` | Delete an audience |

### Creatives

| Tool | Description |
|------|-------------|
| `list_creatives` | List ad creatives |
| `create_creative` | Create with image/video and CTA |
| `upload_image` | Upload image from URL, returns hash |
| `preview_ad` | Preview creative in various formats |

### OAuth

| Tool | Description |
|------|-------------|
| `generate_auth_url` | Generate Facebook OAuth URL |
| `exchange_code_for_token` | Exchange auth code for access token |
| `refresh_to_long_lived_token` | Convert to 60-day token |
| `get_token_info` | Token validity, scopes, expiry |
| `validate_token` | Quick token validation |

### Account

| Tool | Description |
|------|-------------|
| `list_ad_accounts` | List all accessible ad accounts |
| `health_check` | Server + API connectivity check |

## Architecture

```
meta_ads_mcp/
├── server.py          # FastMCP server with lifespan
├── client.py          # Async httpx client (retry + rate limiting)
├── auth.py            # Token management, OAuth flows
├── models/
│   └── common.py      # Enums, constants, field defaults
├── tools/             # 36 MCP tools (8 modules)
│   ├── campaigns.py
│   ├── ad_sets.py
│   ├── ads.py
│   ├── analytics.py
│   ├── audiences.py
│   ├── creatives.py
│   ├── oauth.py
│   └── account.py
└── utils/
    ├── errors.py      # Typed error hierarchy
    ├── rate_limiter.py # Per-account scoring system
    ├── pagination.py   # Cursor + URL pagination
    └── formatting.py   # Markdown tables, currency
```

## Tech Stack

- **Python 3.12+**
- **FastMCP** — MCP server framework
- **httpx** — Async HTTP client
- **Pydantic v2** — Input validation
- **Meta Graph API v23.0**

## Improvements over Original

| Issue | Original (TypeScript) | This version |
|-------|----------------------|--------------|
| Stub tools | `delete_audience`, `update_audience` do nothing | All tools make real API calls |
| compare_performance | Sequential O(n) | Parallel via `asyncio.gather()` |
| Rate limit detection | Misclassified as auth error | Code-first priority (4, 17 before OAuthException) |
| Pagination | Stalls when cursor missing from URL | Supports both cursor and URL fallback |
| Date presets | Missing `last_7d`, `last_30d`, `last_90d` | All 20 Meta presets included |
| Types | `any` everywhere | Pydantic models + typed enums |
| JWT secret | Hardcoded default | Not needed (STDIO only) |
| Logging | `console.log` pollutes STDIO | Python logging to stderr |
| API version | Inconsistent v22/v23 | Single `META_API_VERSION` constant |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Run with coverage
pytest --cov=meta_ads_mcp --cov-report=term-missing
```

## License

MIT
