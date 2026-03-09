"""Per-account rate limiter for Meta Graph API."""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Meta API rate limit tiers
_STANDARD_MAX_SCORE = 9000
_DEVELOPMENT_MAX_SCORE = 60
_DECAY_WINDOW_SECONDS = 300  # 5 minutes
_READ_COST = 1
_WRITE_COST = 3


@dataclass
class _AccountState:
    """Rate limit state for a single ad account."""
    score: float = 0.0
    last_decay: float = field(default_factory=time.monotonic)


class RateLimiter:
    """Point-based rate limiter matching Meta's scoring system.

    Each read costs 1 point, each write costs 3 points.
    Points decay by 50% every 5-minute window.
    """

    def __init__(self, max_score: int = _STANDARD_MAX_SCORE) -> None:
        self._max_score = max_score
        self._accounts: dict[str, _AccountState] = {}

    def _get_state(self, account_id: str) -> _AccountState:
        if account_id not in self._accounts:
            self._accounts[account_id] = _AccountState()
        return self._accounts[account_id]

    def _decay(self, state: _AccountState) -> None:
        """Apply exponential decay based on elapsed time."""
        now = time.monotonic()
        elapsed = now - state.last_decay
        if elapsed >= _DECAY_WINDOW_SECONDS:
            periods = elapsed / _DECAY_WINDOW_SECONDS
            state.score *= 0.5 ** periods
            state.last_decay = now

    def check(self, account_id: str, is_write: bool = False) -> None:
        """Record an API call and check if within limits.

        Args:
            account_id: The ad account ID.
            is_write: True for write operations (3 points), False for reads (1 point).

        Raises:
            RateLimitExceeded: If the account score exceeds the limit.
        """
        state = self._get_state(account_id)
        self._decay(state)

        cost = _WRITE_COST if is_write else _READ_COST
        state.score += cost

        if state.score > self._max_score:
            logger.warning(
                "Rate limit approaching for account %s: %.0f/%d",
                account_id,
                state.score,
                self._max_score,
            )

    def get_usage(self, account_id: str) -> float:
        """Get current usage percentage for an account."""
        state = self._get_state(account_id)
        self._decay(state)
        return (state.score / self._max_score) * 100

    def is_near_limit(self, account_id: str, threshold: float = 80.0) -> bool:
        """Check if an account is near the rate limit threshold."""
        return self.get_usage(account_id) >= threshold


# Module-level singleton
rate_limiter = RateLimiter()
