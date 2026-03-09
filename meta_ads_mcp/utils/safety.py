"""Safety guardrails to prevent Meta account restrictions and bans.

Monitors write operations, enforces cooldowns, and prevents patterns
that Meta's automated systems flag as abusive or suspicious.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Limits — derived from Meta's documented and observed enforcement patterns
# ---------------------------------------------------------------------------
_MAX_CREATES_PER_HOUR = 25          # campaigns + ad sets + ads combined
_MAX_STATUS_CHANGES_PER_HOUR = 40   # pause/resume/delete
_MAX_BUDGET_CHANGES_PER_HOUR = 15   # budget updates
_MIN_SECONDS_BETWEEN_WRITES = 2.0   # basic write cooldown
_WINDOW_SECONDS = 3600              # 1-hour sliding window


@dataclass
class _WriteEvent:
    """A single recorded write operation."""
    kind: str          # "create", "status", "budget", "delete"
    timestamp: float
    account_id: str


class SafetyGuard:
    """Monitors write patterns and blocks operations that risk account bans.

    Tracks:
    - Creation rate (campaigns, ad sets, ads, audiences)
    - Status change rate (pause, resume, delete)
    - Budget change rate
    - Write cooldown (minimum gap between writes)
    """

    def __init__(self) -> None:
        self._events: list[_WriteEvent] = []
        self._last_write: float = 0.0

    def _prune(self) -> None:
        """Remove events older than the sliding window."""
        cutoff = time.monotonic() - _WINDOW_SECONDS
        self._events = [e for e in self._events if e.timestamp > cutoff]

    def _count(self, kind: str, account_id: str | None = None) -> int:
        """Count recent events of a given kind."""
        self._prune()
        return sum(
            1 for e in self._events
            if e.kind == kind and (account_id is None or e.account_id == account_id)
        )

    def check_write_allowed(
        self,
        kind: str,
        account_id: str,
    ) -> str | None:
        """Check if a write operation is safe to execute.

        Args:
            kind: Operation type — "create", "status", "budget", "delete".
            account_id: The ad account being modified.

        Returns:
            None if allowed, or an error message string if blocked.
        """
        self._prune()

        # Cooldown between writes
        now = time.monotonic()
        elapsed = now - self._last_write
        if self._last_write > 0 and elapsed < _MIN_SECONDS_BETWEEN_WRITES:
            return (
                f"Troppo veloce — attendi {_MIN_SECONDS_BETWEEN_WRITES - elapsed:.1f}s "
                f"tra una operazione di scrittura e l'altra per evitare restrizioni."
            )

        # Per-kind limits
        limits = {
            "create": (_MAX_CREATES_PER_HOUR, "creazioni"),
            "status": (_MAX_STATUS_CHANGES_PER_HOUR, "cambi di stato"),
            "budget": (_MAX_BUDGET_CHANGES_PER_HOUR, "modifiche budget"),
            "delete": (_MAX_CREATES_PER_HOUR, "eliminazioni"),
        }
        max_allowed, label = limits.get(kind, (_MAX_CREATES_PER_HOUR, "operazioni"))
        current = self._count(kind, account_id)

        if current >= max_allowed:
            return (
                f"Limite di sicurezza raggiunto: {current}/{max_allowed} {label} "
                f"nell'ultima ora per account {account_id}. "
                f"Attendere prima di continuare per evitare restrizioni Meta."
            )

        # Warning at 80%
        if current >= int(max_allowed * 0.8):
            logger.warning(
                "Safety warning: %d/%d %s in the last hour for %s",
                current, max_allowed, label, account_id,
            )

        return None

    def record_write(self, kind: str, account_id: str) -> None:
        """Record a completed write operation."""
        now = time.monotonic()
        self._events.append(_WriteEvent(kind=kind, timestamp=now, account_id=account_id))
        self._last_write = now

    def get_status(self, account_id: str) -> dict[str, str]:
        """Return current safety status for an account."""
        self._prune()
        return {
            "creates": f"{self._count('create', account_id)}/{_MAX_CREATES_PER_HOUR}",
            "status_changes": f"{self._count('status', account_id)}/{_MAX_STATUS_CHANGES_PER_HOUR}",
            "budget_changes": f"{self._count('budget', account_id)}/{_MAX_BUDGET_CHANGES_PER_HOUR}",
            "deletes": f"{self._count('delete', account_id)}/{_MAX_CREATES_PER_HOUR}",
        }


# Module-level singleton
safety_guard = SafetyGuard()
