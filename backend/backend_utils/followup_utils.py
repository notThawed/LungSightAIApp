from datetime import date, datetime, time, timezone
import json
import io
from PIL import Image, UnidentifiedImageError

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

def resolve_follow_up_chain(patient_id, examination_id):
    """
    Resolve the parent General Consult and the most recent
    preceding follow-up within that consultation's chain.

    Returns:
        (parent_general_consult_id, previous_follow_up_id)

    Raises ValueError when the supplied examination cannot
    be safely associated with a General Consult.
    """
    if not patient_id or not examination_id:
        raise ValueError("Patient and examination IDs are required.")

    exam_response = (
        admin_supabase.table("examinations")
        .select("examination_id, patient_id, examination_type")
        .eq("examination_id", examination_id)
        .eq("patient_id", patient_id)
        .limit(1)
        .execute()
    )

    examinations = exam_response.data or []

    if not examinations:
        raise ValueError("The examination was not found for this patient.")

    examination = examinations[0]
    exam_type = (examination.get("examination_type") or "").strip().lower()

    if exam_type in ("general consult", "general consultation"):
        # A newly selected General Consult starts its own chain.
        parent_id = examination_id

    elif exam_type.startswith("follow-up examination"):
        # Find the appointment whose completed examination
        # is the examination currently being reviewed.
        linked_response = (
            admin_supabase.table("follow_ups")
            .select("follow_up_id, source_examination_id")
            .eq("patient_id", patient_id)
            .eq("follow_up_examination_id", examination_id)
            .limit(1)
            .execute()
        )

        linked_rows = linked_response.data or []

        if not linked_rows:
            raise ValueError(
                "Cannot determine the original General Consult "
                "for this follow-up examination."
            )

        parent_id = linked_rows[0]["source_examination_id"]

    else:
        raise ValueError(
            "Follow-ups must originate from a General Consult "
            "or an examination in an existing follow-up chain."
        )

    # Validate the resolved parent.
    parent_response = (
        admin_supabase.table("examinations")
        .select("examination_id, examination_type, patient_id")
        .eq("examination_id", parent_id)
        .eq("patient_id", patient_id)
        .limit(1)
        .execute()
    )

    parents = parent_response.data or []

    if not parents:
        raise ValueError("Parent consultation could not be verified.")

    parent_type = (
        parents[0].get("examination_type") or ""
    ).strip().lower()

    if parent_type not in ("general consult", "general consultation"):
        raise ValueError(
            "The resolved parent is not a General Consult. "
            "Existing records may require chain repair."
        )

    # Find the most recent appointment in this SAME chain.
    previous_response = (
        admin_supabase.table("follow_ups")
        .select(
            "follow_up_id, follow_up_date, "
            "follow_up_time, status, created_at"
        )
        .eq("patient_id", patient_id)
        .eq("source_examination_id", parent_id)
        .order("created_at", desc=True)
        .execute()
    )

    candidates = previous_response.data or []

    # Exclude cancelled appointments from the chain predecessor.
    candidates = [
        row for row in candidates
        if row.get("status") != "Cancelled"
    ]

    previous_id = (
        candidates[0]["follow_up_id"]
        if candidates else None
    )

    return parent_id, previous_id



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
    Create a scheduled follow-up appointment.

    Chain relationships:

    source_examination_id:
        Always references the ORIGINAL General Consult
        that started this follow-up episode.

    previous_follow_up_id:
        References the immediately preceding follow-up
        appointment belonging to the SAME General Consult.

    follow_up_examination_id:
        Remains NULL until the patient returns and staff
        creates the actual Follow-Up Examination.

    A new General Consult starts a separate follow-up
    chain, even for the same patient.
    """

    try:
        # ====================================================
        # 1. VALIDATE REQUIRED INFORMATION
        # ====================================================

        if not patient_id:
            return {
                "success": False,
                "message": "Patient ID is required.",
            }

        if not examination_id:
            return {
                "success": False,
                "message": "Examination ID is required.",
            }

        if not follow_up_date:
            return {
                "success": False,
                "message": "Follow-up date is required.",
            }

        # ====================================================
        # 2. NORMALIZE DATE AND TIME
        # ====================================================

        serialized_date = serialize_date(
            follow_up_date
        )

        serialized_time = serialize_time(
            follow_up_time
        )

        # ====================================================
        # 3. RESOLVE FOLLOW-UP CHAIN
        # ====================================================

        # The helper identifies:
        #
        # parent_id:
        #     The original General Consult.
        #
        # previous_id:
        #     The most recently created follow-up appointment
        #     under that same General Consult.
        #
        # If the examination is a NEW General Consult,
        # its chain starts independently.

        parent_id, previous_id = resolve_follow_up_chain(
            patient_id=patient_id,
            examination_id=examination_id,
        )

        if not parent_id:
            return {
                "success": False,
                "message": (
                    "Could not determine the original "
                    "General Consultation."
                ),
            }

        # ====================================================
        # 4. GENERATE FOLLOW-UP CODE
        # ====================================================

        follow_up_code = generate_follow_up_code(
            patient_id
        )

        if not follow_up_code:
            return {
                "success": False,
                "message": (
                    "Could not generate a Follow-Up ID."
                ),
            }

        # ====================================================
        # 5. BUILD FOLLOW-UP PAYLOAD
        # ====================================================

        follow_up_data = {
            "patient_id": patient_id,

            "follow_up_code": follow_up_code,

            # ORIGINAL GENERAL CONSULTATION
            "source_examination_id": parent_id,

            # PREVIOUS APPOINTMENT IN THE SAME CHAIN
            "previous_follow_up_id": previous_id,

            # SET ONLY WHEN PATIENT RETURNS
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
        # 6. JSON SAFETY
        # ====================================================

        follow_up_data = validate_json_payload(
            follow_up_data
        )

        # ====================================================
        # 7. FINAL DATE/TIME VALIDATION
        # ====================================================

        if not isinstance(
            follow_up_data.get("follow_up_date"),
            (str, type(None)),
        ):
            raise TypeError(
                "follow_up_date was not converted "
                "to a JSON-safe string."
            )

        if not isinstance(
            follow_up_data.get("follow_up_time"),
            (str, type(None)),
        ):
            raise TypeError(
                "follow_up_time was not converted "
                "to a JSON-safe string."
            )

        # ====================================================
        # 8. INSERT FOLLOW-UP
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

        created_follow_up = response.data[0]

        # ====================================================
        # 9. SUCCESS
        # ====================================================

        return {
            "success": True,
            "message": (
                "Follow-up scheduled successfully."
            ),
            "data": created_follow_up,
        }

    except Exception as exc:
        return {
            "success": False,
            "message": (
                f"Failed to create follow-up: {exc}"
            ),
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
            .eq("follow_up_id", follow_up_id)
            .is_("follow_up_examination_id", "null")
            .in_("status", ["Scheduled", "Rescheduled"])
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

        if status in ("Cancelled", "Missed", "Rescheduled"):
            current = (admin_supabase.table("follow_ups")
                       .select("status, follow_up_examination_id")
                       .eq("follow_up_id", follow_up_id).limit(1).execute()).data or []
            if not current:
                return {"success": False, "message": "Follow-up not found."}
            if (current[0].get("status") not in ("Scheduled", "Rescheduled")
                    or current[0].get("follow_up_examination_id")):
                return {"success": False, "message": "Cannot change an attended or closed follow-up."}

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

        current = (admin_supabase.table("follow_ups")
                   .select("status, follow_up_examination_id")
                   .eq("follow_up_id", follow_up_id).limit(1).execute()).data or []
        if not current or current[0].get("status") not in ("Scheduled", "Rescheduled") or current[0].get("follow_up_examination_id"):
            return {"success": False, "message": "Cannot reschedule an attended or closed follow-up."}

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
                    emergency_contact_name,
                    emergency_contact_no,
                    emergency_contact_relationship,
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
                    chief_complaint,
                    history_of_present_illness,
                    physical_examination,
                    diagnosis,
                    plans_orders,
                    disposition,
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
                    chief_complaint,
                    history_of_present_illness,
                    physical_examination,
                    diagnosis,
                    plans_orders,
                    disposition,
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
                    chief_complaint,
                    history_of_present_illness,
                    physical_examination,
                    diagnosis,
                    plans_orders,
                    disposition,
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
                    emergency_contact_name,
                    emergency_contact_no,
                    emergency_contact_relationship,
                    hospital_id
                ),

                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id,
                    patient_id,
                    examination_type,
                    examination_date,
                    chief_complaint,
                    history_of_present_illness,
                    physical_examination,
                    diagnosis,
                    plans_orders,
                    disposition,
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

# ============================================================
# ============================================================
# FOLLOW-UP APPOINTMENT CODES (GLOBAL SEQUENCE + PATIENT CODE)
# ============================================================

def generate_follow_up_code(patient_id=None):
    """Reserve the next global appointment number for one patient.

    Example: patient LSP2026-002, global sequence 5 -> FULSP2026-002005.

    Unlike examinations.follow_up_sequence, this counter is global.
    A patient ID is mandatory; old maintenance scripts must supply it.
    Requires public.allocate_lungsight_followup_code(uuid) in Supabase.
    """
    if not patient_id:
        raise ValueError("Patient ID is required to generate a Follow-Up ID.")

    response = admin_supabase.rpc(
        "allocate_lungsight_followup_code", {"p_patient_id": str(patient_id)}
    ).execute()
    code = response.data
    if not isinstance(code, str) or not code.startswith("FU"):
        raise RuntimeError("Database did not return a valid Follow-Up ID.")
    return code


# ============================================================
# PREVIOUS FOLLOW-UP LOOKUP (chain)
# ============================================================

def find_previous_follow_up(patient_id, source_examination_id):
    """
    Find the most recent follow-up for this patient
    linked to the same parent examination.
    """

    if not patient_id or not source_examination_id:
        return None

    try:
        response = (
            admin_supabase
            .table("follow_ups")
            .select("follow_up_id, follow_up_date, created_at")
            .eq("patient_id", patient_id)
            .eq("source_examination_id", source_examination_id)
            .order("follow_up_date", desc=True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        return rows[0]["follow_up_id"] if rows else None

    except Exception as exc:
        print(f"Failed to find previous follow-up: {exc}")
        return None


# ============================================================
# GET FOLLOW-UP BY CODE
# ============================================================

def get_follow_up_by_code(code):
    """Fetch a follow-up by its human-readable code."""

    if not code:
        return None

    try:
        response = (
            admin_supabase
            .table("follow_ups")
            .select("""
                *,
                patients (
                    patient_id, patient_code, first_name,
                    middle_name, last_name, suffix,
                    date_of_birth, sex, contact_number, hospital_id
                ),
                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id, patient_id, examination_type,
                    examination_date, chief_complaint,
                    history_of_present_illness, physical_examination,
                    diagnosis, plans_orders, disposition,
                    disposition_notes, status, follow_up_sequence
                ),
                follow_up_examination:examinations!follow_ups_follow_up_examination_id_fkey (
                    examination_id, patient_id, examination_type,
                    examination_date, diagnosis, status, follow_up_sequence
                )
            """)
            .eq("follow_up_code", code.strip().upper())
            .limit(1)
            .execute()
        )

        rows = response.data or []
        return rows[0] if rows else None

    except Exception as exc:
        print(f"Failed to get follow-up by code: {exc}")
        return None


# ============================================================
# SEARCH FOLLOW-UPS
# ============================================================

def search_follow_ups(query, hospital_id=None):
    """Search follow-ups by code OR patient name."""

    if not query or not query.strip():
        return []

    query = query.strip()

    try:
        code_match = get_follow_up_by_code(query)

        if code_match:
            if hospital_id:
                patient = code_match.get("patients") or {}
                if isinstance(patient, list):
                    patient = patient[0] if patient else {}
                if patient.get("hospital_id") != hospital_id:
                    return []
            return [code_match]

        query_builder = (
            admin_supabase
            .table("follow_ups")
            .select("""
                *,
                patients!inner (
                    patient_id, patient_code, first_name,
                    middle_name, last_name, suffix,
                    date_of_birth, sex, contact_number, hospital_id
                ),
                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id, patient_id, examination_type,
                    examination_date, chief_complaint,
                    history_of_present_illness, physical_examination,
                    diagnosis, plans_orders, disposition,
                    disposition_notes, status, follow_up_sequence
                ),
                follow_up_examination:examinations!follow_ups_follow_up_examination_id_fkey (
                    examination_id, patient_id, examination_type,
                    examination_date, diagnosis, status, follow_up_sequence
                )
            """)
            .or_(
                f"patients.first_name.ilike.%{query}%,"
                f"patients.last_name.ilike.%{query}%"
            )
            .in_("status", ["Scheduled", "Rescheduled"])
            .order("follow_up_date", desc=False)
        )

        if hospital_id:
            query_builder = query_builder.eq(
                "patients.hospital_id", hospital_id
            )

        response = query_builder.execute()
        return response.data or []

    except Exception as exc:
        print(f"Failed to search follow-ups: {exc}")
        return []


# ============================================================
# GET SCHEDULED FOLLOW-UPS FOR A DATE
# ============================================================

def get_scheduled_follow_ups_for_date(target_date, hospital_id=None):
    """Return all follow-ups scheduled on a specific date."""

    if not target_date:
        target_date = date.today()

    try:
        query = (
            admin_supabase
            .table("follow_ups")
            .select("""
                *,
                patients!inner (
                    patient_id, patient_code, first_name,
                    middle_name, last_name, suffix,
                    date_of_birth, sex, contact_number, hospital_id
                ),
                source_examination:examinations!follow_ups_source_examination_id_fkey (
                    examination_id, examination_type,
                    examination_date, diagnosis, status
                )
            """)
            .eq("follow_up_date", target_date.isoformat())
            .in_("status", ["Scheduled", "Rescheduled"])
            .order("follow_up_time", desc=False)
        )

        if hospital_id:
            query = query.eq("patients.hospital_id", hospital_id)

        response = query.execute()
        return response.data or []

    except Exception as exc:
        print(f"Failed to get scheduled follow-ups: {exc}")
        return []


# ============================================================
# COMPLETE LINKED FOLLOW-UP AFTER A PHYSICIAN FINALIZES VISIT
# ============================================================

def finalize_follow_up_for_examination(examination_id):
    """Finalize only the appointment explicitly linked to this examination.

    Safe for ordinary examinations (returns skipped). Idempotent for already
    completed follow-ups. A failed update is reported, not silently ignored.
    No historical rows are changed by merely loading a page.
    """
    if not examination_id:
        return {"success": False, "message": "Examination ID is required."}
    try:
        exam_response = (
            admin_supabase.table("examinations")
            .select("examination_id, patient_id, status")
            .eq("examination_id", examination_id).limit(1).execute()
        )
        exams = exam_response.data or []
        if not exams:
            return {"success": False, "message": "Examination not found."}
        exam = exams[0]
        if exam.get("status") not in ("Completed", "Admitted", "Discharged"):
            return {"success": False, "message": "Examination is not finalized."}
        response = (
            admin_supabase.table("follow_ups")
            .select("follow_up_id, patient_id, status, follow_up_examination_id")
            .eq("follow_up_examination_id", examination_id).execute()
        )
        matches = response.data or []
        if not matches:
            return {"success": True, "skipped": True,
                    "message": "No linked follow-up appointment."}
        if len(matches) != 1:
            return {"success": False, "message": "Ambiguous follow-up links; manual review required."}
        fu = matches[0]
        if fu.get("patient_id") != exam.get("patient_id"):
            return {"success": False, "message": "Follow-up patient mismatch."}
        if fu.get("status") == "Completed":
            return {"success": True, "skipped": True, "message": "Already completed."}
        if fu.get("status") not in ("Scheduled", "Rescheduled"):
            return {"success": False, "message": "Appointment status is not active."}
        result = (
            admin_supabase.table("follow_ups")
            .update({"status": "Completed", "completed_at": utc_now(),
                     "updated_at": utc_now()})
            .eq("follow_up_id", fu["follow_up_id"])
            .eq("follow_up_examination_id", examination_id)
            .eq("status", fu["status"]).execute()
        )
        if not result.data:
            return {"success": False, "message": "Appointment update did not match; refresh and retry."}
        return {"success": True, "message": "Linked follow-up completed."}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


# ============================================================
# MARK FOLLOW-UP ARRIVED (staff check-in)
# ============================================================


def mark_follow_up_arrived(
    follow_up_id,
    staff_user_id,
    consent_data=None,
):
    """
    Called when staff checks in a Follow-Up patient.

    Workflow:
        1. Validate Follow-Up appointment.
        2. Validate consent information.
        3. Create Follow-Up Examination.
        4. Link examination to Follow-Up appointment.
        5. Save examination-specific consent and signature.
        6. Record staff check-in timestamp.

    If a partial operation fails, return recovery information
    without creating another examination automatically.
    """

    # ========================================================
    # 1. BASIC VALIDATION
    # ========================================================

    if not follow_up_id:
        return {
            "success": False,
            "message": "Follow-Up ID is required.",
        }

    if not staff_user_id:
        return {
            "success": False,
            "message": "Staff user ID is required.",
        }

    if not consent_data:
        return {
            "success": False,
            "message": "Treatment consent is required before check-in.",
        }

    if not consent_data.get("confirmed"):
        return {
            "success": False,
            "message": "Consent confirmation is required.",
        }

    signed_by_name = (
        consent_data.get("signed_by_name") or ""
    ).strip()

    signed_by_type = (consent_data.get("signed_by_type") or "").strip().lower()

    signature_bytes = consent_data.get("signature_bytes")

    guardian_name = (
        consent_data.get("guardian_name") or ""
    ).strip()

    guardian_relation = (
        consent_data.get("guardian_relation") or ""
    ).strip()

    if not signed_by_name:
        return {
            "success": False,
            "message": "Consent signer name is required.",
        }

    if signed_by_type not in ("patient", "guardian"):
        return {
            "success": False,
            "message": "Invalid consent signer type.",
        }

    signature_error = _validate_consent_signature(signature_bytes)
    if signature_error:
        return {"success": False, "message": signature_error}

    if signed_by_type == "guardian":
        if not guardian_name or not guardian_relation:
            return {
                "success": False,
                "message": (
                    "Guardian name and relationship are required."
                ),
            }

        if guardian_name.casefold() != signed_by_name.casefold():
            return {
                "success": False,
                "message": (
                    "The guardian name must match the consent signer."
                ),
            }

    # ========================================================
    # 2. LOAD AND VALIDATE FOLLOW-UP
    # ========================================================

    exam_id = None
    exam = None
    examination_linked = False
    consent_saved = False

    try:
        follow_up = get_follow_up(follow_up_id)

        if not follow_up:
            return {
                "success": False,
                "message": "Follow-Up appointment not found.",
            }

        status = (follow_up.get("status") or "").strip()

        if status not in ("Scheduled", "Rescheduled"):
            return {
                "success": False,
                "message": (
                    f"Follow-Up is not active (status: {status})."
                ),
            }

        if follow_up.get("follow_up_examination_id"):
            return {
                "success": False,
                "recovery_required": True,
                "examination_id": follow_up["follow_up_examination_id"],
                "message": (
                    "This Follow-Up already has a linked examination. "
                    "Do not create another examination. "
                    "Check whether consent or check-in recovery is needed."
                ),
            }

        patient = follow_up.get("patients") or {}

        if isinstance(patient, list):
            patient = patient[0] if patient else {}

        patient_id = patient.get("patient_id")

        if not patient_id:
            patient_id = follow_up.get("patient_id")

        if not patient_id:
            return {
                "success": False,
                "message": "Patient ID could not be determined.",
            }

        # ====================================================
        # 3. DETERMINE FOLLOW-UP EXAMINATION SEQUENCE
        # ====================================================

        next_sequence = get_next_follow_up_sequence(
            patient_id
        )

        if next_sequence is None:
            return {
                "success": False,
                "message": (
                    "Could not determine the next examination sequence."
                ),
            }

        # ====================================================
        # 4. CREATE FOLLOW-UP EXAMINATION
        # ====================================================

        from backend.crud import create_examination

        exam_result = create_examination(
            patient_id=patient_id,
            examination_type="Follow-Up Examination",
            examination_date=datetime.now(timezone.utc),
            created_by=staff_user_id,
            follow_up_sequence=next_sequence,
        )

        if not exam_result:
            return {
                "success": False,
                "message": "Failed to create Follow-Up Examination.",
            }

        exam = exam_result[0]
        exam_id = exam.get("examination_id")

        if not exam_id:
            return {
                "success": False,
                "recovery_required": True,
                "message": (
                    "Examination creation returned no ID. "
                    "An administrator must verify the database "
                    "before another check-in attempt."
                ),
            }

        # ====================================================
        # 5. LINK EXAMINATION TO FOLLOW-UP
        # ====================================================

        link_result = link_follow_up_examination(
            follow_up_id,
            exam_id,
        )

        if not link_result.get("success"):
            return {
                "success": False,
                "recovery_required": True,
                "examination_id": exam_id,
                "message": (
                    "The examination was created but could not "
                    "be linked to the Follow-Up appointment. "
                    "Do not retry check-in until the record "
                    "has been reconciled. "
                    + link_result.get("message", "")
                ),
            }

        examination_linked = True

        # ====================================================
        # 6. SAVE CONSENT AND SIGNATURE
        # ====================================================

        consent_result = save_follow_up_consent(
            examination_id=exam_id,
            staff_user_id=staff_user_id,
            signed_by_name=signed_by_name,
            signed_by_type=signed_by_type,
            signature_bytes=signature_bytes,
            guardian_name=(
                guardian_name
                if signed_by_type == "guardian"
                else None
            ),
            guardian_relation=(
                guardian_relation
                if signed_by_type == "guardian"
                else None
            ),
        )

        if not consent_result.get("success"):
            return {
                "success": False,
                "recovery_required": True,
                "examination_id": exam_id,
                "message": (
                    "Follow-Up Examination created and linked, "
                    "but consent could not be saved. "
                    "Use 'Record Missing Consent' for the "
                    "existing examination. Do not check in again. "
                    + consent_result.get(
                        "message",
                        "Unknown consent error.",
                    )
                ),
            }

        consent_saved = True

        # ====================================================
        # 7. RECORD ACTUAL CHECK-IN
        # ====================================================

        checkin_result = (
            admin_supabase
            .table("follow_ups")
            .update({
                "checked_in_at": utc_now(),
                "checked_in_by": staff_user_id,
                "updated_at": utc_now(),
            })
            .eq("follow_up_id", follow_up_id)
            .eq("follow_up_examination_id", exam_id)
            .is_("checked_in_at", "null")
            .execute()
        )

        if not checkin_result.data:
            return {
                "success": False,
                "recovery_required": True,
                "examination_id": exam_id,
                "consent_saved": True,
                "message": (
                    "Examination and consent were saved, "
                    "but the check-in timestamp could not "
                    "be recorded. Contact an administrator "
                    "to reconcile the existing record."
                ),
            }

        # ====================================================
        # 8. SUCCESS
        # ====================================================

        return {
            "success": True,
            "message": (
                "Patient checked in successfully. "
                "Follow-Up Examination, treatment consent, "
                "and signature have been recorded."
            ),
            "examination": exam,
            "follow_up": follow_up,
            "examination_id": exam_id,
            "consent_saved": True,
            "checked_in": True,
        }

    except Exception as exc:
        return {
            "success": False,
            "recovery_required": bool(exam_id),
            "examination_id": exam_id,
            "examination_linked": examination_linked,
            "consent_saved": consent_saved,
            "message": (
                f"Follow-Up check-in failed: {exc}. "
                "If an examination was created, verify its "
                "state before attempting another check-in."
            ),
        }


def _validate_consent_signature(signature_bytes):
    """Validate that the signature is a reasonably sized, nonblank PNG."""
    if not isinstance(signature_bytes, bytes) or not signature_bytes:
        return "A signature image is required."
    if len(signature_bytes) > 2 * 1024 * 1024:
        return "Signature image exceeds the 2 MB limit."
    try:
        with Image.open(io.BytesIO(signature_bytes)) as image:
            if image.format != "PNG":
                return "Signature must be a PNG image."
            if image.width < 20 or image.height < 20 or image.width * image.height > 2_000_000:
                return "Signature image dimensions are invalid."
            rgb = image.convert("RGB")
            extrema = rgb.getextrema()
            if all(lo >= 230 for lo, hi in extrema):
                return "Please draw a signature before submitting."
    except (UnidentifiedImageError, OSError, ValueError):
        return "Signature image is invalid or corrupted."
    return None


def save_follow_up_consent(
    examination_id,
    staff_user_id,
    signed_by_name,
    signed_by_type,
    signature_bytes,
    guardian_name=None,
    guardian_relation=None,
):
    """
    Save a new, examination-specific treatment consent.

    Can be used for:
    - Newly checked-in Follow-Up Examinations
    - Existing examinations missing consent

    Does not create or modify an examination.
    """
    from backend.crud import upload_consent_signature

    signed_by_type = (signed_by_type or "").strip().lower()

    if not examination_id or not staff_user_id:
        return {"success": False, "message": "Missing examination or staff ID."}

    if not signed_by_name or not signed_by_name.strip():
        return {"success": False, "message": "Signer name is required."}

    signed_by_type = (signed_by_type or "").strip().lower()

    if signed_by_type not in ("patient", "guardian"):
        return {
            "success": False,
            "message": "Invalid signer type.",
        }
    
    if signed_by_type == "guardian":
        if not guardian_name or not guardian_name.strip() or not guardian_relation or not guardian_relation.strip():
            return {"success": False, "message": "Guardian details are required."}
        if guardian_name.strip().casefold() != signed_by_name.strip().casefold():
            return {"success": False, "message": "Guardian name must match signer name."}

    signature_error = _validate_consent_signature(signature_bytes)
    if signature_error:
        return {"success": False, "message": signature_error}

    try:
        # Confirm the examination belongs to a follow-up.
        follow_up_result = (
            admin_supabase.table("follow_ups")
            .select("follow_up_id, patient_id")
            .eq("follow_up_examination_id", examination_id)
            .limit(1)
            .execute()
        )

        if not follow_up_result.data:
            return {
                "success": False,
                "message": "No linked Follow-Up Examination found.",
            }

        follow_up = follow_up_result.data[0]

        exam_result = (
            admin_supabase.table("examinations")
            .select("examination_id, patient_id, examination_type, status")
            .eq("examination_id", examination_id)
            .single()
            .execute()
        )

        exam = exam_result.data

        if (
            not exam
            or exam["patient_id"] != follow_up["patient_id"]
            or exam["examination_type"] != "Follow-Up Examination"
        ):
            return {"success": False, "message": "Examination validation failed."}

        if exam["status"] in ("Completed", "Admitted", "Discharged", "Cancelled"):
            return {
                "success": False,
                "message": "Historical or finalized examination. Use an authorized records-correction workflow.",
            }

        existing = (
            admin_supabase.table("examination_consents")
            .select("consent_id, given, signature_path")
            .eq("examination_id", examination_id)
            .execute()
        ).data or []

        # Never overwrite existing signed consent.
        if existing:
            return {
                "success": False,
                "message": "A consent record already exists. Review it before making changes.",
            }

        signature_path = upload_consent_signature(
            examination_id,
            signature_bytes,
        )

        if not signature_path:
            return {
                "success": False,
                "message": "Signature upload failed. Consent was not recorded.",
            }

        consent_data = {
            "examination_id": examination_id,
            "consent_type": "Treatment",
            "given": True,
            "signed_by_name": signed_by_name.strip(),
            "signed_by_type": signed_by_type,
            "guardian_name": (
                guardian_name.strip()
                if signed_by_type == "guardian"
                else None
            ),
            "guardian_relation": (
                guardian_relation.strip()
                if signed_by_type == "guardian"
                else None
            ),
            "signed_at": utc_now(),
            "witnessed_by": staff_user_id,
            "signature_path": signature_path,
        }

        result = (
            admin_supabase.table("examination_consents")
            .insert(consent_data)
            .execute()
        )

        if not result.data:
            return {
                "success": False,
                "message": "Consent insert failed. Check for an orphaned signature upload.",
            }

        return {
            "success": True,
            "message": "Consent and signature saved.",
            "consent": result.data[0],
        }

    except Exception as exc:
        return {"success": False, "message": str(exc)}

