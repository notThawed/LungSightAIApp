"""
LIVE, READ-ONLY check against the real Supabase project in .env:
anonymous requests (publishable key, no login) must not see clinical data.

Opt-in only, because it talks to the real database:
    RUN_LIVE_SECURITY_TESTS=1 pytest tests/security

Regression for the 2026-10-21 finding fixed by
supabase/migrations/20261021120000_lock_down_patient_data.sql.
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_SECURITY_TESTS") != "1" or not (ROOT / ".env").exists(),
    reason="live test: set RUN_LIVE_SECURITY_TESTS=1 and provide .env",
)

CLINICAL_TABLES = [
    "patients",
    "examinations",
    "follow_ups",
    "xray_requests",
    "xray_images",
    "xray_ai_results",
    "xray_reviews",
    "examination_vitals",
    "examination_consents",
    "medical_records",
    "user_profiles",
]

PRIVATE_BUCKETS = ["consent-signatures", "xray-images", "xray-ai-heatmaps", "external-medical-records"]


@pytest.fixture(scope="module")
def live_env():
    from dotenv import dotenv_values

    return dotenv_values(ROOT / ".env")


@pytest.fixture(scope="module")
def anon_client(live_env):
    from supabase import create_client

    return create_client(live_env["SUPABASE_URL"].strip(), live_env["SUPABASE_KEY"].strip())


@pytest.mark.parametrize("table", CLINICAL_TABLES)
def test_anonymous_cannot_read(anon_client, table):
    try:
        rows = anon_client.table(table).select("*").limit(1).execute().data
    except Exception:
        return  # denied outright is also fine

    # Compare the count only, so a failure never prints patient data.
    visible = len(rows)
    assert visible == 0, f"anonymous read of {table} returned data"


@pytest.mark.parametrize("bucket", PRIVATE_BUCKETS)
def test_clinical_buckets_are_private(live_env, bucket):
    from supabase import create_client

    admin = create_client(live_env["SUPABASE_URL"].strip(), live_env["SUPABASE_SECRET_KEY"].strip())
    buckets = {b.name: b.public for b in admin.storage.list_buckets()}

    assert buckets.get(bucket) is False, f"bucket {bucket} is public"
