import os

from pathlib import Path

import streamlit as st

from supabase import create_client, Client
from dotenv import load_dotenv


# ============================================================
# LOAD LOCAL ENVIRONMENT
# ============================================================
#
# This allows the application to continue working locally
# using:
#
# backend/.env
#
# Streamlit Cloud will use st.secrets instead.
# ============================================================

load_dotenv(
    Path(__file__).parent / ".env"
)


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

def get_secret(name):
    """
    Get a configuration value.

    Priority:
        1. Streamlit Secrets
        2. Environment variables / local .env

    This allows the same code to work both locally
    and on Streamlit Cloud.
    """

    # --------------------------------------------------------
    # Streamlit Cloud
    # --------------------------------------------------------

    try:

        value = st.secrets.get(name)

        if value:
            return value

    except Exception:

        # st.secrets may not be available when running
        # outside Streamlit.
        pass

    # --------------------------------------------------------
    # Local .env / environment variables
    # --------------------------------------------------------

    return os.getenv(name)


SUPABASE_URL = get_secret(
    "SUPABASE_URL"
)

SUPABASE_KEY = get_secret(
    "SUPABASE_KEY"
)

SUPABASE_SECRET_KEY = get_secret(
    "SUPABASE_SECRET_KEY"
)


# ============================================================
# VALIDATE CONFIGURATION
# ============================================================

if not SUPABASE_URL:

    raise RuntimeError(
        "SUPABASE_URL is missing. "
        "Add it to Streamlit Secrets or your local .env file."
    )


if not SUPABASE_KEY:

    raise RuntimeError(
        "SUPABASE_KEY is missing. "
        "Add it to Streamlit Secrets or your local .env file."
    )


if not SUPABASE_SECRET_KEY:

    raise RuntimeError(
        "SUPABASE_SECRET_KEY is missing. "
        "Add it to Streamlit Secrets or your local .env file."
    )


# ============================================================
# NORMAL SUPABASE CLIENT
# ============================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# ============================================================
# ADMIN SUPABASE CLIENT
# ============================================================
#
# IMPORTANT:
#
# SUPABASE_SECRET_KEY is the privileged server-side key.
# Never expose this value in frontend code or commit it
# to GitHub.
# ============================================================

admin_supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


# ============================================================
# DEBUG
# ============================================================
#
# Do NOT print the actual keys.
# These messages are safe to appear in Streamlit logs.
# ============================================================

print(
    "SUPABASE CLIENT LOADED"
)

print(
    "SUPABASE URL EXISTS:",
    bool(SUPABASE_URL)
)

print(
    "NORMAL CLIENT EXISTS:",
    supabase is not None
)

print(
    "ADMIN CLIENT EXISTS:",
    admin_supabase is not None
)