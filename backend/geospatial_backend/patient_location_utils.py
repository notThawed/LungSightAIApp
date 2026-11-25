# LUNGSIGHT_PSGC_NO_MANUAL_GEO_V2
"""Privacy-conscious location grouping and hospital-scoped case counts.

Only clinician-confirmed pneumonia examinations contribute to case counts.
Patient-level locations never leave the Streamlit server.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
# LUNGSIGHT_GEOSPATIAL_RECORDS_FIX_20261118

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




def _normalized_place(value, kind=""):
    """Normalize spelling variants for grouping, not for database rewriting."""
    import re
    s = str(value or "").casefold().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = " ".join(s.split())
    if kind == "city":
        if s.startswith("city of "):
            s = s[8:]
        if s.endswith(" city"):
            s = s[:-5]
    elif kind == "barangay":
        s = re.sub(r"^(?:barangay|brgy)\s+", "", s)
    return s


def _place_tuple(row):
    return (
        _normalized_place(row.get("province")),
        _normalized_place(row.get("city"), "city"),
        _normalized_place(row.get("barangay"), "barangay"),
    )


def _psgc_lookup(rows):
    """Infer legacy-to-PSGC matches ONLY from coded patients in the same data.

    Ambiguous place names with different PSGC codes are intentionally NOT merged.
    """
    candidates = defaultdict(set)
    for row in rows:
        code = str(row.get("psgc_barangay_code") or "").strip()
        key = _place_tuple(row)
        if code and key[1] and key[2]:
            candidates[key].add(code)
    return {key: next(iter(codes)) for key, codes in candidates.items()
            if len(codes) == 1}


def _group_key(row, code_lookup):
    code = str(row.get("psgc_barangay_code") or "").strip()
    if code:
        return code
    place = _place_tuple(row)
    if not place[1] or not place[2]:
        return None
    matched = code_lookup.get(place)
    if matched:
        return matched
    # Keep unmatched legacy places visible; never merge unrelated localities.
    return "legacy:" + "|".join(place)


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
    """Observed barangays grouped by PSGC code where a verified local match exists."""
    patients = _all_patient_rows(
        hospital_id,
        "psgc_barangay_code,province,city,barangay,latitude,longitude,location_precision",
    )
    lookup = _psgc_lookup(patients)
    result = {}
    for row in patients:
        key = _group_key(row, lookup)
        if not key:
            continue
        # Prefer display names from coded rows; preserve validated coordinates.
        coded = bool(str(row.get("psgc_barangay_code") or "").strip())
        if key not in result:
            result[key] = {
                "barangay_id": key,
                "province": row.get("province") or "",
                "city": row.get("city") or "",
                "barangay": row.get("barangay") or "",
                "latitude": None,
                "longitude": None,
                "_coded_name": coded,
            }
        elif coded and not result[key]["_coded_name"]:
            for field in ("province", "city", "barangay"):
                result[key][field] = row.get(field) or result[key][field]
            result[key]["_coded_name"] = True
        if (row.get("location_precision") == "barangay"
                and row.get("latitude") is not None
                and row.get("longitude") is not None):
            result[key]["latitude"] = row["latitude"]
            result[key]["longitude"] = row["longitude"]
    for grouped in result.values():
        grouped.pop("_coded_name", None)
    return list(result.values())


def real_case_counts(hospital_id, year, month, age="All ages", sex="All"):
    """One unique clinician-confirmed patient per hospital/reporting month.

    Include admitted patients when a physician confirmed pneumonia; do not count
    raw AI results. A patient's currently stored residential location is used.
    """
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    patients = _all_patient_rows(
        hospital_id,
        "patient_id,date_of_birth,sex,psgc_barangay_code,province,city,barangay",
    )
    lookup = _psgc_lookup(patients)
    eligible = {
        str(p["patient_id"]): p for p in patients
        if _group_key(p, lookup)
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
                .in_("status", ["Completed", "Admitted", "Discharged"])
                .range(offset, offset + 999).execute().data or []
            )
            for exam in exams:
                if exam.get("confirmed_label") in ("bacterial_pneumonia", "viral_pneumonia", "covid19_pneumonia", "pneumonia_unspecified"):
                    confirmed.add(str(exam["patient_id"]))
            if len(exams) < 1000:
                break
            offset += len(exams)
    counts = defaultdict(int)
    for pid in confirmed:
        counts[_group_key(eligible[pid], lookup)] += 1
    return dict(counts)


def real_registered_patient_counts(hospital_id, year, month, age="All ages", sex="All"):
    """Count actual registered patients using the SAME barangay grouping as cases."""
    end = date(year + (month == 12), month % 12 + 1, 1)
    patients = _all_patient_rows(
        hospital_id,
        "psgc_barangay_code,province,city,barangay,date_of_birth,sex,created_at",
    )
    lookup = _psgc_lookup(patients)
    counts = defaultdict(int)
    for row in patients:
        key = _group_key(row, lookup)
        if not key or str(row.get("created_at") or "")[:10] >= end.isoformat():
            continue
        if sex != "All" and row.get("sex") != sex:
            continue
        if age != "All ages" and _age_group(row.get("date_of_birth"), year, month) != age:
            continue
        counts[key] += 1
    return dict(counts)
