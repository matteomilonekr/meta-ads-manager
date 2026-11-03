"""Per-account rate limit tracking for Meta Graph API.

Two layers:

1. Meta's own signals (primary). Every response may carry usage headers
   (``X-Business-Use-Case-Usage``, ``X-Ad-Account-Usage``, ``X-App-Usage``,
   ``X-FB-Ads-Insights-Throttle``). ``parse_usage_headers`` reads them
   defensively and ``RateLimiter`` keeps, per ad account, the last utilization
   percentage, the ads API access tier and a "blocked until" timestamp.

2. A local point counter (secondary guard, warning only). Reads cost 1 point,
   writes 3 points. Meta documents a score limit per ad account: 9000 with
   decay 300 s for standard/full access, 60 for development access. The tier
   is not universal, so it is taken from ``ads_api_access_tier`` when Meta
   reports it and falls back to the standard value otherwise.

Documented units (Meta Graph API rate limiting docs):
``estimated_time_to_regain_access`` is in MINUTES, ``reset_time_duration`` is in
SECONDS. Usage percentages are whole or fractional percent of the limit.

Sources:
https://developers.facebook.com/docs/graph-api/overview/rate-limiting/
https://developers.facebook.com/docs/marketing-api/overview/rate-limiting/
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Score limits per ad account, from Meta's docs (read = 1, write = 3).
_STANDARD_MAX_SCORE = 9000  # standard / full access
_DEVELOPMENT_MAX_SCORE = 60  # development access
_DECAY_WINDOW_SECONDS = 300  # 5 minutes
_READ_COST = 1
_WRITE_COST = 3

# Header names (HTTP headers are case-insensitive; lowercase for lookups).
# The Marketing API page names the BUC header "X-Business-Use-Case", the Graph
# API page "X-Business-Use-Case-Usage": both are accepted.
_HDR_BUC = ("x-business-use-case-usage", "x-business-use-case")
_HDR_AD_ACCOUNT = "x-ad-account-usage"
_HDR_APP = "x-app-usage"
_HDR_INSIGHTS = "x-fb-ads-insights-throttle"

_DEVELOPMENT_TIER = "development_access"

# Utilization at or above this value is logged as a warning.
HIGH_UTILIZATION_PCT = 90.0


def normalize_account_key(account_id: str | int) -> str:
    """Normalize 'act_123' / '123' / 123 to the same key ('123')."""
    return str(account_id).strip().removeprefix("act_")


# ── Header parsing ───────────────────────────────────────────────────


def _as_number(value: Any) -> float | None:
    """Return a finite, non-negative float or None (bools/NaN/garbage -> None)."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _load_json(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _max_opt(*values: float | None) -> float | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


@dataclass
class UsageSnapshot:
    """Usage information extracted from one response's headers."""

    # Utilization percentages (None = header absent or unusable).
    app_pct: float | None = None
    account_pct: float | None = None
    buc_pct: float | None = None
    # Seconds. regain_seconds comes from BUC estimated_time_to_regain_access
    # (minutes * 60); 0.0 means "present and not blocked", None means unknown.
    regain_seconds: float | None = None
    # Seconds, from X-Ad-Account-Usage reset_time_duration.
    reset_seconds: float | None = None
    access_tier: str | None = None
    # BUC entries by business object id (normalized): regain seconds and pct.
    buc_by_object: dict[str, tuple[float, float | None]] = field(default_factory=dict)

    @property
    def max_pct(self) -> float | None:
        return _max_opt(self.app_pct, self.account_pct, self.buc_pct)

    @property
    def has_data(self) -> bool:
        return any(
            v is not None
            for v in (
                self.app_pct,
                self.account_pct,
                self.buc_pct,
                self.regain_seconds,
                self.reset_seconds,
                self.access_tier,
            )
        )


def _tier(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def parse_usage_headers(headers: Mapping[str, str] | None) -> UsageSnapshot:
    """Parse Meta usage headers. Never raises: bad input yields empty fields."""
    snap = UsageSnapshot()
    if headers is None:
        return snap
    try:
        _parse_into(headers, snap)
    except Exception:  # defensive: header parsing must never break a request
        logger.debug("Unexpected error while parsing usage headers", exc_info=True)
    return snap


def _parse_into(headers: Mapping[str, str], snap: UsageSnapshot) -> None:
    lowered = {str(k).lower(): v for k, v in headers.items()}

    def get(name: str) -> str | None:
        value = lowered.get(name)
        return value if isinstance(value, str) else None

    # X-App-Usage: {"call_count": 28, "total_time": 25, "total_cputime": 25} (percent)
    app = _load_json(get(_HDR_APP))
    if isinstance(app, dict):
        snap.app_pct = _max_opt(
            *(_as_number(app.get(k)) for k in ("call_count", "total_time", "total_cputime"))
        )

    # X-Ad-Account-Usage: acc_id_util_pct (percent), reset_time_duration (SECONDS)
    acc = _load_json(get(_HDR_AD_ACCOUNT))
    if isinstance(acc, dict):
        snap.account_pct = _as_number(acc.get("acc_id_util_pct"))
        snap.reset_seconds = _as_number(acc.get("reset_time_duration"))
        snap.access_tier = _tier(acc.get("ads_api_access_tier"))

    # X-FB-Ads-Insights-Throttle: app_id_util_pct, acc_id_util_pct, ads_api_access_tier
    ins = _load_json(get(_HDR_INSIGHTS))
    if isinstance(ins, dict):
        snap.app_pct = _max_opt(snap.app_pct, _as_number(ins.get("app_id_util_pct")))
        snap.account_pct = _max_opt(snap.account_pct, _as_number(ins.get("acc_id_util_pct")))
        snap.access_tier = snap.access_tier or _tier(ins.get("ads_api_access_tier"))

    # X-Business-Use-Case-Usage: {"<object id>": [{type, call_count, total_cputime,
    # total_time, estimated_time_to_regain_access (MINUTES), ads_api_access_tier}]}
    raw_buc = next((get(n) for n in _HDR_BUC if get(n)), None)
    buc = _load_json(raw_buc)
    if isinstance(buc, dict):
        for object_id, entries in buc.items():
            if not isinstance(entries, list):
                continue
            obj_regain: float | None = None
            obj_pct: float | None = None
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                minutes = _as_number(entry.get("estimated_time_to_regain_access"))
                if minutes is not None:
                    obj_regain = _max_opt(obj_regain, minutes * 60.0)
                obj_pct = _max_opt(
                    obj_pct,
                    *(
                        _as_number(entry.get(k))
                        for k in ("call_count", "total_time", "total_cputime")
                    ),
                )
                snap.access_tier = snap.access_tier or _tier(entry.get("ads_api_access_tier"))
            if obj_regain is not None or obj_pct is not None:
                snap.buc_by_object[normalize_account_key(object_id)] = (
                    obj_regain if obj_regain is not None else 0.0,
                    obj_pct,
                )
                snap.regain_seconds = _max_opt(snap.regain_seconds, obj_regain)
                snap.buc_pct = _max_opt(snap.buc_pct, obj_pct)


# ── Per-account state ────────────────────────────────────────────────


@dataclass
class _AccountState:
    """Rate limit state for a single ad account."""
    score: float = 0.0
    last_decay: float = field(default_factory=time.monotonic)
    # Meta-reported signals
    utilization_pct: float | None = None
    access_tier: str | None = None
    blocked_until: float = 0.0  # time.monotonic() timestamp; 0 = not blocked


class RateLimiter:
    """Tracks Meta's reported usage per account plus a local point counter.

    The local counter (read 1 point, write 3 points, decay by 50% per
    5-minute window) is a secondary guard that only logs a warning. Its limit is
    9000 for standard access and 60 for development access, as reported by
    ``ads_api_access_tier`` when available.
    """

    def __init__(self, max_score: int = _STANDARD_MAX_SCORE) -> None:
        self._max_score = max_score
        self._accounts: dict[str, _AccountState] = {}

    def _get_state(self, account_id: str) -> _AccountState:
        key = normalize_account_key(account_id)
        if key not in self._accounts:
            self._accounts[key] = _AccountState()
        return self._accounts[key]

    def _decay(self, state: _AccountState) -> None:
        """Apply exponential decay based on elapsed time."""
        now = time.monotonic()
        elapsed = now - state.last_decay
        if elapsed >= _DECAY_WINDOW_SECONDS:
            periods = elapsed / _DECAY_WINDOW_SECONDS
            state.score *= 0.5 ** periods
            state.last_decay = now

    def _limit_for(self, state: _AccountState) -> int:
        if state.access_tier == _DEVELOPMENT_TIER:
            return _DEVELOPMENT_MAX_SCORE
        return self._max_score

    def check(self, account_id: str, is_write: bool = False) -> None:
        """Record an API call and check if within limits (warning only).

        Args:
            account_id: The ad account ID.
            is_write: True for write operations (3 points), False for reads (1 point).
        """
        state = self._get_state(account_id)
        self._decay(state)

        cost = _WRITE_COST if is_write else _READ_COST
        state.score += cost

        limit = self._limit_for(state)
        if state.score > limit:
            logger.warning(
                "Local rate limit estimate exceeded for account %s: %.0f/%d (tier: %s)",
                account_id,
                state.score,
                limit,
                state.access_tier or "unknown",
            )

    def get_usage(self, account_id: str) -> float:
        """Get current local-counter usage percentage for an account."""
        state = self._get_state(account_id)
        self._decay(state)
        return (state.score / self._limit_for(state)) * 100

    def is_near_limit(self, account_id: str, threshold: float = 80.0) -> bool:
        """Check if an account is near the rate limit threshold."""
        return self.get_usage(account_id) >= threshold

    # ── Meta-reported state ──────────────────────────────────────────

    def record_usage(
        self,
        account_id: str,
        utilization_pct: float | None = None,
        access_tier: str | None = None,
    ) -> None:
        """Store the last utilization % and access tier reported by Meta."""
        state = self._get_state(account_id)
        if utilization_pct is not None:
            state.utilization_pct = utilization_pct
        if access_tier:
            state.access_tier = access_tier

    def get_reported_utilization(self, account_id: str) -> float | None:
        """Last utilization % reported by Meta headers (None if never seen)."""
        return self._get_state(account_id).utilization_pct

    def get_access_tier(self, account_id: str) -> str | None:
        """Last ads_api_access_tier reported by Meta (None if never seen)."""
        return self._get_state(account_id).access_tier

    def block(self, account_id: str, seconds: float) -> None:
        """Mark an account as blocked for ``seconds`` from now."""
        if seconds <= 0:
            return
        self._get_state(account_id).blocked_until = time.monotonic() + seconds

    def unblock(self, account_id: str) -> None:
        """Clear a block (Meta reported that access is available again)."""
        self._get_state(account_id).blocked_until = 0.0

    def blocked_seconds(self, account_id: str) -> float:
        """Seconds left before the account is allowed again (0 if not blocked)."""
        state = self._get_state(account_id)
        return max(0.0, state.blocked_until - time.monotonic())


# Module-level singleton
rate_limiter = RateLimiter()
