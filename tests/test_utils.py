"""Tests for utility modules."""

from __future__ import annotations

import pytest

from meta_ads_mcp.utils.errors import (
    AuthenticationError,
    MetaAdsMCPError,
    PermissionError,
    RateLimitError,
    ResourceNotFoundError,
    ValidationError,
    classify_meta_error,
)
from meta_ads_mcp.utils.formatting import (
    format_currency,
    format_number,
    format_percentage,
    format_table_markdown,
)
from meta_ads_mcp.utils.pagination import (
    PageInfo,
    extract_next_cursor,
    paginate_local,
)
from meta_ads_mcp.utils.rate_limiter import RateLimiter


# ── Error classification ─────────────────────────────────────────


class TestClassifyMetaError:
    def test_auth_error(self):
        err = classify_meta_error({"code": 190, "message": "Invalid token", "type": "OAuthException"})
        assert isinstance(err, AuthenticationError)

    def test_oauth_exception_type(self):
        err = classify_meta_error({"code": 999, "message": "Bad", "type": "OAuthException"})
        assert isinstance(err, AuthenticationError)

    def test_permission_error(self):
        err = classify_meta_error({"code": 200, "message": "No perm", "type": ""})
        assert isinstance(err, PermissionError)

    def test_validation_error(self):
        err = classify_meta_error({"code": 100, "message": "Bad param", "type": ""})
        assert isinstance(err, ValidationError)

    def test_rate_limit_error(self):
        err = classify_meta_error({"code": 4, "message": "Limit", "type": ""})
        assert isinstance(err, RateLimitError)

    def test_not_found_error(self):
        err = classify_meta_error({"code": 803, "message": "Not found", "type": ""})
        assert isinstance(err, ResourceNotFoundError)

    def test_generic_error(self):
        err = classify_meta_error({"code": 999, "message": "Unknown", "type": ""})
        assert isinstance(err, MetaAdsMCPError)
        assert err.code == 999


# ── Formatting ───────────────────────────────────────────────────


class TestFormatting:
    def test_format_currency(self):
        assert format_currency(5000) == "USD 50.00"
        assert format_currency(0) == "USD 0.00"
        assert format_currency("invalid") == "invalid"

    def test_format_currency_eur(self):
        assert format_currency(10050, "EUR") == "EUR 100.50"

    def test_format_number(self):
        assert format_number(1000) == "1,000"
        assert format_number(1234567) == "1,234,567"
        assert format_number(None) == "0"
        assert format_number(3.14) == "3.14"

    def test_format_percentage(self):
        assert format_percentage(0.0523) == "5.23%"
        assert format_percentage(None) == "0.00%"

    def test_format_table_empty(self):
        assert format_table_markdown([], ["a"]) == "_No data_"

    def test_format_table(self):
        rows = [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
        table = format_table_markdown(rows, ["a", "b"], {"a": "Col A", "b": "Col B"})
        assert "Col A" in table
        assert "| 1 | 2 |" in table
        assert "---" in table


# ── Pagination ───────────────────────────────────────────────────


class TestPagination:
    def test_extract_cursor_from_cursors(self):
        paging = {"cursors": {"after": "abc123"}}
        assert extract_next_cursor(paging) == "abc123"

    def test_extract_cursor_from_url(self):
        paging = {"next": "https://graph.facebook.com/v23.0/me?after=url_cursor"}
        assert extract_next_cursor(paging) == "url_cursor"

    def test_extract_cursor_none(self):
        assert extract_next_cursor(None) is None
        assert extract_next_cursor({}) is None
        assert extract_next_cursor({"cursors": {}}) is None

    def test_paginate_local(self):
        items = [1, 2, 3, 4, 5]
        page, info = paginate_local(items, limit=2, offset=0)
        assert page == [1, 2]
        assert info.total == 5
        assert info.count == 2
        assert info.has_more is True

    def test_paginate_local_last_page(self):
        items = [1, 2, 3]
        page, info = paginate_local(items, limit=10, offset=0)
        assert page == [1, 2, 3]
        assert info.has_more is False

    def test_paginate_local_with_offset(self):
        items = [1, 2, 3, 4, 5]
        page, info = paginate_local(items, limit=2, offset=3)
        assert page == [4, 5]
        assert info.offset == 3
        assert info.has_more is False

    def test_page_info_to_dict(self):
        info = PageInfo(total=10, count=5, offset=0, has_more=True, next_cursor="abc")
        d = info.to_dict()
        assert d["total"] == 10
        assert d["next_cursor"] == "abc"


# ── Rate limiter ─────────────────────────────────────────────────


class TestRateLimiter:
    def test_check_read(self):
        limiter = RateLimiter(max_score=100)
        limiter.check("acc_1", is_write=False)
        assert limiter.get_usage("acc_1") > 0

    def test_check_write_costs_more(self):
        limiter = RateLimiter(max_score=100)
        limiter.check("acc_1", is_write=False)
        usage_read = limiter.get_usage("acc_1")
        limiter.check("acc_1", is_write=True)
        usage_after_write = limiter.get_usage("acc_1")
        assert usage_after_write > usage_read * 2

    def test_is_near_limit(self):
        limiter = RateLimiter(max_score=10)
        for _ in range(9):
            limiter.check("acc_1", is_write=False)
        assert limiter.is_near_limit("acc_1", threshold=80.0)

    def test_separate_accounts(self):
        limiter = RateLimiter(max_score=100)
        limiter.check("acc_1", is_write=False)
        assert limiter.get_usage("acc_2") == 0.0
