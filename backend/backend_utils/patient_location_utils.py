# LUNGSIGHT_PSGC_NO_MANUAL_GEO_V2
"""Privacy-conscious location grouping and hospital-scoped case counts.

Only clinician-confirmed pneumonia examinations contribute to case counts.
Patient-level locations never leave the Streamlit server.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date

from backend.supabase_client import admin_supabase


def location_key(row):
    """Stable PSGC code, with legacy name-only fallback until matched."""
    code = str(row.get("psgc_barangay_code") or "").strip()
    if code:
        return code
    province = str(row.get("province") or "").strip().casefold()
    city = str(row.get("city") or "").strip().casefold()
    barangay = str(row.get("barangay") or "").strip().casefold()
    if not barangay or not city:
        return None
    return f"legacy:{province}|{city}|{barangay}"


def _age_group(birthdate, year, month):
    if not birthdate:
        return None
    try:
        dob = date.fromisoformat(str(birthdate)[:10])
    except (ValueError, TypeError):
        return None
    age = year - dob.year - ((month, 1) < (dob.month, dob.day))
    if age < 0:
        return None
    return "0–17" if age < 18 else "18–39" if age < 40 else "40–59" if age < 60 else "60+"


def _all_patient_rows(hospital_id, fields):
    if not hospital_id:
        raise ValueError("Hospital ID is required")
    result = []
    offset = 0
    while True:
        batch = (
            admin_supabase.table("patients").select(fields)
            .eq("hospital_id", str(hospital_id))
            .range(offset, offset + 999).execute().data or []
        )
        result.extend(batch)
        if len(batch) < 1000:
            break
        offset += len(batch)
    return result


def catalog_by_hospital(hospital_id):
    """Only observed residential barangays; no manual reference tables."""
    patients = _all_patient_rows(
        hospital_id,
        "psgc_barangay_code,province,city,barangay,latitude,longitude,location_precision",
    )
    result = {}
    for row in patients:
        key = location_key(row)
        if not key:
            continue
        if key not in result:
            result[key] = {
                "barangay_id": key,
                "province": row.get("province") or "",
                "city": row.get("city") or "",
                "barangay": row.get("barangay") or "",
                "latitude": None,
                "longitude": None,
            }
        # Only validated barangay centroids; never expose precise home coordinates.
        if (row.get("location_precision") == "barangay"
                and row.get("latitude") is not None and row.get("longitude") is not None):
            result[key]["latitude"] = row["latitude"]
            result[key]["longitude"] = row["longitude"]
    return list(result.values())


def real_case_counts(hospital_id, year, month, age="All ages", sex="All"):
    """One confirmed unique patient per month, hospital scoped."""
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    patients = _all_patient_rows(
        hospital_id,
        "patient_id,date_of_birth,sex,psgc_barangay_code,province,city,barangay",
    )
    eligible = {
        str(p["patient_id"]): p for p in patients
        if location_key(p)
        and (sex == "All" or p.get("sex") == sex)
        and (age == "All ages" or _age_group(p.get("date_of_birth"), year, month) == age)
    }
    confirmed = set()
    ids = list(eligible)
    for beginning in range(0, len(ids), 100):
        chunk = ids[beginning:beginning + 100]
        offset = 0
        while True:
            exams = (
                admin_supabase.table("examinations")
                .select("patient_id,status,confirmed_label,examination_date")
                .in_("patient_id", chunk)
                .gte("examination_date", start.isoformat())
                .lt("examination_date", end.isoformat())
                .in_("status", ["Completed", "Discharged"])
                .range(offset, offset + 999).execute().data or []
            )
            for exam in exams:
                if exam.get("confirmed_label") in ("bacterial_pneumonia", "viral_pneumonia"):
                    confirmed.add(str(exam["patient_id"]))
            if len(exams) < 1000:
                break
            offset += len(exams)
    counts = defaultdict(int)
    for pid in confirmed:
        counts[location_key(eligible[pid])] += 1
    return dict(counts)


def real_registered_patient_counts(hospital_id, year, month, age="All ages", sex="All"):
    end = date(year + (month == 12), month % 12 + 1, 1)
    counts = defaultdict(int)
    for row in _all_patient_rows(hospital_id, "psgc_barangay_code,province,city,barangay,date_of_birth,sex,created_at"):
        key = location_key(row)
        if not key or str(row.get("created_at") or "")[:10] >= end.isoformat():
            continue
        if sex != "All" and row.get("sex") != sex:
            continue
        if age != "All ages" and _age_group(row.get("date_of_birth"), year, month) != age:
            continue
        counts[key] += 1
    return dict(counts)
