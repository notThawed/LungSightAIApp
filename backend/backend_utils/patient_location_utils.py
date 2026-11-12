"""Structured patient residence and privacy-conscious case aggregation.

Use the privileged Supabase client only from the Streamlit server. Never expose
patient-level coordinates or diagnosis records to a browser-side map.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from backend.supabase_client import admin_supabase



def get_barangays():
    return (
        admin_supabase.table("geo_barangays")
        .select("barangay_id,province,city,barangay,latitude,longitude")
        .eq("is_active", True)
        .order("province")
        .order("city")
        .order("barangay")
        .execute().data or []
    )


def get_puroks(barangay_id):
    if not barangay_id:
        return []
    return (
        admin_supabase.table("geo_puroks")
        .select("purok")
        .eq("barangay_id", barangay_id)
        .eq("is_active", True)
        .order("purok")
        .execute().data or []
    )


def get_streets(barangay_id):
    if not barangay_id:
        return []
    return (
        admin_supabase.table("geo_streets")
        .select("street")
        .eq("barangay_id", barangay_id)
        .eq("is_active", True)
        .order("street")
        .execute().data or []
    )


def build_address(province, city, barangay, purok=None, street=None, details=None):
    parts = [details, street, purok, barangay, city, province, "Philippines"]
    return ", ".join(str(part).strip() for part in parts if part and str(part).strip())


def patient_location_fields(barangay_row, purok=None, street=None, details=None):
    """Store approximate barangay coordinates, explicitly not household coordinates."""
    if not barangay_row:
        raise ValueError("Select a barangay before saving the patient.")
    return {
        "province": barangay_row["province"],
        "city": barangay_row["city"],
        "barangay_id": barangay_row["barangay_id"],
        "purok": purok or None,
        "street": street or None,
        "address_details": details or None,
        "latitude": barangay_row.get("latitude"),
        "longitude": barangay_row.get("longitude"),
        "location_precision": "barangay",
        "address": build_address(
            barangay_row["province"], barangay_row["city"],
            barangay_row["barangay"], purok, street, details,
        ),
    }


def _age_group(birthdate, year, month):
    if not birthdate:
        return None
    try:
        dob = date.fromisoformat(str(birthdate)[:10])
    except (TypeError, ValueError):
        return None
    age = year - dob.year - ((month, 1) < (dob.month, dob.day))
    if age < 0:
        return None
    return "0–17" if age < 18 else "18–39" if age < 40 else "40–59" if age < 60 else "60+"


def _pneumonia_confirmed(exam):
    """Only explicit clinician-confirmed pneumonia labels; never AI predictions."""
    if exam.get("confirmed_label") in ("bacterial_pneumonia", "viral_pneumonia"):
        return True
    # Free-text diagnoses are deliberately NOT counted as confirmed cases.
    return False


def real_case_counts(hospital_id, year, month, age="All ages", sex="All"):
    """Return aggregate unique-patient counts for the month and selected hospital.

    One patient is counted at most once in the selected month. Results are not
    incidence estimates. No patient-level data is returned to the UI.
    """
    if not hospital_id:
        raise ValueError("Hospital context is required")

    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)

    # Supabase can limit responses to 1000 rows; paginate to avoid silent undercounts.
    patients = []
    offset = 0
    while True:
        batch = (
            admin_supabase.table("patients")
            .select("patient_id,date_of_birth,sex,barangay_id")
            .eq("hospital_id", hospital_id)
            .not_.is_("barangay_id", "null")
            .range(offset, offset + 999).execute().data or []
        )
        patients.extend(batch)
        if len(batch) < 1000:
            break
        offset += len(batch)

    patient_lookup = {str(p["patient_id"]): p for p in patients}
    if not patient_lookup:
        return {}

    # Filter at the server using the patient's hospital membership. Examinations
    # do not have hospital_id in the supplied schema, so join by patient_id.
    eligible = {
        patient_id: patient
        for patient_id, patient in patient_lookup.items()
        if (sex == "All" or patient.get("sex") == sex)
        and (age == "All ages" or _age_group(patient.get("date_of_birth"), year, month) == age)
    }
    confirmed = set()
    ids = list(eligible)
    for chunk_start in range(0, len(ids), 100):
        chunk = ids[chunk_start:chunk_start + 100]
        offset = 0
        while chunk:
            exams = (
                admin_supabase.table("examinations")
                .select("patient_id,status,confirmed_label,examination_date")
                .in_("patient_id", chunk)
                .gte("examination_date", start.isoformat())
                .lt("examination_date", end.isoformat())
                .in_("status", ["Completed", "Discharged"])
                .range(offset, offset + 999)
                .execute().data or []
            )
            for exam in exams:
                if _pneumonia_confirmed(exam):
                    confirmed.add(str(exam["patient_id"]))
            if len(exams) < 1000:
                break
            offset += len(exams)

    counts = defaultdict(int)
    for patient_id in confirmed:
        counts[patient_lookup[patient_id]["barangay_id"]] += 1
    return dict(counts)


def real_registered_patient_counts(hospital_id, year, month, age="All ages", sex="All"):
    """Count real hospital patients registered through selected month; no demo data."""
    if not hospital_id:
        raise ValueError("Hospital context is required")
    from collections import defaultdict
    end = date(year + (month == 12), month % 12 + 1, 1)
    counts = defaultdict(int)
    offset = 0
    while True:
        batch = (
            admin_supabase.table("patients")
            .select("patient_id,barangay_id,date_of_birth,sex,created_at")
            .eq("hospital_id", str(hospital_id))
            .not_.is_("barangay_id", "null")
            .lt("created_at", end.isoformat())
            .range(offset, offset + 999)
            .execute().data or []
        )
        for patient in batch:
            if sex != "All" and patient.get("sex") != sex:
                continue
            if age != "All ages" and _age_group(patient.get("date_of_birth"),year,month) != age:
                continue
            counts[str(patient["barangay_id"])] += 1
        if len(batch) < 1000:
            break
        offset += len(batch)
    return dict(counts)
