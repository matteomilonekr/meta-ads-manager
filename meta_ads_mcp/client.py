"""Meta Graph API async HTTP client with retry and rate limiting."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from meta_ads_mcp.auth import AuthManager
from meta_ads_mcp.models.common import META_GRAPH_URL
from meta_ads_mcp.utils.errors import (
    MetaAdsMCPError,
    RateLimitError,
    classify_meta_error,
)
from meta_ads_mcp.utils.pagination import extract_next_cursor
from meta_ads_mcp.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 60.0


class MetaAdsClient:
    """Async HTTP client for Meta Graph API with retry and rate limiting."""

    def __init__(
        self,
        auth: AuthManager,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._auth = auth
        self._timeout = timeout
        self._http = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    # ── Core request method ──────────────────────────────────────────

    async def request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        account_id: str | None = None,
        is_write: bool = False,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Meta Graph API with retry.

        Args:
            endpoint: API endpoint (e.g., 'me/adaccounts' or a full object ID).
            method: HTTP method.
            params: Query parameters (merged with auth params).
            data: POST body (form-encoded).
            account_id: For rate limiting tracking.
            is_write: True for write operations.

        Returns:
            Parsed JSON response.
        """
        url = f"{META_GRAPH_URL}/{endpoint}"
        auth_params = self._auth.get_auth_params()
        merged_params = {**auth_params, **(params or {})}

        if account_id:
            rate_limiter.check(account_id, is_write)

        return await self._execute_with_retry(
            method=method,
            url=url,
            params=merged_params,
            data=data,
        )

    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        params: dict[str, Any],
        data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Execute HTTP request with exponential backoff retry."""
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._http.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                )
                return self._handle_response(response)

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    delay = min(_BACKOFF_BASE * (2 ** attempt), _BACKOFF_MAX)
                    logger.warning(
                        "Transient error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, _MAX_RETRIES + 1, delay, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise MetaAdsMCPError(
                        f"Request failed after {_MAX_RETRIES + 1} attempts: {exc}"
                    ) from exc

            except RateLimitError:
                if attempt < _MAX_RETRIES:
                    delay = min(_BACKOFF_BASE * (2 ** (attempt + 2)), _BACKOFF_MAX)
                    logger.warning("Rate limited, waiting %.1fs", delay)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise MetaAdsMCPError(f"Unexpected failure after retries: {last_error}")

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse response and raise typed errors for failures."""
        try:
            body = response.json()
        except Exception:
            if response.is_success:
                return {"raw": response.text}
            raise MetaAdsMCPError(
                f"HTTP {response.status_code}: {response.text[:500]}"
            )

        if "error" in body:
            raise classify_meta_error(body["error"])

        return body

    # ── Convenience methods ──────────────────────────────────────────

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """GET request."""
        return await self.request(endpoint, "GET", params=params, account_id=account_id)

    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """POST request (write operation)."""
        return await self.request(
            endpoint, "POST", params=params, data=data,
            account_id=account_id, is_write=True,
        )

    async def delete(
        self,
        endpoint: str,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """DELETE request (write operation)."""
        return await self.request(
            endpoint, "DELETE", account_id=account_id, is_write=True,
        )

    # ── Pagination helpers ───────────────────────────────────────────

    async def get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        account_id: str | None = None,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated endpoint.

        Args:
            endpoint: API endpoint.
            params: Query parameters.
            account_id: For rate limiting.
            max_pages: Safety cap on number of pages.

        Returns:
            Flat list of all data items across pages.
        """
        all_items: list[dict[str, Any]] = []
        current_params = dict(params or {})
        pages_fetched = 0

        while pages_fetched < max_pages:
            result = await self.get(endpoint, params=current_params, account_id=account_id)
            data = result.get("data", [])
            all_items.extend(data)
            pages_fetched += 1

            paging = result.get("paging")
            next_cursor = extract_next_cursor(paging)
            if not next_cursor:
                break
            current_params["after"] = next_cursor

        return all_items

    # ── Account helpers ──────────────────────────────────────────────

    async def get_ad_accounts(self) -> list[dict[str, Any]]:
        """List all accessible ad accounts."""
        return await self.get_paginated(
            "me/adaccounts",
            params={"fields": "id,name,account_status,currency,timezone_name,business"},
        )

    async def validate_token(self) -> dict[str, Any]:
        """Validate the current access token by calling /me."""
        return await self.get("me")
