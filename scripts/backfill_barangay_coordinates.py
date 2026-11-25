"""One-time, cautious, PSGC-grouped coordinate backfill.

Run from repo root:
 python -m scripts.backfill_barangay_coordinates
 python -m scripts.backfill_barangay_coordinates --geocode
 python -m scripts.backfill_barangay_coordinates --geocode --apply

Dry run by default. Geoapify requires LUNGSIGHT_GEOAPIFY_API_KEY.
Only missing coordinate rows are updated. No patient PII sent to provider.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from backend.supabase_client import admin_supabase
from backend.geospatial_backend.barangay_geocoding import (
    _valid_coords, resolve_barangay_coordinates, lookup_existing_coordinates,
    geocoding_configured,
)


def _all_patients():
    result = []
    offset = 0
    while True:
        batch = (admin_supabase.table("patients")
                 .select("patient_id,psgc_barangay_code,barangay,city,province,latitude,longitude,location_precision")
                 .range(offset, offset + 999).execute().data or [])
        result.extend(batch)
        if len(batch) < 1000:
            break
        offset += len(batch)
    return result


def _load_overrides(path):
    """Optional manually verified barangay points; never include patient addresses."""
    overrides = {}
    if not path:
        return overrides
    with open(path, newline="", encoding="utf-8-sig") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            code = str(row.get("psgc_barangay_code") or "").strip()
            if not code or not code.isdigit() or code in overrides:
                raise ValueError(f"Invalid or duplicated PSGC code at CSV line {line_no}")
            if not _valid_coords(row.get("latitude"), row.get("longitude")):
                raise ValueError(f"Invalid/missing Philippine coordinates at CSV line {line_no}")
            if not all((row.get("barangay"), row.get("city"), row.get("province"))):
                raise ValueError(f"CSV line {line_no} needs barangay, city and province for review")
            overrides[code] = row
    return overrides


def run(*, apply=False, geocode=False, overrides_path=None, report="barangay_backfill_report.csv"):
    if geocode and not geocoding_configured():
        raise SystemExit("--geocode needs LUNGSIGHT_GEOAPIFY_API_KEY (or Streamlit secrets). No database changes made.")
    overrides = _load_overrides(overrides_path)
    patients = _all_patients()
    groups = defaultdict(list)
    for patient in patients:
        code = str(patient.get("psgc_barangay_code") or "").strip()
        if code.isdigit():
            groups[code].append(patient)
    report_rows = []
    updates = 0
    for code in sorted(groups):
        group = groups[code]
        missing = [r for r in group if r.get("latitude") is None or r.get("longitude") is None]
        if not missing:
            continue
        # Ensure every row with this PSGC code has a consistent human-readable locality.
        def norm(s):
            import re
            s = re.sub(r"[^a-z0-9]+", " ", str(s or "").casefold()).strip()
            if s.startswith("city of "):
                s = s[8:]
            if s.endswith(" city"):
                s = s[:-5]
            return s
        place_variants = {(norm(r.get("barangay")), norm(r.get("city")), norm(r.get("province"))) for r in group}
        place = next((r for r in group if all((r.get("barangay"),r.get("city"),r.get("province")))), group[0])
        name, city, province = (place.get(k) or "" for k in ("barangay", "city", "province"))
        point = None
        reason = "unresolved"
        if len(place_variants) > 1:
            reason = "conflicting_name_for_same_code_review_required"
        elif code in overrides:
            o = overrides[code]
            if (norm(o.get("barangay")),norm(o.get("city")),norm(o.get("province"))) != next(iter(place_variants)):
                reason = "override_name_mismatch"
            else:
                try:
                    known = lookup_existing_coordinates(code)
                except ValueError:
                    known = None
                    reason = "conflicting_stored_points_review_required"
                if reason != "conflicting_stored_points_review_required":
                    candidate = (round(float(o["latitude"]),5), round(float(o["longitude"]),5))
                    existing = (round(float(known["latitude"]),5), round(float(known["longitude"]),5)) if known else None
                    if existing and candidate != existing:
                        reason = "override_conflicts_with_existing_psgc_coordinates"
                    else:
                        point = {"latitude":candidate[0],"longitude":candidate[1],
                                 "location_precision":"barangay","source":"manual_verified"}
        else:
            try:
                point = lookup_existing_coordinates(code)
                if point is None and geocode:
                    point = resolve_barangay_coordinates(code, name, city, province, allow_api=True)
            except ValueError:
                reason = "conflicting_stored_points_review_required"
        if point:
            reason = point.get("source") or "resolved"
        for row in missing:
            state = "ready" if point else reason
            if apply and point:
                # Guard against concurrent updates and address changes.
                # 'or_' updates only records still missing one coordinate.
                result = (admin_supabase.table("patients")
                          .update({"latitude":point["latitude"],"longitude":point["longitude"],"location_precision":"barangay"})
                          .eq("patient_id",row["patient_id"])
                          .eq("psgc_barangay_code",code)
                          .or_("latitude.is.null,longitude.is.null")
                          .execute())
                if result.data:
                    updates += len(result.data)
                    state = "updated"
                else:
                    state = "not_updated_recheck"
            report_rows.append({"psgc_barangay_code":code,"barangay":name,"city":city,
                                "province":province,"status":state,
                                "latitude":point["latitude"] if point else "",
                                "longitude":point["longitude"] if point else "",
                                "source":reason})
        print(f"{code} {name} ({city}): {len(missing)} missing record(s); {reason}")
    path = Path(report)
    with path.open("w",newline="",encoding="utf-8") as f:
        columns = ["psgc_barangay_code","barangay","city","province","status","latitude","longitude","source"]
        writer=csv.DictWriter(f,fieldnames=columns)
        writer.writeheader()
        writer.writerows(report_rows)
    print(f"\nMode: {'APPLY' if apply else 'DRY RUN'}; missing records: {len(report_rows)}; updated: {updates}; report: {path}")
    return updates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true",help="Commit only verified coordinates to patients")
    parser.add_argument("--geocode",action="store_true",help="Use configured Geoapify for unresolved PSGC groups")
    parser.add_argument("--overrides",help="CSV of manually VERIFIED coordinate references")
    parser.add_argument("--report",default="barangay_backfill_report.csv",help="CSV status report path")
    args = parser.parse_args()
    run(apply=args.apply,geocode=args.geocode,overrides_path=args.overrides,report=args.report)
