"""Error hierarchy for Meta Ads MCP."""

from __future__ import annotations

import math

# Throttling error codes documented by Meta
# (https://developers.facebook.com/docs/graph-api/overview/rate-limiting/ and
# https://developers.facebook.com/docs/marketing-api/overview/rate-limiting/):
#   4 app, 17 user, 32 Pages API, 613 custom limit,
#   80000 Ads Insights, 80001 Pages, 80002 Instagram, 80003 Custom Audience,
#   80004 Ads Management, 80005 LeadGen, 80006 Messenger,
#   80008 WhatsApp Business Management, 80009 Catalog Management, 80014 Catalog Batch.
RATE_LIMIT_CODES = frozenset({4, 17, 32, 613, 80000, 80001, 80002, 80003, 80004, 80005, 80006, 80008, 80009, 80014})
# Subcodes that only appear on throttling errors (613/1487742 ad account API
# limit, */2446079 ad account / BUC limit). Matched even if the code differs.
RATE_LIMIT_SUBCODES = frozenset({1487742, 2446079})


def format_wait_it(seconds: float) -> str:
    """Human-readable Italian wait time, rounded up ('circa 5 minuti')."""
    if seconds < 60:
        return f"circa {max(1, math.ceil(seconds))} secondi"
    minutes = math.ceil(seconds / 60)
    return "circa 1 minuto" if minutes == 1 else f"circa {minutes} minuti"


class MetaAdsMCPError(Exception):
    """Base error for all Meta Ads MCP errors."""

    def __init__(self, message: str, code: int | None = None) -> None:
        self.code = code
        super().__init__(message)


class AuthenticationError(MetaAdsMCPError):
    """Meta API authentication/authorization error (error code 190)."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Authentication error: {message}", code=190)


class PermissionError(MetaAdsMCPError):
    """Insufficient permissions (error codes 200, 10)."""

    def __init__(self, message: str, code: int = 200) -> None:
        super().__init__(f"Permission error: {message}", code=code)


class ValidationError(MetaAdsMCPError):
    """Invalid parameters (error code 100)."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Validation error: {message}", code=100)


class RateLimitError(MetaAdsMCPError):
    """API rate limit exceeded (see RATE_LIMIT_CODES).

    ``retry_after_seconds`` is the wait reported by Meta (usage headers), or
    None when Meta did not say how long to wait.
    """

    def __init__(
        self,
        message: str,
        retry_after_seconds: float | None = None,
        code: int = 4,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit: {message}", code=code)


class ResourceNotFoundError(MetaAdsMCPError):
    """Resource not found."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Not found: {message}", code=803)


def is_rate_limit_error(error_data: dict) -> bool:
    """True if a Meta 'error' object is a documented throttling error."""
    return (
        error_data.get("code", 0) in RATE_LIMIT_CODES
        or error_data.get("error_subcode", 0) in RATE_LIMIT_SUBCODES
    )


def classify_meta_error(
    error_data: dict, retry_after_seconds: float | None = None
) -> MetaAdsMCPError:
    """Convert a Meta API error response to the appropriate exception.

    Args:
        error_data: The 'error' object from a Meta API response.
        retry_after_seconds: Wait reported by Meta usage headers, if any
            (attached to RateLimitError only).

    Returns:
        Typed MetaAdsMCPError subclass.
    """
    code = error_data.get("code", 0)
    subcode = error_data.get("error_subcode", 0)
    message = error_data.get("message", "Unknown error")
    error_type = error_data.get("type", "")

    # Rate limit errors (check first — Meta sometimes wraps these as OAuthException)
    if is_rate_limit_error(error_data):
        wait = retry_after_seconds if retry_after_seconds and retry_after_seconds > 0 else None
        if wait is not None:
            message = f"{message} (Meta chiede di attendere {format_wait_it(wait)})"
        return RateLimitError(message, retry_after_seconds=wait, code=code or 4)

    # Validation errors — check BEFORE OAuthException because Meta often wraps
    # code-100 "Invalid parameter" errors with type "OAuthException"
    if code == 100:
        return ValidationError(message)

    # Permission errors
    if code in (200, 10):
        return PermissionError(message, code=code)

    # Authentication errors (code 190, or OAuthException without a more specific code)
    if code == 190 or "OAuthException" in error_type:
        return AuthenticationError(message)

    # Not found
    if code == 803 or subcode == 33:
        return ResourceNotFoundError(message)

    return MetaAdsMCPError(f"Meta API error ({code}): {message}", code=code)
