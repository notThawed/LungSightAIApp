"""
Shared pytest setup.

Placeholder Supabase credentials are set BEFORE any backend module is
imported, so backend.supabase_client can be imported without a .env file
and no test can ever reach a real (possibly production) database:
load_dotenv() never overrides variables that are already set.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

for path in (PROJECT_ROOT, PROJECT_ROOT / "streamlit_app"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

PLACEHOLDER_ENV = {
    "SUPABASE_URL": "https://placeholder-not-real.supabase.co",
    "SUPABASE_KEY": "placeholder-anon-key",
    "SUPABASE_SECRET_KEY": "placeholder-secret-key",
}

for name, value in PLACEHOLDER_ENV.items():
    os.environ[name] = value

# Never download models (e.g. the ~600 MB CLIP model used by the X-ray
# validator) during tests; use the local Hugging Face cache or skip.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
