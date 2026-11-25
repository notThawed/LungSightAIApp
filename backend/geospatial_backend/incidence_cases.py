"""Hospital-scoped first-recorded pneumonia patient counts, by PH calendar month.

Place in backend/backend_utils/incidence_cases.py.
Not an infection-onset date or a community-wide surveillance registry.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from backend.supabase_client import admin_supabase
from backend.geospatial_backend.patient_location_utils import (
    _all_patient_rows, _group_key, _psgc_lookup,
)

MANILA = ZoneInfo("Asia/Manila")
POSITIVE_LABELS = frozenset((
    "bacterial_pneumonia",
    "viral_pneumonia",
    "covid19_pneumonia",
    "pneumonia_unspecified",
))
ELIGIBLE_STATUSES = ["Completed", "Admitted", "Discharged"]


def _datetime(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MANILA)


def first_recorded_confirmed_cases(hospital_id: str, year: int, month: int) -> dict:
    """Count a patient once, in month of their earliest recorded confirmation.

    Avoids counting repeated positive follow-up examinations of the same patient
    as new cases. A subsequent independent pneumonia episode is not separately
    counted because this DB does not yet define episode onset/resolution.
    """
    if not hospital_id:
        raise ValueError("hospital_id is required")
    start = datetime(year, month, 1, tzinfo=MANILA)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=MANILA)
    end_utc = end.astimezone(timezone.utc).isoformat()

    patients = _all_patient_rows(
        hospital_id,
        "patient_id,psgc_barangay_code,province,city,barangay",
    )
    code_lookup = _psgc_lookup(patients)
    eligible = {
        str(p["patient_id"]): p for p in patients if _group_key(p, code_lookup)
    }
    earliest = {}
    ids = list(eligible)

    for beginning in range(0, len(ids), 100):
        chunk = ids[beginning:beginning + 100]
        offset = 0
        while True:
            exams = (
                admin_supabase.table("examinations")
                .select("patient_id,status,confirmed_label,reviewed_at,examination_date")
                .in_("patient_id", chunk)
                .in_("status", ELIGIBLE_STATUSES)
                .lt("examination_date", end_utc)
                .range(offset, offset + 999)
                .execute().data or []
            )
            for exam in exams:
                if exam.get("confirmed_label") not in POSITIVE_LABELS:
                    continue
                pid = str(exam["patient_id"])
                confirmed_at = _datetime(exam.get("reviewed_at")) or _datetime(exam.get("examination_date"))
                if not confirmed_at or confirmed_at >= end:
                    continue
                if pid not in earliest or confirmed_at < earliest[pid]:
                    earliest[pid] = confirmed_at
            if len(exams) < 1000:
                break
            offset += len(exams)

    counts = defaultdict(int)
    for pid, diagnosed_at in earliest.items():
        if start <= diagnosed_at < end:
            counts[_group_key(eligible[pid], code_lookup)] += 1
    return dict(counts)
