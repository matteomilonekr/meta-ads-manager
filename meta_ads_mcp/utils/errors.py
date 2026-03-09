"""Error hierarchy for Meta Ads MCP."""

from __future__ import annotations


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
    """API rate limit exceeded (error codes 4, 17, 32)."""

    def __init__(self, message: str, retry_after_seconds: int = 60) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit: {message}", code=4)


class ResourceNotFoundError(MetaAdsMCPError):
    """Resource not found."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Not found: {message}", code=803)


def classify_meta_error(error_data: dict) -> MetaAdsMCPError:
    """Convert a Meta API error response to the appropriate exception.

    Args:
        error_data: The 'error' object from a Meta API response.

    Returns:
        Typed MetaAdsMCPError subclass.
    """
    code = error_data.get("code", 0)
    subcode = error_data.get("error_subcode", 0)
    message = error_data.get("message", "Unknown error")
    error_type = error_data.get("type", "")

    # Rate limit errors (check first — Meta sometimes wraps these as OAuthException)
    if code in (4, 17, 32):
        return RateLimitError(message)

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
