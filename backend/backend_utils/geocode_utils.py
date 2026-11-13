# backend/backend_utils/geocode_utils.py

"""
One-time geocoding for hospital addresses.

Uses Nominatim (OpenStreetMap) — free, no API key.
Rate-limited to comply with Nominatim's usage policy:
    https://operations.osmfoundation.org/policies/nominatim/

Run once with:
    python -m backend.backend_utils.geocode_utils
"""

import time
import requests

from backend.supabase_client import admin_supabase


# ============================================================
# CONFIG
# ============================================================

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    # Nominatim requires a User-Agent identifying your app.
    "User-Agent": "LungSight/1.0 (capstone project)",
}

# Nominatim's policy: no more than 1 request per second.
REQUEST_INTERVAL_SECONDS = 1.2

# Bias results to the Philippines.
COUNTRY_CODES = "ph"


# ============================================================
# GEOCODE
# ============================================================

def geocode_address(address: str):
    """
    Look up an address and return (latitude, longitude).

    Returns None when:
      - the address is empty/trash
      - Nominatim returns no matches
      - the request fails
    """

    if not address or not address.strip():
        return None

    # Reject obviously bad addresses early — saves API calls
    cleaned = address.strip().lower()

    if cleaned in ("asdasd", "n/a", "na", "none", "test", "-"):
        return None

    params = {
        "q": address,
        "format": "json",
        "limit": 1,
        "countrycodes": COUNTRY_CODES,
    }

    try:
        r = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        if not data:
            return None

        return float(data[0]["lat"]), float(data[0]["lon"])

    except Exception as exc:
        print(f"  ✗ geocode failed for '{address}': {exc}")
        return None


# ============================================================
# BACKFILL
# ============================================================

def backfill_hospital_coordinates(force=False):
    """
    Geocode every hospital whose latitude/longitude is NULL.

    force=True re-geocodes even hospitals that already
    have coordinates (useful after fixing an address).
    """

    query = (
        admin_supabase
        .table("hospitals")
        .select("hospital_id, hospital_name, address, latitude, longitude")
    )

    if not force:
        query = query.is_("latitude", "null")

    hospitals = query.execute().data or []

    print(f"\n{len(hospitals)} hospital(s) to geocode.\n")

    updated = 0
    skipped = 0
    failed = 0

    for h in hospitals:

        name = h.get("hospital_name") or "(unnamed)"
        address = h.get("address") or ""

        print(f"→ {name}")
        print(f"  address: {address}")

        result = geocode_address(address)

        if not result:
            print("  ✗ no match found\n")
            failed += 1
            time.sleep(REQUEST_INTERVAL_SECONDS)
            continue

        lat, lon = result

        (
            admin_supabase
            .table("hospitals")
            .update({
                "latitude": lat,
                "longitude": lon,
            })
            .eq("hospital_id", h["hospital_id"])
            .execute()
        )

        print(f"  ✓ {lat:.6f}, {lon:.6f}\n")
        updated += 1
        time.sleep(REQUEST_INTERVAL_SECONDS)

    print("=" * 50)
    print(f"Updated:  {updated}")
    print(f"Failed:   {failed}")
    print(f"Skipped:  {skipped}")
    print("=" * 50)


# ============================================================
# ENTRY POINT
# ============================================================

# def dry_run():
#     """Preview what would be geocoded without writing to DB."""
#     hospitals = (
#         admin_supabase
#         .table("hospitals")
#         .select("hospital_id, hospital_name, address")
#         .is_("latitude", "null")
#         .execute()
#         .data
#     ) or []

#     print(f"\n{len(hospitals)} hospitals need geocoding:\n")
#     for h in hospitals:
#         print(f"  • {h['hospital_name']}")
#         print(f"    {h['address']}")
#         print()


if __name__ == "__main__":
    backfill_hospital_coordinates()
