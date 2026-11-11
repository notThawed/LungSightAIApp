"""
Scoped data access for hospital reports (service-role client, server-side).

The Streamlit app reads through the service role, so this module IS the
isolation boundary: the hospital always comes from the database-verified
viewer (backend.audit.get_viewer_scope), never from the caller. Rows are
fetched per table in id batches — no SQL joins between clinical tables — so
nothing fans out before the per-exam reduction in calculations.py.
"""

import re
from dataclasses import dataclass

from backend import audit
from backend.reports.calculations import ReportInputs


RESOURCE = "hospital_reports"

PAGE = 1_000
ID_BATCH = 150
MAX_EXAMS = 20_000

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class ReportTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class ReportScope:
    user_id: str
    role: str
    hospital_id: str
    patient_level: bool


def _client():
    return audit._get_client()


def get_report_scope(requested_hospital_id=None):
    """
    Hospital Admin: always their own hospital (requested id ignored), with
    patient-level detail. Superadmin: the requested hospital, aggregates only.
    Everyone else: AuditAccessDenied (and an auth.permission_denied event).
    """

    scope = audit.get_viewer_scope(RESOURCE)

    if not scope["platform"]:
        return ReportScope(scope["user_id"], scope["role"], scope["hospital_id"], True)

    if not requested_hospital_id or not _UUID.match(str(requested_hospital_id)):
        raise ValueError("Select a hospital.")

    exists = (
        _client()
        .table("hospitals")
        .select("hospital_id")
        .eq("hospital_id", str(requested_hospital_id))
        .limit(1)
        .execute()
        .data
    )

    if not exists:
        raise ValueError("Hospital not found.")

    return ReportScope(scope["user_id"], scope["role"], str(requested_hospital_id), False)


def list_report_hospitals():
    """Hospital choices for the Superadmin selector."""

    audit.get_viewer_scope(RESOURCE)

    return (
        _client()
        .table("hospitals")
        .select("hospital_id, hospital_name")
        .order("hospital_name")
        .execute()
        .data
        or []
    )


# ============================================================
# FETCH HELPERS
# ============================================================

def _fetch_pages(build, order_column, cap=None):
    rows = []
    offset = 0

    while True:
        batch = build().order(order_column).range(offset, offset + PAGE - 1).execute().data or []
        rows.extend(batch)

        if cap is not None and len(rows) > cap:
            raise ReportTooLarge(
                f"This period has more than {cap:,} examinations. Choose a shorter period."
            )

        if len(batch) < PAGE:
            return rows

        offset += PAGE


def _fetch_by_ids(table, columns, id_column, ids, order_column):
    ids = sorted({str(i) for i in ids if i})
    rows = []

    for start in range(0, len(ids), ID_BATCH):
        chunk = ids[start:start + ID_BATCH]
        rows.extend(
            _fetch_pages(
                lambda chunk=chunk: _client().table(table).select(columns).in_(id_column, chunk),
                order_column,
            )
        )

    return rows


def _count(build):
    response = build().limit(1).execute()
    return response.count or 0


# ============================================================
# INPUTS
# ============================================================

def fetch_report_inputs(hospital_id, period, include_audit=True):
    start = period.start_utc.isoformat()
    end = period.end_utc.isoformat()

    hospital = (
        _client()
        .table("hospitals")
        .select("hospital_id, hospital_name, hospital_code, hospital_type, address")
        .eq("hospital_id", hospital_id)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0]

    exams = _fetch_pages(
        lambda: (
            _client()
            .table("examinations")
            .select(
                "examination_id, created_at, examination_date, status, examination_type, "
                "follow_up_sequence, disposition, severity_status, "
                "patients!inner(hospital_id, patient_code)"
            )
            .eq("patients.hospital_id", hospital_id)
            .gte("created_at", start)
            .lt("created_at", end)
        ),
        "examination_id",
        cap=MAX_EXAMS,
    )

    exam_ids = [e["examination_id"] for e in exams]

    requests = _fetch_by_ids(
        "xray_requests", "request_id, examination_id, status, requested_at",
        "examination_id", exam_ids, "request_id",
    )
    request_ids = [r["request_id"] for r in requests]

    images = _fetch_by_ids(
        "xray_images", "image_id, request_id, uploaded_at",
        "request_id", request_ids, "image_id",
    )

    ai_results = _fetch_by_ids(
        "xray_ai_results", "ai_result_id, image_id, ai_findings, pneumonia_type, ai_model_version, processed_at",
        "image_id", [i["image_id"] for i in images], "ai_result_id",
    )

    # findings is read only to test whether it is filled in; it never leaves calculations.py.
    reviews = _fetch_by_ids(
        "xray_reviews", "review_id, request_id, findings, reviewed_at",
        "request_id", request_ids, "review_id",
    )

    images_uploaded = _count(lambda: (
        _client()
        .table("xray_images")
        .select("image_id, xray_requests!inner(hospital_id)", count="exact")
        .eq("xray_requests.hospital_id", hospital_id)
        .gte("uploaded_at", start)
        .lt("uploaded_at", end)
    ))

    patients_registered = _count(lambda: (
        _client()
        .table("patients")
        .select("patient_id", count="exact")
        .eq("hospital_id", hospital_id)
        .gte("created_at", start)
        .lt("created_at", end)
    ))

    currently_admitted = _count(lambda: (
        _client()
        .table("examinations")
        .select("examination_id, patients!inner(hospital_id)", count="exact")
        .eq("patients.hospital_id", hospital_id)
        .eq("status", "Admitted")
    ))

    staff_rows = (
        _client()
        .table("user_profiles")
        .select("roles(role_name)")
        .eq("hospital_id", hospital_id)
        .eq("is_active", True)
        .execute()
        .data
        or []
    )
    active_staff = []
    for row in staff_rows:
        role = row.get("roles") or {}
        if isinstance(role, list):
            role = role[0] if role else {}
        active_staff.append({"role": role.get("role_name")})

    audit_rows = None
    if include_audit:
        audit_rows = audit.fetch_scoped_event_rows(
            {
                "hospital_id": hospital_id,
                "created_from": period.start_utc,
                "created_before": period.end_utc,
            },
            resource=RESOURCE,
        )
        audit_rows = [r for r in audit_rows if str(r.get("hospital_id")) == str(hospital_id)]

    return ReportInputs(
        hospital=hospital,
        exams=exams,
        requests=requests,
        images=images,
        ai_results=ai_results,
        reviews=reviews,
        images_uploaded=images_uploaded,
        patients_registered=patients_registered,
        currently_admitted=currently_admitted,
        active_staff=active_staff,
        audit_rows=audit_rows,
    )
