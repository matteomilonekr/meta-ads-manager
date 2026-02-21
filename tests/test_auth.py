"""Tests for AuthManager."""

from __future__ import annotations

import pytest

from meta_ads_mcp.auth import AuthManager, MetaAuthConfig, load_config_from_env


def test_auth_params(auth_manager: AuthManager):
    """Test auth params include token and appsecret_proof."""
    params = auth_manager.get_auth_params()
    assert params["access_token"] == "test_token_123"
    assert "appsecret_proof" in params


def test_auth_params_no_secret():
    """Test auth params without app secret."""
    config = MetaAuthConfig(access_token="test_token")
    auth = AuthManager(config)
    params = auth.get_auth_params()
    assert params["access_token"] == "test_token"
    assert "appsecret_proof" not in params


def test_generate_oauth_url(auth_manager: AuthManager):
    """Test OAuth URL generation."""
    url = auth_manager.generate_oauth_url()
    assert "dialog/oauth" in url
    assert "client_id=test_app_id" in url
    assert "ads_management" in url


def test_generate_oauth_url_no_app_id():
    """Test OAuth URL fails without app ID."""
    config = MetaAuthConfig(access_token="test")
    auth = AuthManager(config)
    with pytest.raises(ValueError, match="META_APP_ID"):
        auth.generate_oauth_url()


def test_generate_oauth_url_custom_scopes(auth_manager: AuthManager):
    """Test OAuth URL with custom scopes."""
    url = auth_manager.generate_oauth_url(scopes=["ads_read"])
    assert "ads_read" in url
    assert "ads_management" not in url


def test_generate_oauth_url_with_state(auth_manager: AuthManager):
    """Test OAuth URL includes state parameter."""
    url = auth_manager.generate_oauth_url(state="csrf_token_123")
    assert "state=csrf_token_123" in url


def test_token_exchange_params(auth_manager: AuthManager):
    """Test token exchange params."""
    params = auth_manager.get_token_exchange_params("auth_code_abc")
    assert params["client_id"] == "test_app_id"
    assert params["client_secret"] == "test_app_secret"
    assert params["code"] == "auth_code_abc"


def test_token_exchange_params_no_credentials():
    """Test token exchange fails without credentials."""
    config = MetaAuthConfig(access_token="test")
    auth = AuthManager(config)
    with pytest.raises(ValueError, match="META_APP_ID"):
        auth.get_token_exchange_params("code")


def test_long_lived_token_params(auth_manager: AuthManager):
    """Test long-lived token exchange params."""
    params = auth_manager.get_long_lived_token_params()
    assert params["grant_type"] == "fb_exchange_token"
    assert params["fb_exchange_token"] == "test_token_123"


def test_long_lived_token_params_custom_token(auth_manager: AuthManager):
    """Test long-lived token exchange with custom token."""
    params = auth_manager.get_long_lived_token_params("short_token")
    assert params["fb_exchange_token"] == "short_token"


def test_with_token_immutable(auth_manager: AuthManager):
    """Test with_token creates new instance (immutable pattern)."""
    new_auth = auth_manager.with_token("new_token")
    assert new_auth.access_token == "new_token"
    assert auth_manager.access_token == "test_token_123"  # Original unchanged


def test_load_config_from_env(monkeypatch):
    """Test loading config from environment."""
    monkeypatch.setenv("META_ACCESS_TOKEN", "env_token")
    monkeypatch.setenv("META_APP_ID", "env_app_id")
    config = load_config_from_env()
    assert config.access_token == "env_token"
    assert config.app_id == "env_app_id"
