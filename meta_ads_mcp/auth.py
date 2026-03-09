"""Authentication and token management for Meta Graph API."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from urllib.parse import urlencode

from meta_ads_mcp.models.common import META_API_VERSION, META_GRAPH_URL

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetaAuthConfig:
    """Meta API authentication configuration."""
    access_token: str
    app_id: str | None = None
    app_secret: str | None = None
    redirect_uri: str = "https://localhost:3000/callback"


def load_config_from_env() -> MetaAuthConfig:
    """Load auth config from environment variables.

    Required: META_ACCESS_TOKEN
    Optional: META_APP_ID, META_APP_SECRET, META_REDIRECT_URI
    """
    token = os.environ.get("META_ACCESS_TOKEN", "")
    if not token:
        logger.warning("META_ACCESS_TOKEN not set — OAuth tools will still work")

    return MetaAuthConfig(
        access_token=token,
        app_id=os.environ.get("META_APP_ID"),
        app_secret=os.environ.get("META_APP_SECRET"),
        redirect_uri=os.environ.get("META_REDIRECT_URI", "https://localhost:3000/callback"),
    )


class AuthManager:
    """Manages Meta API authentication, token validation, and OAuth flows."""

    def __init__(self, config: MetaAuthConfig) -> None:
        self._config = config

    @property
    def access_token(self) -> str:
        return self._config.access_token

    @property
    def app_id(self) -> str | None:
        return self._config.app_id

    @property
    def app_secret(self) -> str | None:
        return self._config.app_secret

    def get_auth_params(self) -> dict[str, str]:
        """Get query parameters for authenticated API calls."""
        params: dict[str, str] = {"access_token": self._config.access_token}
        proof = self._compute_appsecret_proof()
        if proof:
            params["appsecret_proof"] = proof
        return params

    def _compute_appsecret_proof(self) -> str | None:
        """Compute appsecret_proof HMAC for enhanced security."""
        if not self._config.app_secret or not self._config.access_token:
            return None
        return hmac.new(
            self._config.app_secret.encode("utf-8"),
            self._config.access_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def generate_oauth_url(
        self,
        scopes: list[str] | None = None,
        state: str | None = None,
    ) -> str:
        """Generate Facebook OAuth authorization URL.

        Args:
            scopes: OAuth scopes to request.
            state: Optional state parameter for CSRF protection.

        Returns:
            Authorization URL string.
        """
        if not self._config.app_id:
            raise ValueError("META_APP_ID required for OAuth flow")

        default_scopes = ["ads_management", "ads_read", "business_management"]
        params = {
            "client_id": self._config.app_id,
            "redirect_uri": self._config.redirect_uri,
            "scope": ",".join(scopes or default_scopes),
            "response_type": "code",
        }
        if state:
            params["state"] = state
        return f"https://www.facebook.com/{META_API_VERSION}/dialog/oauth?{urlencode(params)}"

    def get_token_exchange_params(self, code: str) -> dict[str, str]:
        """Get params for exchanging auth code for access token."""
        if not self._config.app_id or not self._config.app_secret:
            raise ValueError("META_APP_ID and META_APP_SECRET required for code exchange")
        return {
            "client_id": self._config.app_id,
            "client_secret": self._config.app_secret,
            "redirect_uri": self._config.redirect_uri,
            "code": code,
        }

    def get_long_lived_token_params(self, short_token: str | None = None) -> dict[str, str]:
        """Get params for exchanging short-lived token for long-lived (60-day) token."""
        if not self._config.app_id or not self._config.app_secret:
            raise ValueError("META_APP_ID and META_APP_SECRET required for token exchange")
        return {
            "grant_type": "fb_exchange_token",
            "client_id": self._config.app_id,
            "client_secret": self._config.app_secret,
            "fb_exchange_token": short_token or self._config.access_token,
        }

    def with_token(self, new_token: str) -> AuthManager:
        """Create a new AuthManager with an updated token (immutable pattern)."""
        new_config = MetaAuthConfig(
            access_token=new_token,
            app_id=self._config.app_id,
            app_secret=self._config.app_secret,
            redirect_uri=self._config.redirect_uri,
        )
        return AuthManager(new_config)

    @property
    def token_url(self) -> str:
        return f"{META_GRAPH_URL}/oauth/access_token"

    @property
    def debug_token_url(self) -> str:
        return f"{META_GRAPH_URL}/debug_token"
