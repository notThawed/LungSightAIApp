import os

from dotenv import load_dotenv
from supabase import create_client, Client


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing from .env")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing from .env")

if not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "SUPABASE_SECRET_KEY is missing from .env"
    )


# Normal client
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# Admin client
supabase_admin: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)


print("SUPABASE CLIENT LOADED")
print("ADMIN CLIENT EXISTS:", supabase_admin is not None)