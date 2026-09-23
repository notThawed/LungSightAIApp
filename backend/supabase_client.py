import os

from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv(Path(__file__).parent / ".env")


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


# ============================================================
# VALIDATE ENVIRONMENT
# ============================================================

if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL is missing from .env"
    )

if not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_KEY is missing from .env"
    )

if not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "SUPABASE_SECRET_KEY is missing from .env"
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

admin_supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


# ============================================================
# DEBUG
# ============================================================

print("SUPABASE CLIENT LOADED")
print(
    "ADMIN CLIENT EXISTS:",
    admin_supabase is not None,
)