"""
One-time migration: generate follow_up_code for existing follow-ups
that don't have one, and populate previous_follow_up_id.

Run from project root:
    python scripts/backfill_follow_up_codes.py
"""

import sys
from pathlib import Path

# Add project root to sys.path so `backend` resolves correctly
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.supabase_client import admin_supabase
from backend.backend_utils.followup_utils import (
    generate_follow_up_code,
    find_previous_follow_up,
)


def backfill():
    response = (
        admin_supabase
        .table("follow_ups")
        .select(
            "follow_up_id, patient_id, source_examination_id, "
            "follow_up_date, follow_up_code, previous_follow_up_id"
        )
        .order("follow_up_date", desc=False)
        .execute()
    )

    rows = response.data or []
    missing_code = [r for r in rows if not r.get("follow_up_code")]
    missing_prev = [r for r in rows if not r.get("previous_follow_up_id")]

    print(
        f"Total: {len(rows)}, "
        f"missing code: {len(missing_code)}, "
        f"missing previous: {len(missing_prev)}"
    )

    for row in missing_code:
        code = generate_follow_up_code()
        if code:
            admin_supabase.table("follow_ups").update(
                {"follow_up_code": code}
            ).eq("follow_up_id", row["follow_up_id"]).execute()
            print(f"  {row['follow_up_id']} -> {code}")

    for row in missing_prev:
        prev_id = find_previous_follow_up(
            row["patient_id"], row["source_examination_id"]
        )
        if prev_id and prev_id != row["follow_up_id"]:
            admin_supabase.table("follow_ups").update(
                {"previous_follow_up_id": prev_id}
            ).eq("follow_up_id", row["follow_up_id"]).execute()
            print(f"  {row['follow_up_id']} -> prev {prev_id}")

    print("Done.")


if __name__ == "__main__":
    backfill()