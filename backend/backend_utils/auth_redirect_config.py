"""Canonical invite/recovery redirect configuration for Streamlit & .env."""
from __future__ import annotations
import os

from backend.supabase_client import get_secret

PRODUCTION_REDIRECT = "https://notthawed.github.io/LungSightAuthRedirect/"
LOCAL_REDIRECT = PRODUCTION_REDIRECT + "?env=local"


def _setting(name: str) -> str:
    # An explicit process environment variable wins over Cloud secrets.
    # The backend Supabase client loads LungSightAIApp/.env on import.
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        value = get_secret(name)
    return str(value).strip() if value is not None else ""


def current_auth_environment() -> str:
    value = _setting("LUNGSIGHT_ENV").lower() or "production"
    if value not in ("local", "production"):
        raise RuntimeError("LUNGSIGHT_ENV must be 'local' or 'production'.")
    return value


def get_auth_redirect_url() -> str:
    """Strictly allow only the two controlled LungSightAuthRedirect URLs."""
    env = current_auth_environment()
    expected = LOCAL_REDIRECT if env == "local" else PRODUCTION_REDIRECT
    configured = _setting("INVITE_REDIRECT_URL")
    if not configured:
        return expected
    if configured != expected:
        raise RuntimeError(
            "Invitation redirect configuration does not match LUNGSIGHT_ENV. "
            "For local use: " + LOCAL_REDIRECT + "; for production use: " + PRODUCTION_REDIRECT
        )
    return expected
