from datetime import date, datetime, time, timezone
import json

from backend.supabase_client import admin_supabase


# ============================================================
# FOLLOW-UP STATUS
# ============================================================

FOLLOW_UP_STATUSES = [
    "Scheduled",
    "Completed",
    "Missed",
    "Cancelled",
    "Rescheduled",
]


# ============================================================
# VALUE HELPERS
# ============================================================

def serialize_date(value):
    """
    Convert a Python date/datetime value into a
    PostgreSQL/JSON-safe date string.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


def serialize_time(value):
    """
    Convert a Python time/datetime value into a
    PostgreSQL/JSON-safe time string.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.time().strftime("%H:%M:%S")

    if isinstance(value, time):
        return value.strftime("%H:%M:%S")

    return str(value)


def serialize_datetime(value):
    """
    Convert Python date/time values into
    JSON-safe strings.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, time):
        return value.strftime("%H:%M:%S")

    return str(value)


def utc_now():
    """
    Return the current UTC timestamp as
    an ISO-formatted string.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# JSON SAFETY
# ============================================================

def make_json_safe(value):
    """
    Recursively convert values into types that
    Python's JSON encoder can safely serialize.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, time):
        return value.strftime("%H:%M:%S")

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    return str(value)


def validate_json_payload(payload):
    """
    Force a JSON serialization check before
    sending the payload to Supabase.
    """

    safe_payload = make_json_safe(payload)

    json.dumps(safe_payload)

    return safe_payload


# ============================================================
# FOLLOW-UP EXAMINATION SEQUENCE
# ============================================================

def get_next_follow_up_sequence(
    patient_id,
):
    """
    Get the next follow-up examination sequence
    number for a patient.

    Example:

        Existing:
            Follow-Up Examination 001
            Follow-Up Examination 002

        Returns:
            3

    Initial examinations do not use a sequence.

    The sequence is stored in:

        examinations.follow_up_sequence
    """

    if not patient_id:
        return None

    try:

        response = (
            admin_supabase
            .table("examinations")
            .select(
                "follow_up_sequence"
            )
            .eq(
                "patient_id",
                patient_id,
            )
            .not_.is_(
                "follow_up_sequence",
                "null",
            )
            .order(
                "follow_up_sequence",
                desc=True,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        # --------------------------------------------
        # NO PREVIOUS FOLLOW-UP EXAMINATIONS
        # --------------------------------------------

        if not rows:
            return 1

        highest_sequence = rows[0].get(
            "follow_up_sequence"
        )

        if highest_sequence is None:
            return 1

        return int(
            highest_sequence
        ) + 1

    except Exception as exc:

        print(
            "Failed to determine next "
            f"follow-up sequence: {exc}"
        )

        return None


def format_follow_up_examination_name(
    sequence,
):
    """
    Convert a numeric follow-up sequence into
    the display name used by the application.

    Examples:

        1  -> Follow-Up Examination 001
        2  -> Follow-Up Examination 002
        10 -> Follow-Up Examination 010
    """

    if sequence is None:
        return None

    try:

        sequence = int(sequence)

    except (TypeError, ValueError):

        return None

    return (
        f"Follow-Up Examination "
        f"{sequence:03d}"
    )


# ============================================================
# CREATE FOLLOW-UP
# ============================================================

def create_follow_up(
    patient_id,
    examination_id,
    follow_up_date,
    follow_up_time=None,
    notes=None,
    created_by=None,
):
    """
    Create a scheduled follow-up.

    examination_id refers to the ORIGINAL examination
    that resulted in the physician scheduling a follow-up.

    The value is stored as:

        source_examination_id

    follow_up_examination_id remains NULL until the
    patient actually returns and a new examination
    is created for the follow-up visit.
    """

    try:

        # ====================================================
        # NORMALIZE DATE
        # ====================================================

        serialized_date = serialize_date(
            follow_up_date
        )

        # ====================================================
        # NORMALIZE TIME
        # ====================================================

        serialized_time = serialize_time(
            follow_up_time
        )

        # ====================================================
        # BUILD PAYLOAD
        # ====================================================

        follow_up_data = {
            "patient_id": patient_id,

            "source_examination_id": examination_id,

            "follow_up_examination_id": None,

            "follow_up_date": serialized_date,

            "follow_up_time": serialized_time,

            "notes": (
                notes.strip()
                if isinstance(notes, str)
                and notes.strip()
                else None
            ),

            "status": "Scheduled",

            "created_by": created_by,
        }

        # ====================================================
        # JSON SAFETY
        # ====================================================

        follow_up_data = validate_json_payload(
            follow_up_data
        )

        # ====================================================
        # FINAL DATE/TIME SAFETY CHECK
        # ====================================================

        if not isinstance(
            follow_up_data.get(
                "follow_up_date"
            ),
            (str, type(None)),
        ):
            raise TypeError(
                "follow_up_date was not converted "
                "to a JSON-safe string."
            )

        if not isinstance(
            follow_up_data.get(
                "follow_up_time"
            ),
            (str, type(None)),
        ):
            raise TypeError(
                "follow_up_time was not converted "
                "to a JSON-safe string."
            )

        # ====================================================
        # INSERT
        # ====================================================

        response = (
            admin_supabase
            .table("follow_ups")
            .insert(follow_up_data)
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Follow-up could not be created."
                ),
            }

        return {
            "success": True,
            "message": (
                "Follow-up scheduled successfully."
            ),
            "data": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# LINK FOLLOW-UP TO RE-EXAMINATION
# ============================================================

def link_follow_up_examination(
    follow_up_id,
    follow_up_examination_id,
):
    """
    Link a follow-up appointment to the NEW examination
    created when the patient actually returns.

    Relationship:

        source_examination_id
            ↓
        Original examination

        follow_up_examination_id
            ↓
        New follow-up examination
    """

    try:

        if not follow_up_id:

            return {
                "success": False,
                "message": (
                    "Follow-up ID is required."
                ),
            }

        if not follow_up_examination_id:

            return {
                "success": False,
                "message": (
                    "Follow-up examination ID "
                    "is required."
                ),
            }

        follow_up_data = {
            "follow_up_examination_id": (
                follow_up_examination_id
            ),
            "updated_at": utc_now(),
        }

        follow_up_data = validate_json_payload(
            follow_up_data
        )

        response = (
            admin_supabase
            .table("follow_ups")
            .update(follow_up_data)
            .eq(
                "follow_up_id",
                follow_up_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Follow-up could not be linked "
                    "to the re-examination."
                ),
            }

        return {
            "success": True,
            "message": (
                "Follow-up examination linked "
                "successfully."
            ),
            "data": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# UPDATE FOLLOW-UP
# ============================================================

def update_follow_up(
    follow_up_id,
    follow_up_date=None,
    follow_up_time=None,
    notes=None,
    status=None,
):
    """
    Update an existing follow-up.

    Only supplied fields are updated.
    """

    try:

        follow_up_data = {}

        if follow_up_date is not None:

            follow_up_data[
                "follow_up_date"
            ] = serialize_date(
                follow_up_date
            )

        if follow_up_time is not None:

            follow_up_data[
                "follow_up_time"
            ] = serialize_time(
                follow_up_time
            )

        if notes is not None:

            follow_up_data[
                "notes"
            ] = notes

        if status is not None:

            if status not in FOLLOW_UP_STATUSES:

                return {
                    "success": False,
                    "message": (
                        "Invalid follow-up status."
                    ),
                }

            follow_up_data[
                "status"
            ] = status

        follow_up_data[
            "updated_at"
        ] = utc_now()

        follow_up_data = validate_json_payload(
            follow_up_data
        )

        response = (
            admin_supabase
            .table("follow_ups")
            .update(follow_up_data)
            .eq(
                "follow_up_id",
                follow_up_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Follow-up not found or "
                    "could not be updated."
                ),
            }

        return {
            "success": True,
            "message": (
                "Follow-up updated successfully."
            ),
            "data": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# UPDATE FOLLOW-UP STATUS
# ============================================================

def update_follow_up_status(
    follow_up_id,
    status,
):
    """
    Update only the status of a follow-up.
    """

    try:

        if status not in FOLLOW_UP_STATUSES:

            return {
                "success": False,
                "message": (
                    "Invalid follow-up status."
                ),
            }

        follow_up_data = {
            "status": status,
            "updated_at": utc_now(),
        }

        follow_up_data = validate_json_payload(
            follow_up_data
        )

        response = (
            admin_supabase
            .table("follow_ups")
            .update(follow_up_data)
            .eq(
                "follow_up_id",
                follow_up_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Follow-up not found."
                ),
            }

        return {
            "success": True,
            "message": (
                "Follow-up status updated."
            ),
            "data": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# RESCHEDULE FOLLOW-UP
# ============================================================

def reschedule_follow_up(
    follow_up_id,
    new_date,
    new_time=None,
    notes=None,
):
    """
    Reschedule an existing follow-up.

    The original follow-up record is retained.
    Its status becomes Rescheduled.
    """

    try:

        follow_up_data = {
            "follow_up_date": serialize_date(
                new_date
            ),
            "follow_up_time": serialize_time(
                new_time
            ),
            "status": "Rescheduled",
            "updated_at": utc_now(),
        }

        if notes is not None:

            follow_up_data[
                "notes"
            ] = notes

        follow_up_data = validate_json_payload(
            follow_up_data
        )

        response = (
            admin_supabase
            .table("follow_ups")
            .update(follow_up_data)
            .eq(
                "follow_up_id",
                follow_up_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Follow-up could not be rescheduled."
                ),
            }

        return {
            "success": True,
            "message": (
                "Follow-up rescheduled successfully."
            ),
            "data": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# CANCEL FOLLOW-UP
# ============================================================

def cancel_follow_up(
    follow_up_id,
):
    """
    Cancel a follow-up without deleting the record.
    """

    return update_follow_up_status(
        follow_up_id,
        "Cancelled",
    )


# ============================================================
# COMPLETE FOLLOW-UP
# ============================================================

def complete_follow_up(
    follow_up_id,
    notes=None,
):
    """
    Mark a follow-up as completed.

    Completing the appointment and linking the
    follow-up examination are separate operations.
    """

    try:

        follow_up_data = {
            "status": "Completed",
            "updated_at": utc_now(),
        }

        if notes is not None:

            follow_up_data[
                "notes"
            ] = notes

        follow_up_data = validate_json_payload(
            follow_up_data
        )

        response = (
            admin_supabase
            .table("follow_ups")
            .update(follow_up_data)
            .eq(
                "follow_up_id",
                follow_up_id,
            )
            .execute()
        )

        if not response.data:

            return {
                "success": False,
                "message": (
                    "Follow-up could not be completed."
                ),
            }

        return {
            "success": True,
            "message": (
                "Follow-up marked as completed."
            ),
            "data": response.data[0],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# DELETE FOLLOW-UP
# ============================================================

def delete_follow_up(
    follow_up_id,
):
    """
    Permanently delete a follow-up.

    This should generally be avoided for clinical records.
    Prefer Cancelled when possible.
    """

    try:

        response = (
            admin_supabase
            .table("follow_ups")
            .delete()
            .eq(
                "follow_up_id",
                follow_up_id,
            )
            .execute()
        )

        return {
            "success": True,
            "message": (
                "Follow-up deleted successfully."
            ),
            "data": response.data or [],
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


# ============================================================
# GET SINGLE FOLLOW-UP
# ============================================================

def get_follow_up(
    follow_up_id,
):
    """
    Get one complete follow-up record.

    Includes:

        Patient
        Original/source examination
        Follow-up examination
    """

    if not follow_up_id:
        return None

    try:

        response = (
            admin_supabase
            .table("follow_ups")
            .select("""
                *,

                patients (
                    patient_id,
                    patient_code,
                    first_name,
                    middle_name,
                    last_name,
                    suffix,
                    date_of_birth,
                    sex,
                    contact_number,
                    hospital_id
                ),

                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    history_of_present_illness,
                    chief_complaint,
                    physical_examination,
                    diagnosis,
                    plans_orders,
                    disposition,
                    disposition_notes,
                    time_in,
                    time_of_discharge,
                    status,
                    created_by,
                    reviewed_by,
                    reviewed_at,
                    follow_up_sequence
                ),

                follow_up_examination:examinations!follow_ups_follow_up_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    history_of_present_illness,
                    chief_complaint,
                    physical_examination,
                    diagnosis,
                    plans_orders,
                    disposition,
                    disposition_notes,
                    time_in,
                    time_of_discharge,
                    status,
                    created_by,
                    reviewed_by,
                    reviewed_at,
                    follow_up_sequence
                )
            """)
            .eq(
                "follow_up_id",
                follow_up_id,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        return rows[0]

    except Exception as exc:

        print(
            f"Failed to fetch follow-up: {exc}"
        )

        return None


# ============================================================
# GET ALL FOLLOW-UPS FOR ONE PATIENT
# ============================================================

def get_follow_ups_by_patient(
    patient_id,
):
    """
    Get all follow-ups belonging to one patient.
    """

    if not patient_id:
        return []

    try:

        response = (
            admin_supabase
            .table("follow_ups")
            .select("""
                *,

                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    diagnosis,
                    status,
                    follow_up_sequence
                ),

                follow_up_examination:examinations!follow_ups_follow_up_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    diagnosis,
                    status,
                    follow_up_sequence
                )
            """)
            .eq(
                "patient_id",
                patient_id,
            )
            .order(
                "follow_up_date",
                desc=False,
            )
            .order(
                "follow_up_time",
                desc=False,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            "Failed to fetch patient follow-ups: "
            f"{exc}"
        )

        return []


# ============================================================
# GET UPCOMING FOLLOW-UPS FOR ONE PATIENT
# ============================================================

def get_upcoming_follow_ups_by_patient(
    patient_id,
):
    """
    Get scheduled/rescheduled follow-ups
    for one patient.
    """

    if not patient_id:
        return []

    try:

        response = (
            admin_supabase
            .table("follow_ups")
            .select("""
                *,

                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    diagnosis,
                    status,
                    follow_up_sequence
                ),

                follow_up_examination:examinations!follow_ups_follow_up_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    diagnosis,
                    status,
                    follow_up_sequence
                )
            """)
            .eq(
                "patient_id",
                patient_id,
            )
            .in_(
                "status",
                [
                    "Scheduled",
                    "Rescheduled",
                ],
            )
            .order(
                "follow_up_date",
                desc=False,
            )
            .order(
                "follow_up_time",
                desc=False,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            "Failed to fetch upcoming "
            f"follow-ups: {exc}"
        )

        return []


# ============================================================
# GET FOLLOW-UP HISTORY FOR ONE PATIENT
# ============================================================

def get_follow_up_history(
    patient_id,
):
    """
    Get completed, missed, cancelled,
    and rescheduled follow-up history.
    """

    if not patient_id:
        return []

    try:

        response = (
            admin_supabase
            .table("follow_ups")
            .select("""
                *,

                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    diagnosis,
                    status,
                    follow_up_sequence
                ),

                follow_up_examination:examinations!follow_ups_follow_up_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    diagnosis,
                    status,
                    follow_up_sequence
                )
            """)
            .eq(
                "patient_id",
                patient_id,
            )
            .in_(
                "status",
                [
                    "Completed",
                    "Missed",
                    "Cancelled",
                    "Rescheduled",
                ],
            )
            .order(
                "follow_up_date",
                desc=True,
            )
            .order(
                "follow_up_time",
                desc=True,
            )
            .execute()
        )

        return response.data or []

    except Exception as exc:

        print(
            "Failed to fetch follow-up history: "
            f"{exc}"
        )

        return []


# ============================================================
# GET ALL PATIENTS WITH FOLLOW-UPS
# ============================================================

def get_patients_with_follow_ups(
    hospital_id=None,
):
    """
    Get patients who have at least one follow-up.
    """

    try:

        query = (
            admin_supabase
            .table("follow_ups")
            .select("""
                patient_id,

                patients!inner (
                    patient_id,
                    patient_code,
                    first_name,
                    middle_name,
                    last_name,
                    suffix,
                    date_of_birth,
                    sex,
                    contact_number,
                    hospital_id,

                    hospitals (
                        hospital_id,
                        hospital_name,
                        hospital_code
                    )
                )
            """)
            .order(
                "follow_up_date",
                desc=False,
            )
        )

        if hospital_id:

            query = query.eq(
                "patients.hospital_id",
                hospital_id,
            )

        response = query.execute()

        rows = response.data or []

        patients = {}

        for row in rows:

            patient = row.get(
                "patients"
            )

            if isinstance(
                patient,
                list,
            ):
                patient = (
                    patient[0]
                    if patient
                    else None
                )

            if not patient:
                continue

            patient_id = patient.get(
                "patient_id"
            )

            if not patient_id:
                continue

            patients[
                patient_id
            ] = patient

        return list(
            patients.values()
        )

    except Exception as exc:

        print(
            "Failed to fetch patients with "
            f"follow-ups: {exc}"
        )

        return []


# ============================================================
# GET ALL FOLLOW-UPS FOR HOSPITAL
# ============================================================

def get_hospital_follow_ups(
    hospital_id=None,
    status=None,
):
    """
    Get follow-ups for a hospital.
    """

    try:

        query = (
            admin_supabase
            .table("follow_ups")
            .select("""
                *,

                patients!inner (
                    patient_id,
                    patient_code,
                    first_name,
                    middle_name,
                    last_name,
                    suffix,
                    date_of_birth,
                    sex,
                    contact_number,
                    hospital_id
                ),

                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    diagnosis,
                    status,
                    follow_up_sequence
                ),

                follow_up_examination:examinations!follow_ups_follow_up_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    diagnosis,
                    status,
                    follow_up_sequence
                )
            """)
            .order(
                "follow_up_date",
                desc=False,
            )
            .order(
                "follow_up_time",
                desc=False,
            )
        )

        if hospital_id:

            query = query.eq(
                "patients.hospital_id",
                hospital_id,
            )

        if status:

            query = query.eq(
                "status",
                status,
            )

        response = query.execute()

        return response.data or []

    except Exception as exc:

        print(
            "Failed to fetch hospital "
            f"follow-ups: {exc}"
        )

        return []


# ============================================================
# GET FOLLOW-UP COUNTS
# ============================================================

def get_follow_up_counts(
    hospital_id=None,
):
    """
    Return follow-up counts for dashboard/cards.
    """

    follow_ups = get_hospital_follow_ups(
        hospital_id=hospital_id,
    )

    counts = {
        "total": 0,
        "scheduled": 0,
        "completed": 0,
        "missed": 0,
        "cancelled": 0,
        "rescheduled": 0,
    }

    for follow_up in follow_ups:

        counts["total"] += 1

        status = (
            follow_up.get("status")
            or ""
        ).lower()

        if status == "scheduled":

            counts["scheduled"] += 1

        elif status == "completed":

            counts["completed"] += 1

        elif status == "missed":

            counts["missed"] += 1

        elif status == "cancelled":

            counts["cancelled"] += 1

        elif status == "rescheduled":

            counts["rescheduled"] += 1

    return counts


# ============================================================
# GET PATIENTS WITH UPCOMING FOLLOW-UPS
# ============================================================

def get_patients_with_upcoming_follow_ups(
    hospital_id=None,
):
    """
    Get unique patients who have at least one
    Scheduled or Rescheduled follow-up.

    Patients are ordered by their earliest
    upcoming follow-up date and time.
    """

    try:

        query = (
            admin_supabase
            .table("follow_ups")
            .select("""
                patient_id,
                follow_up_date,
                follow_up_time,
                status,

                patients!inner (
                    patient_id,
                    patient_code,
                    first_name,
                    middle_name,
                    last_name,
                    suffix,
                    date_of_birth,
                    sex,
                    contact_number,
                    hospital_id,

                    hospitals (
                        hospital_id,
                        hospital_name,
                        hospital_code
                    )
                )
            """)
            .in_(
                "status",
                [
                    "Scheduled",
                    "Rescheduled",
                ],
            )
            .order(
                "follow_up_date",
                desc=False,
            )
            .order(
                "follow_up_time",
                desc=False,
            )
        )

        if hospital_id:

            query = query.eq(
                "patients.hospital_id",
                hospital_id,
            )

        response = query.execute()

        rows = response.data or []

        patients = {}

        for row in rows:

            patient = row.get(
                "patients"
            )

            if isinstance(
                patient,
                list,
            ):
                patient = (
                    patient[0]
                    if patient
                    else None
                )

            if not patient:
                continue

            patient_id = patient.get(
                "patient_id"
            )

            if not patient_id:
                continue

            if patient_id not in patients:

                patient = dict(
                    patient
                )

                patient[
                    "upcoming_follow_up_date"
                ] = row.get(
                    "follow_up_date"
                )

                patient[
                    "upcoming_follow_up_time"
                ] = row.get(
                    "follow_up_time"
                )

                patient[
                    "upcoming_follow_up_status"
                ] = row.get(
                    "status"
                )

                patients[
                    patient_id
                ] = patient

        return list(
            patients.values()
        )

    except Exception as exc:

        print(
            "Failed to fetch patients with "
            f"upcoming follow-ups: {exc}"
        )

        return []