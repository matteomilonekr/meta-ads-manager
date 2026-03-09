"""Cursor-based pagination for Meta Graph API responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, parse_qs


@dataclass(frozen=True)
class PageInfo:
    """Pagination metadata."""
    total: int
    count: int
    offset: int
    has_more: bool
    next_cursor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "count": self.count,
            "offset": self.offset,
            "has_more": self.has_more,
            "next_cursor": self.next_cursor,
        }


def extract_next_cursor(paging: dict[str, Any] | None) -> str | None:
    """Extract the next page cursor from a Meta API paging object.

    Supports both explicit cursors and fallback to URL parsing.
    Fixes the original TypeScript bug where cursor-less URL pagination stalled.
    """
    if not paging:
        return None

    # Prefer explicit cursor
    cursors = paging.get("cursors", {})
    after = cursors.get("after")
    if after:
        return after

    # Fallback: parse cursor from next URL
    next_url = paging.get("next")
    if next_url:
        parsed = urlparse(next_url)
        params = parse_qs(parsed.query)
        after_list = params.get("after", [])
        if after_list:
            return after_list[0]

    return None


def paginate_local(
    items: list[Any],
    limit: int,
    offset: int = 0,
) -> tuple[list[Any], PageInfo]:
    """Apply local offset/limit pagination to a list.

    Args:
        items: Full list of items.
        limit: Max items to return.
        offset: Starting index.

    Returns:
        Tuple of (sliced items, PageInfo).
    """
    total = len(items)
    page = items[offset: offset + limit]
    return page, PageInfo(
        total=total,
        count=len(page),
        offset=offset,
        has_more=(offset + limit) < total,
    )
