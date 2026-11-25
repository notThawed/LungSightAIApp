"""Structured physician-requested laboratory tests for LungSightAI.

All lookups are hospital-scoped, checked against the database (not just session
state). Uploaded files are private objects in the `lab-results` Storage bucket.
An order belongs to its originating examination and optionally one follow-up.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image

from backend.supabase_client import admin_supabase

BUCKET = "lab-results"
MAX_FILE_SIZE = 10 * 1024 * 1024
TEST_OPTIONS = (
    "Complete Blood Count (CBC)",
    "C-Reactive Protein (CRP)",
    "Procalcitonin (PCT)",
    "Sputum Gram Stain",
    "Sputum Culture and Sensitivity",
    "Blood Culture",
    "Arterial Blood Gas (ABG)",
    "Serum Electrolytes",
    "Renal Function Tests (BUN / Creatinine)",
    "Respiratory Pathogen PCR Panel",
    "Influenza Test",
    "COVID-19 Test",
    "Legionella Urinary Antigen",
    "Pleural Fluid Analysis",
)

DOCTOR_ROLES = {1, 3, 6}  # Admin and radiologist access; enforce separately in UI.
VIEW_ROLES = {1, 3, 4, 6, 7}
STAFF_UPLOAD_ROLES = {1, 6, 7}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _first(table, field, value, columns="*"):
    rows = (admin_supabase.table(table).select(columns)
            .eq(field, value).limit(1).execute()).data or []
    return rows[0] if rows else None


def _actor(user_id, allowed_roles=VIEW_ROLES):
    if not user_id:
        raise PermissionError("Please sign in again.")
    profile = _first("user_profiles", "user_id", str(user_id),
                     "user_id,hospital_id,role_id,is_active")
    if not profile or profile.get("is_active") is False:
        raise PermissionError("Your account is unavailable or inactive.")
    role = int(profile.get("role_id") or 0)
    if role not in allowed_roles:
        raise PermissionError("Your role is not authorized for this action.")
    return profile


def _patient_context(patient_id, actor_id, roles=VIEW_ROLES):
    actor = _actor(actor_id, roles)
    patient = _first("patients", "patient_id", str(patient_id), "patient_id,hospital_id")
    if not patient:
        raise ValueError("Patient record was not found.")
    if int(actor["role_id"]) != 1 and str(actor.get("hospital_id")) != str(patient["hospital_id"]):
        raise PermissionError("You cannot access another hospital's patient records.")
    return patient, actor


def _exam_context(examination_id, actor_id, roles=VIEW_ROLES):
    exam = _first("examinations", "examination_id", str(examination_id),
                  "examination_id,patient_id,examination_type")
    if not exam:
        raise ValueError("Examination not found.")
    patient, actor = _patient_context(exam["patient_id"], actor_id, roles)
    return exam, patient, actor


def _follow_up_context(follow_up_id, actor_id, roles=VIEW_ROLES):
    fu = _first("follow_ups", "follow_up_id", str(follow_up_id),
                "follow_up_id,patient_id,source_examination_id,previous_follow_up_id,follow_up_examination_id,status")
    if not fu:
        raise ValueError("Follow-up was not found.")
    patient, actor = _patient_context(fu["patient_id"], actor_id, roles)
    return fu, patient, actor


def get_requests_for_examination(examination_id, actor_id):
    exam, patient, _ = _exam_context(examination_id, actor_id)
    return ((admin_supabase.table("lab_requests").select("*")
             .eq("origin_examination_id", exam["examination_id"])
             .eq("patient_id", patient["patient_id"])
             .order("requested_at").execute()).data or [])


def save_requested_labs(examination_id, actor_id, selected_tests):
    """Idempotently save tests on one physician-completed examination.

    Deselecting an unfulfilled order cancels it; uploaded results are preserved.
    A saved canceled test may be restored by selecting it again.
    """
    exam, patient, actor = _exam_context(examination_id, actor_id, DOCTOR_ROLES)
    tests = sorted({str(s).strip() for s in selected_tests if str(s).strip()})
    if any(len(s) < 2 or len(s) > 120 for s in tests):
        raise ValueError("Laboratory test labels must be between 2 and 120 characters.")
    if len(tests) > 30:
        raise ValueError("Please select no more than 30 tests per examination.")
    existing = get_requests_for_examination(examination_id, actor_id)
    current = {r["test_type"]: r for r in existing}
    for name in tests:
        old = current.get(name)
        if old:
            if old.get("status") == "Cancelled":
                (admin_supabase.table("lab_requests")
                 .update({"status": "Requested", "updated_at": _now()})
                 .eq("lab_request_id", old["lab_request_id"]).execute())
            continue
        (admin_supabase.table("lab_requests").insert({
            "patient_id": patient["patient_id"],
            "hospital_id": patient["hospital_id"],
            "origin_examination_id": exam["examination_id"],
            "test_type": name, "requested_by": actor["user_id"],
        }).execute())
    for name, old in current.items():
        if name in tests or old.get("status") != "Requested":
            continue
        result_rows = ((admin_supabase.table("lab_request_documents")
                        .select("document_id").eq("lab_request_id", old["lab_request_id"])
                        .limit(1).execute()).data or [])
        if result_rows:
            continue
        (admin_supabase.table("lab_requests")
         .update({"status": "Cancelled", "updated_at": _now()})
         .eq("lab_request_id", old["lab_request_id"]).execute())
    return len(tests)


def attach_pending_labs(examination_id, follow_up_id):
    """Associate only outstanding orders from the exact originating exam.

    The parent consult is not reused for later follow-ups: a new follow-up
    examination must explicitly request new tests for its next appointment.
    """
    fu = _first("follow_ups", "follow_up_id", follow_up_id,
                "follow_up_id,patient_id")
    exam = _first("examinations", "examination_id", examination_id,
                  "examination_id,patient_id")
    if not fu or not exam or str(fu["patient_id"]) != str(exam["patient_id"]):
        raise ValueError("Cannot associate laboratory orders with a different patient.")
    outstanding = ((admin_supabase.table("lab_requests").select("lab_request_id")
                    .eq("origin_examination_id", examination_id)
                    .eq("patient_id", fu["patient_id"])
                    .eq("status", "Requested")
                    .is_("follow_up_id", "null").execute()).data or [])
    for req in outstanding:
        (admin_supabase.table("lab_requests")
         .update({"follow_up_id": follow_up_id, "updated_at": _now()})
         .eq("lab_request_id", req["lab_request_id"])
         .is_("follow_up_id", "null").execute())
    return len(outstanding)


def _origin_for_fu(fu):
    previous_id = fu.get("previous_follow_up_id")
    if previous_id:
        previous = _first("follow_ups", "follow_up_id", previous_id,
                          "follow_up_examination_id")
        return (previous or {}).get("follow_up_examination_id")
    return fu.get("source_examination_id")


def _documents_for(request_id):
    return ((admin_supabase.table("lab_request_documents").select("*")
             .eq("lab_request_id", request_id).order("uploaded_at", desc=True)
             .execute()).data or [])


def get_requests_for_follow_up(follow_up_id, actor_id):
    fu, patient, _ = _follow_up_context(follow_up_id, actor_id)
    origin_id = _origin_for_fu(fu)
    # Orders already attached to the appointment are always included.
    linked = ((admin_supabase.table("lab_requests").select("*")
               .eq("follow_up_id", fu["follow_up_id"])
               .eq("patient_id", patient["patient_id"])
             .eq("hospital_id", patient["hospital_id"]).execute()).data or [])
    # Also find old, outstanding orders that predate appointment association.
    unassigned = []
    if origin_id:
        unassigned = ((admin_supabase.table("lab_requests").select("*")
                       .eq("origin_examination_id", origin_id)
                       .eq("patient_id", patient["patient_id"])
                       .eq("hospital_id", patient["hospital_id"])
                       .eq("status", "Requested")
                       .is_("follow_up_id", "null").execute()).data or [])
    by_id = {str(r["lab_request_id"]): r for r in linked + unassigned}
    result = []
    for req in by_id.values():
        if req["status"] == "Cancelled":
            continue
        req = dict(req)
        req["documents"] = _documents_for(req["lab_request_id"])
        result.append(req)
    return sorted(result, key=lambda x: x["test_type"].casefold())


def get_follow_up_for_examination(examination_id, actor_id):
    exam, patient, _ = _exam_context(examination_id, actor_id)
    rows = ((admin_supabase.table("follow_ups").select("follow_up_id")
             .eq("follow_up_examination_id", exam["examination_id"])
             .eq("patient_id", patient["patient_id"])
             .limit(1).execute()).data or [])
    return (rows[0] or {}).get("follow_up_id") if rows else None


def _validate_file(data, filename):
    """Validate a PDF or normalize a supported image to its filename format.

    Returns (extension, MIME type, validated bytes).
    """
    if not isinstance(data, bytes) or not data:
        raise ValueError("Please select a non-empty PDF, JPG, or PNG file.")
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("The maximum size is 10 MB per document.")

    ext = Path(filename).suffix.lower()
    mime = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(ext)
    if not mime:
        raise ValueError("Only PDF, JPG, JPEG, and PNG files are supported.")

    if ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("This file is not a valid PDF document.")
        return ext, mime, data

    expected_format = "PNG" if ext == ".png" else "JPEG"
    try:
        # verify() checks integrity, but the image must be reopened afterward.
        with Image.open(BytesIO(data)) as image:
            actual_format = image.format
            if actual_format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Unsupported image encoding.")
            if image.width * image.height > 25_000_000:
                raise ValueError("Image dimensions are too large.")
            image.verify()

        if actual_format == expected_format:
            return ext, mime, data

        # Convert the decoded pixels rather than simply renaming the file.
        with Image.open(BytesIO(data)) as image:
            image.load()
            if expected_format == "JPEG":
                image = image.convert("RGB")
            else:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            buffer = BytesIO()
            image.save(buffer, format=expected_format)
            normalized = buffer.getvalue()

        if len(normalized) > MAX_FILE_SIZE:
            raise ValueError("Converted image exceeds the 10 MB limit.")
        return ext, mime, normalized
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError(f"Cannot read the image safely: {exc}") from exc


def upload_lab_document(lab_request_id, follow_up_id, actor_id, filename, file_bytes):
    fu, patient, actor = _follow_up_context(follow_up_id, actor_id, STAFF_UPLOAD_ROLES)
    requests = get_requests_for_follow_up(follow_up_id, actor_id)
    request = next((r for r in requests if str(r["lab_request_id"]) == str(lab_request_id)), None)
    if request is None:
        raise PermissionError("Requested test does not belong to this appointment.")
    if request["status"] == "Cancelled":
        raise ValueError("Cannot attach a result to a canceled test.")
    ext, mime, file_bytes = _validate_file(file_bytes, filename)
    # Bind unassigned older orders to this appointment; guard against races.
    if not request.get("follow_up_id"):
        matched = ((admin_supabase.table("lab_requests")
                    .update({"follow_up_id": fu["follow_up_id"], "updated_at": _now()})
                    .eq("lab_request_id", lab_request_id)
                    .is_("follow_up_id", "null").execute()).data or [])
        if not matched:
            raise ValueError("This laboratory request was assigned elsewhere. Refresh and retry.")
    path = (f"{patient['hospital_id']}/{patient['patient_id']}/"
            f"{fu['follow_up_id']}/{request['lab_request_id']}/{uuid4().hex}{ext}")
    bucket = admin_supabase.storage.from_(BUCKET)
    bucket.upload(path, file_bytes, {"content-type": mime, "upsert": "false"})
    try:
        (admin_supabase.table("lab_request_documents").insert({
            "lab_request_id": request["lab_request_id"],
            "follow_up_id": fu["follow_up_id"],
            "patient_id": patient["patient_id"],
            "hospital_id": patient["hospital_id"],
            "storage_path": path,
            "original_filename": Path(filename).name[:255],
            "content_type": mime,
            "size_bytes": len(file_bytes),
            "uploaded_by": actor["user_id"],
        }).execute())
    except Exception:
        try:
            bucket.remove([path])
        except Exception:
            pass
        raise
    (admin_supabase.table("lab_requests")
     .update({"status": "Result Uploaded", "updated_at": _now()})
     .eq("lab_request_id", request["lab_request_id"]).execute())
    return path


def signed_lab_document_url(document_id, actor_id):
    doc = _first("lab_request_documents", "document_id", document_id)
    if not doc:
        raise ValueError("Document not found.")
    patient, _actor_profile = _patient_context(doc["patient_id"], actor_id)
    if str(patient["hospital_id"]) != str(doc["hospital_id"]):
        raise PermissionError("Document does not belong to this hospital.")
    # Check the hospital relationship, and that the referenced request and
    # follow-up are for the very same patient.
    request = _first("lab_requests", "lab_request_id", doc["lab_request_id"],
                     "lab_request_id,patient_id,hospital_id,follow_up_id")
    if (not request or str(request["patient_id"]) != str(doc["patient_id"])
            or str(request["hospital_id"]) != str(doc["hospital_id"])
            or str(request["follow_up_id"]) != str(doc["follow_up_id"])):
        raise PermissionError("Laboratory document association is invalid.")
    response = admin_supabase.storage.from_(BUCKET).create_signed_url(doc["storage_path"], 300)
    if isinstance(response, dict):
        return response.get("signedURL") or response.get("signedUrl") or response.get("signed_url")
    return getattr(response, "signed_url", None)

def delete_lab_document(document_id, follow_up_id, actor_id):
    """
    Permanently delete one laboratory result.

    1. Verify staff authorization and document ownership.
    2. Delete the matching database record.
    3. Verify that the database record is gone.
    4. Remove the file from Supabase Storage.
    5. Recalculate the laboratory request status.
    """

    fu, patient, actor = _follow_up_context(
        follow_up_id,
        actor_id,
        STAFF_UPLOAD_ROLES,
    )

    document_id = str(document_id)
    follow_up_id = str(follow_up_id)

    doc = _first(
        "lab_request_documents",
        "document_id",
        document_id,
    )

    if not doc:
        raise ValueError(
            "Document not found. It may already have been deleted."
        )

    req_id = str(doc["lab_request_id"])

    if (
        str(doc.get("follow_up_id")) != follow_up_id
        or str(doc.get("patient_id")) != str(patient["patient_id"])
        or str(doc.get("hospital_id")) != str(patient["hospital_id"])
    ):
        raise PermissionError(
            "This document does not belong to this appointment."
        )

    request = _first(
        "lab_requests",
        "lab_request_id",
        req_id,
        "lab_request_id,patient_id,hospital_id,follow_up_id",
    )

    if (
        not request
        or str(request.get("patient_id")) != str(patient["patient_id"])
        or str(request.get("hospital_id")) != str(patient["hospital_id"])
        or str(request.get("follow_up_id")) != follow_up_id
    ):
        raise PermissionError(
            "Laboratory request association is invalid."
        )

    path = str(doc.get("storage_path") or "")

    expected_prefix = (
        f"{patient['hospital_id']}/"
        f"{patient['patient_id']}/"
        f"{follow_up_id}/"
        f"{req_id}/"
    )

    if (
        not path.startswith(expected_prefix)
        or path == expected_prefix
    ):
        raise PermissionError(
            "Unexpected document storage path. Deletion blocked."
        )

    # STEP 1: Delete the exact database document.
    (
        admin_supabase.table("lab_request_documents")
        .delete()
        .eq("document_id", document_id)
        .eq("lab_request_id", req_id)
        .eq("follow_up_id", follow_up_id)
        .eq("patient_id", patient["patient_id"])
        .eq("hospital_id", patient["hospital_id"])
        .execute()
    )

    # STEP 2: Verify deletion using a fresh database query.
    still_exists = _first(
        "lab_request_documents",
        "document_id",
        document_id,
    )

    if still_exists:
        raise RuntimeError(
            "Database deletion was not completed. "
            "The document is still registered in Supabase."
        )

    # STEP 3: Recalculate status using remaining documents.
    remaining = _documents_for(req_id)

    new_status = (
        "Result Uploaded"
        if remaining
        else "Requested"
    )

    (
        admin_supabase.table("lab_requests")
        .update({
            "status": new_status,
            "updated_at": _now(),
        })
        .eq("lab_request_id", req_id)
        .eq("patient_id", patient["patient_id"])
        .eq("hospital_id", patient["hospital_id"])
        .execute()
    )

    # STEP 4: Remove the underlying Storage object.
    # If Storage fails, the database record remains deleted.
    # Report the failure for administrative cleanup.
    try:
        admin_supabase.storage.from_(BUCKET).remove([path])
    except Exception as exc:
        raise RuntimeError(
            "The laboratory document was deleted from the database, "
            "but its Storage file could not be removed. "
            "An administrator must clean up the orphaned file. "
            f"Storage error: {exc}"
        ) from exc

    return len(remaining)
