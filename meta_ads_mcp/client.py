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
    format_wait_it,
    is_rate_limit_error,
)
from meta_ads_mcp.utils.pagination import extract_next_cursor
from meta_ads_mcp.utils.rate_limiter import (
    HIGH_UTILIZATION_PCT,
    UsageSnapshot,
    normalize_account_key,
    parse_usage_headers,
    rate_limiter,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 60.0
# A throttling wait reported by Meta longer than this is not retried: the
# error is raised immediately with the wait time, and further calls for the
# same account are short-circuited until it elapses.
_MAX_RETRYABLE_WAIT = 60.0


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
            await self._wait_if_blocked(account_id)
            rate_limiter.check(account_id, is_write)

        return await self._execute_with_retry(
            method=method,
            url=url,
            params=merged_params,
            data=data,
            account_id=account_id,
        )

    async def _wait_if_blocked(self, account_id: str) -> None:
        """Do not call Meta for an account Meta told us to stay away from.

        Long blocks raise RateLimitError without sending any request; short
        ones (<= _MAX_RETRYABLE_WAIT) are simply waited out.
        """
        remaining = rate_limiter.blocked_seconds(account_id)
        if remaining <= 0:
            return
        if remaining > _MAX_RETRYABLE_WAIT:
            raise RateLimitError(
                f"l'account {account_id} è bloccato da Meta per limite di richieste. "
                f"Attendere {format_wait_it(remaining)} prima di riprovare "
                "(nessuna chiamata è stata inviata).",
                retry_after_seconds=remaining,
            )
        logger.warning(
            "Account %s temporarily blocked by Meta, waiting %.1fs", account_id, remaining
        )
        await asyncio.sleep(remaining)

    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        params: dict[str, Any],
        data: dict[str, Any] | None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute HTTP request with retry.

        Transient network errors use exponential backoff. Throttling errors
        honor the wait reported by Meta: waits longer than _MAX_RETRYABLE_WAIT
        are raised immediately, short ones are retried after that wait, and an
        unknown wait falls back to exponential backoff.
        """
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._http.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                )
                return self._handle_response(response, account_id)

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

            except RateLimitError as exc:
                wait = exc.retry_after_seconds
                if wait is not None and wait > _MAX_RETRYABLE_WAIT:
                    raise
                if attempt < _MAX_RETRIES:
                    if wait is not None:
                        delay = min(wait, _BACKOFF_MAX)
                    else:
                        delay = min(_BACKOFF_BASE * (2 ** (attempt + 2)), _BACKOFF_MAX)
                    logger.warning("Rate limited, waiting %.1fs", delay)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise MetaAdsMCPError(f"Unexpected failure after retries: {last_error}")

    def _handle_response(
        self, response: httpx.Response, account_id: str | None = None
    ) -> dict[str, Any]:
        """Parse response and raise typed errors for failures.

        Usage headers are read on every response (success and error) and the
        per-account state in ``rate_limiter`` is updated before the body is
        interpreted.
        """
        try:
            body = response.json()
        except Exception:
            self._observe_usage(response, account_id, throttled=False)
            if response.is_success:
                return {"raw": response.text}
            raise MetaAdsMCPError(
                f"HTTP {response.status_code}: Non-JSON error response from Meta API."
            )

        if isinstance(body, dict) and "error" in body:
            error_data = body["error"] if isinstance(body["error"], dict) else {}
            throttled = is_rate_limit_error(error_data)
            wait = self._observe_usage(response, account_id, throttled=throttled)
            raise classify_meta_error(error_data, retry_after_seconds=wait)

        self._observe_usage(response, account_id, throttled=False)
        return body

    def _observe_usage(
        self,
        response: httpx.Response,
        account_id: str | None,
        throttled: bool,
    ) -> float | None:
        """Update rate limit state from usage headers; never raises.

        Returns the wait in seconds Meta asked for (None if unknown).
        """
        try:
            snap = parse_usage_headers(response.headers)
            if not snap.has_data:
                return None
            return self._apply_usage(snap, account_id, throttled)
        except Exception:  # headers must never break a request
            logger.debug("Could not process usage headers", exc_info=True)
            return None

    @staticmethod
    def _apply_usage(
        snap: UsageSnapshot, account_id: str | None, throttled: bool
    ) -> float | None:
        # The header describes the object the request touched: attribute it to
        # the request's account; without one, use the BUC object ids.
        targets = [account_id] if account_id else list(snap.buc_by_object)
        label = normalize_account_key(account_id) if account_id else "app"

        account_pct = snap.account_pct
        if snap.buc_pct is not None:
            account_pct = max(account_pct or 0.0, snap.buc_pct)

        for target in targets:
            rate_limiter.record_usage(target, account_pct, snap.access_tier)

        if snap.max_pct is not None and snap.max_pct >= HIGH_UTILIZATION_PCT:
            logger.warning(
                "Meta API usage high (%s): %.0f%% of limit (tier: %s)",
                label, snap.max_pct, snap.access_tier or "unknown",
            )

        # Wait: BUC estimated_time_to_regain_access (minutes, converted) when
        # Meta says access is lost; otherwise reset_time_duration (seconds)
        # when throttled or the account is at 100%.
        wait: float | None = None
        if snap.regain_seconds and snap.regain_seconds > 0:
            wait = snap.regain_seconds
        elif (throttled or (snap.account_pct or 0.0) >= 100.0) and snap.reset_seconds:
            wait = snap.reset_seconds

        if wait:
            for target in targets:
                if account_id:
                    rate_limiter.block(target, wait)
                else:
                    seconds, _ = snap.buc_by_object[target]
                    rate_limiter.block(target, seconds or wait)
        elif snap.regain_seconds == 0 and not throttled:
            for target in targets:
                rate_limiter.unblock(target)
        return wait

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

    async def post_multipart(
        self,
        url: str,
        data: dict[str, Any],
        files: dict[str, tuple[str, bytes, str]] | None = None,
        account_id: str | None = None,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """POST a multipart form to a full URL (used for video chunk uploads).

        No automatic retry: a chunk upload is retried by the caller, which
        knows the current offset.
        """
        if account_id:
            await self._wait_if_blocked(account_id)
            rate_limiter.check(account_id, True)
        response = await self._http.post(
            url,
            params=self._auth.get_auth_params(),
            data=data,
            files=files,
            timeout=timeout,
        )
        return self._handle_response(response, account_id)

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
