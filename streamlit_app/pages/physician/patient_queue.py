import streamlit as st

from datetime import datetime, date, time, timezone

from backend.fetches import (
    get_pending_examinations,
    get_pending_xray_requests,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_consent_signature_url,
)

from backend.crud import (
    create_examination,
    update_examination,
    add_examination_vitals,
    create_xray_request,
)

from backend.backend_utils.followup_utils import (
    get_hospital_follow_ups,
    get_follow_up,
    get_next_follow_up_sequence,
    link_follow_up_examination,
    complete_follow_up,
    reschedule_follow_up,
    cancel_follow_up,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    format_date,
    pill,
    metric_card,
    table_header,
    table_row,
    name_cell,
    text_cell,
    pill_cell,
    remember,
    show_flash_message,
)

from shared.assets import load_css


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_RADTECH = 4
ROLE_HOSPITAL_ADMIN = 6
ROLE_STAFF = 7

DOCTOR_ROLES = [
    ROLE_RADIOLOGIST,
]

ADMIN_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_HOSPITAL_ADMIN,
]


FOLLOW_UP_STATUSES = [
    "Scheduled",
    "Completed",
    "Missed",
    "Cancelled",
    "Rescheduled",
]


ACTIVE_FOLLOW_UP_STATUSES = [
    "Scheduled",
    "Rescheduled",
]


# ============================================================
# PAGE / DIALOG KEYS
# ============================================================

PAGE_KEY = "sa_page"
DIALOG_KEY = "sa_dialog"


# ============================================================
# TABLE CONFIGURATION
# ============================================================

QUEUE_WIDTHS = [
    2.5,
    1,
    1.2,
    1.2,
    1.2,
]

QUEUE_HEADERS = [
    "Patient",
    "Pending",
    "Waiting",
    "History",
    "Actions",
]


XRAY_QUEUE_WIDTHS = [
    2.4,
    1.4,
    1.6,
    1.3,
    1.2,
]

XRAY_QUEUE_HEADERS = [
    "Patient",
    "Requested",
    "Requested At",
    "Status",
    "View",
]


FOLLOW_UP_WIDTHS = [
    2.2,
    1.5,
    1.6,
    1.2,
    1.3,
]

FOLLOW_UP_HEADERS = [
    "Patient",
    "Follow-Up",
    "Source Examination",
    "Status",
    "Actions",
]


# ============================================================
# SESSION / USER HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_user_id():
    return current_user().get("user_id")


def current_hospital_id():
    return current_user().get("hospital_id")


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return (
        patient.get("patient_code")
        or patient.get("patient_id")
    )


# ============================================================
# DATE / TIME HELPERS
# ============================================================

def parse_datetime(value):
    if not value:
        return None

    try:
        if isinstance(value, datetime):
            dt = value
        else:
            value = str(value)

            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")

            dt = datetime.fromisoformat(value)

        return dt

    except Exception:
        return None


def format_datetime(value):
    """
    Example:
    September 30, 2026 at 12:45 PM
    """

    if not value:
        return "—"

    try:
        dt = parse_datetime(value)

        if not dt:
            return str(value)

        if dt.tzinfo is not None:
            dt = dt.astimezone()

        return dt.strftime(
            "%B %d, %Y at %I:%M %p"
        )

    except Exception:
        return str(value)


def format_follow_up_datetime(follow_up):
    """
    Supports the current follow-up structure where
    date and time may be stored separately.
    """

    follow_up_date = (
        follow_up.get("follow_up_date")
        or follow_up.get("scheduled_date")
        or follow_up.get("date")
    )

    follow_up_time = (
        follow_up.get("follow_up_time")
        or follow_up.get("scheduled_time")
        or follow_up.get("time")
    )

    if not follow_up_date:
        return "—"

    try:
        if isinstance(follow_up_date, datetime):
            dt = follow_up_date
        elif isinstance(follow_up_date, date):
            dt = datetime.combine(
                follow_up_date,
                time.min,
            )
        else:
            date_string = str(follow_up_date)

            if "T" in date_string:
                dt = parse_datetime(date_string)
            else:
                parsed_date = date.fromisoformat(
                    date_string[:10]
                )

                if follow_up_time:
                    if isinstance(
                        follow_up_time,
                        time,
                    ):
                        parsed_time = follow_up_time
                    else:
                        parsed_time = time.fromisoformat(
                            str(follow_up_time)[:8]
                        )
                else:
                    parsed_time = time.min

                dt = datetime.combine(
                    parsed_date,
                    parsed_time,
                )

        if not dt:
            return str(follow_up_date)

        return dt.strftime(
            "%B %d, %Y at %I:%M %p"
        )

    except Exception:
        return str(follow_up_date)


def follow_up_date_value(follow_up):
    value = (
        follow_up.get("follow_up_date")
        or follow_up.get("scheduled_date")
        or follow_up.get("date")
    )

    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(
            str(value)[:10]
        )
    except Exception:
        return None


def examination_datetime(examination):
    return (
        examination.get("examination_date")
        or examination.get("created_at")
    )


def medical_record_datetime(record):
    return (
        record.get("record_date")
        or record.get("created_at")
    )


def xray_request_datetime(examination):
    return (
        examination.get("xray_requested_at")
        or examination.get("requested_at")
        or examination.get("created_at")
    )


# ============================================================
# WAITING TIME
# ============================================================

def waiting_minutes(created_at_str):
    if not created_at_str:
        return 0

    try:
        created = datetime.fromisoformat(
            str(created_at_str).replace(
                "Z",
                "+00:00",
            )
        )

        if created.tzinfo is None:
            created = created.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(timezone.utc)

        delta = now - created

        return max(
            0,
            int(
                delta.total_seconds() // 60
            ),
        )

    except Exception:
        return 0


def waiting_tone(minutes):
    if minutes < 10:
        return "green"

    if minutes < 30:
        return "amber"

    return "red"


def format_waiting(minutes):
    if minutes < 60:
        return f"{minutes} min"

    hours = minutes // 60

    return f"{hours}h {minutes % 60}m"


# ============================================================
# BMI
# ============================================================

def calculate_bmi(
    weight_kg,
    height_cm,
):
    try:
        weight = float(weight_kg)
        height = float(height_cm) / 100

        if weight <= 0 or height <= 0:
            return None

        return round(
            weight / (height * height),
            2,
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def bmi_tone(bmi_value):
    if bmi_value is None:
        return ("—", "grey")

    if bmi_value < 18.5:
        return ("Underweight", "blue")

    if bmi_value < 25:
        return ("Normal", "green")

    if bmi_value < 30:
        return ("Overweight", "amber")

    return ("Obese", "red")


def get_vitals_value(
    vitals_list,
    field_name,
):
    for vital in vitals_list:

        if vital.get(field_name) is not None:
            return vital[field_name]

    return None


# ============================================================
# FOLLOW-UP HELPERS
# ============================================================

def get_follow_up_patient(follow_up):
    """
    Supports the patient relationship returned by
    the follow-up utility.
    """

    patient = follow_up.get("patients")

    if patient:
        return patient

    patient = follow_up.get("patient")

    if patient:
        return patient

    return {}


def get_source_examination(follow_up):
    """
    Supports the explicit source examination
    relationship used by the current follow-up backend.
    """

    examination = (
        follow_up.get(
            "source_examination"
        )
        or follow_up.get(
            "examinations"
        )
    )

    if isinstance(examination, list):
        return (
            examination[0]
            if examination
            else {}
        )

    return examination or {}


def get_follow_up_examination(follow_up):
    """
    Returns the examination linked to the
    follow-up visit, when available.
    """

    examination = follow_up.get(
        "follow_up_examination"
    )

    if isinstance(examination, list):
        return (
            examination[0]
            if examination
            else {}
        )

    return examination or {}


def get_follow_up_id(follow_up):
    return (
        follow_up.get("follow_up_id")
        or follow_up.get("id")
    )


def get_follow_up_status(follow_up):
    return (
        follow_up.get("status")
        or "Scheduled"
    )


def follow_up_status_tone(status):
    tones = {
        "Scheduled": "blue",
        "Completed": "green",
        "Missed": "red",
        "Cancelled": "red",
        "Rescheduled": "amber",
    }

    return tones.get(
        status,
        "grey",
    )


def has_follow_up_examination(
    follow_up,
):
    examination_id = follow_up.get(
        "follow_up_examination_id"
    )

    if examination_id:
        return True

    examination = get_follow_up_examination(
        follow_up
    )

    return bool(
        examination.get(
            "examination_id"
        )
    )


def clear_dialog_state():
    keys = [
        "selected_follow_up",
        "selected_patient_follow_ups",
        "selected_examination",
        "edit_patient",
        "history_patient",
        "pending_exams_patient",
        "xray_request_patient",
        "previous_examinations_patient",
        "previous_medical_records_patient",
    ]

    for key in keys:
        st.session_state.pop(
            key,
            None,
        )


# ============================================================
# GROUP PENDING EXAMINATIONS
# ============================================================

def group_pending_by_patient(
    pending_exams,
):
    by_patient = {}

    for examination in pending_exams:

        patient = (
            examination.get("patients")
            or {}
        )

        patient_id = patient.get(
            "patient_id"
        )

        if not patient_id:
            continue

        if patient_id not in by_patient:

            by_patient[patient_id] = {
                "patient": patient,
                "exams": [],
                "oldest_waiting": 0,
            }

        by_patient[patient_id][
            "exams"
        ].append(examination)

        waiting = waiting_minutes(
            examination.get(
                "created_at"
            )
        )

        if waiting > by_patient[
            patient_id
        ]["oldest_waiting"]:

            by_patient[
                patient_id
            ]["oldest_waiting"] = waiting

    grouped = list(
        by_patient.values()
    )

    grouped.sort(
        key=lambda item: item[
            "oldest_waiting"
        ],
        reverse=True,
    )

    return grouped


# ============================================================
# GROUP ACTIVE FOLLOW-UPS BY PATIENT
# ============================================================

def group_active_follow_ups_by_patient(follow_ups):
    """
    Group active (Scheduled / Rescheduled) follow-ups
    by patient.

    Returns a list of dicts:
        {
            "patient": {...},
            "follow_ups": [ ...all active follow-ups... ],
            "next_follow_up": { ...earliest by date/time... },
        }

    Sorted by the earliest upcoming follow-up date/time.
    """

    by_patient = {}

    for follow_up in follow_ups:

        status = get_follow_up_status(follow_up)

        if status not in ACTIVE_FOLLOW_UP_STATUSES:
            continue

        patient = get_follow_up_patient(follow_up)

        patient_id = patient.get("patient_id")

        if not patient_id:
            continue

        if patient_id not in by_patient:

            by_patient[patient_id] = {
                "patient": patient,
                "follow_ups": [],
                "next_follow_up": None,
            }

        by_patient[patient_id]["follow_ups"].append(follow_up)

    # ------------------------------------------------------
    # SORT EACH PATIENT'S FOLLOW-UPS BY DATE, THEN PICK
    # THE EARLIEST AS next_follow_up
    # ------------------------------------------------------

    for entry in by_patient.values():

        entry["follow_ups"].sort(
            key=lambda item: (
                follow_up_date_value(item)
                or date.max
            )
        )

        entry["next_follow_up"] = entry["follow_ups"][0]

    # ------------------------------------------------------
    # SORT PATIENTS BY THEIR EARLIEST UPCOMING FOLLOW-UP
    # ------------------------------------------------------

    grouped = list(by_patient.values())

    grouped.sort(
        key=lambda item: (
            follow_up_date_value(item["next_follow_up"])
            or date.max
        )
    )

    return grouped


# ============================================================
# HISTORY DIALOG
# ============================================================

@st.dialog(
    "Patient History",
    width="large",
)
def show_patient_history_dialog(
    patient,
):
    patient_id = patient.get(
        "patient_id"
    )

    with st.container(
        key=DIALOG_KEY
    ):

        section_title(
            "Patient Information"
        )

        show_rows([
            (
                "Patient",
                patient_name(patient),
            ),
            (
                "Patient ID",
                patient_code(patient),
            ),
            (
                "Date of Birth",
                format_date(
                    patient.get(
                        "date_of_birth"
                    )
                ),
            ),
            (
                "Sex",
                patient.get(
                    "sex"
                )
                or "—",
            ),
        ])

        st.divider()

        section_title(
            "Examination History"
        )

        try:
            examinations = (
                get_examinations_by_patient(
                    patient_id
                )
            )

        except Exception as error:

            examinations = []

            st.error(
                "Failed to load examination "
                f"history: {error}"
            )

        completed = [
            examination
            for examination in examinations
            if examination.get(
                "status"
            )
            in (
                "Completed",
                "Cancelled",
            )
        ]

        if not completed:

            empty_state(
                "No previous examinations found."
            )

        else:

            for examination in sorted(
                completed,
                key=lambda item:
                    examination_datetime(
                        item
                    )
                    or "",
                reverse=True,
            ):

                status = (
                    examination.get(
                        "status"
                    )
                    or "Unknown"
                )

                tone = (
                    "green"
                    if status
                    == "Completed"
                    else "red"
                )

                st.markdown(
                    f"**{examination.get('examination_type') or 'Examination'}**"
                )

                st.caption(
                    format_datetime(
                        examination_datetime(
                            examination
                        )
                    )
                )

                st.markdown(
                    f"Status: "
                    f"{pill(status, tone)}",
                    unsafe_allow_html=True,
                )

                if examination.get(
                    "diagnosis"
                ):

                    st.caption(
                        "Diagnosis: "
                        f"{examination.get('diagnosis')}"
                    )

                if examination.get(
                    "chief_complaint"
                ):

                    st.caption(
                        "Chief Complaint: "
                        f"{examination.get('chief_complaint')}"
                    )

                if examination.get(
                    "disposition"
                ):

                    st.caption(
                        "Disposition: "
                        f"{examination.get('disposition')}"
                    )

                st.divider()

        section_title(
            "Previous Medical / External Records"
        )

        try:

            from backend.fetches import (
                get_medical_records_by_patient,
            )

            records = (
                get_medical_records_by_patient(
                    patient_id
                )
            )

        except Exception as error:

            records = []

            st.error(
                "Failed to load medical "
                f"records: {error}"
            )

        if not records:

            empty_state(
                "No previous external medical "
                "records found."
            )

        else:

            for record in sorted(
                records,
                key=lambda item:
                    medical_record_datetime(
                        item
                    )
                    or "",
                reverse=True,
            ):

                st.markdown(
                    f"**{record.get('record_type') or 'Medical Record'}**"
                )

                st.caption(
                    format_datetime(
                        medical_record_datetime(
                            record
                        )
                    )
                )

                st.markdown(
                    "**Facility:** "
                    f"{record.get('facility_name') or '—'}"
                )

                if record.get(
                    "diagnosis"
                ):

                    st.markdown(
                        "**Diagnosis:** "
                        f"{record.get('diagnosis')}"
                    )

                if record.get(
                    "treatment"
                ):

                    st.markdown(
                        "**Treatment:** "
                        f"{record.get('treatment')}"
                    )

                if record.get(
                    "notes"
                ):

                    st.markdown(
                        "**Notes:** "
                        f"{record.get('notes')}"
                    )

                st.divider()

        if st.button(
            "Close",
            key="followups_history_close",
            width="stretch",
        ):

            st.session_state.pop(
                "history_patient",
                None,
            )

            st.rerun()


# ============================================================
# PREVIOUS EXAMINATIONS DIALOG
# ============================================================

@st.dialog(
    "Previous Examination History",
    width="large",
)
def show_previous_examinations_dialog(
    patient,
):
    patient_id = patient.get(
        "patient_id"
    )

    examinations = (
        get_examinations_by_patient(
            patient_id
        )
    )

    previous = [
        examination
        for examination in examinations
        if examination.get(
            "status"
        )
        in (
            "Completed",
            "Cancelled",
        )
    ]

    with st.container(
        key=DIALOG_KEY
    ):

        section_title(
            f"Previous Examinations ({len(previous)})"
        )

        if not previous:

            empty_state(
                "No previous examinations found."
            )

        else:

            for examination in sorted(
                previous,
                key=lambda item:
                    examination_datetime(
                        item
                    )
                    or "",
                reverse=True,
            ):

                status = (
                    examination.get(
                        "status"
                    )
                    or "Unknown"
                )

                tone = (
                    "green"
                    if status
                    == "Completed"
                    else "red"
                )

                st.markdown(
                    f"### "
                    f"{examination.get('examination_type') or 'Examination'}"
                )

                st.markdown(
                    "**Date & Time:** "
                    f"{format_datetime(examination_datetime(examination))}"
                )

                st.markdown(
                    f"**Status:** "
                    f"{pill(status, tone)}",
                    unsafe_allow_html=True,
                )

                st.markdown(
                    "**Chief Complaint:** "
                    f"{examination.get('chief_complaint') or '—'}"
                )

                st.markdown(
                    "**Diagnosis:** "
                    f"{examination.get('diagnosis') or '—'}"
                )

                st.markdown(
                    "**Plans / Orders:** "
                    f"{examination.get('plans_orders') or '—'}"
                )

                st.markdown(
                    "**Disposition:** "
                    f"{examination.get('disposition') or '—'}"
                )

                st.divider()

        if st.button(
            "Close",
            key="followups_previous_exam_close",
            width="stretch",
        ):

            st.session_state.pop(
                "previous_examinations_patient",
                None,
            )

            st.rerun()


# ============================================================
# PREVIOUS MEDICAL RECORDS DIALOG
# ============================================================

@st.dialog(
    "Previous Medical Histories",
    width="large",
)
def show_previous_medical_records_dialog(
    patient,
):

    patient_id = patient.get(
        "patient_id"
    )

    try:

        from backend.fetches import (
            get_medical_records_by_patient,
        )

        records = (
            get_medical_records_by_patient(
                patient_id
            )
        )

    except Exception as error:

        records = []

        st.error(
            f"Failed to load medical records: {error}"
        )

    with st.container(
        key=DIALOG_KEY
    ):

        section_title(
            f"Previous Medical Records ({len(records)})"
        )

        if not records:

            empty_state(
                "No previous external medical "
                "records found."
            )

        else:

            for record in sorted(
                records,
                key=lambda item:
                    medical_record_datetime(
                        item
                    )
                    or "",
                reverse=True,
            ):

                st.markdown(
                    f"### "
                    f"{record.get('record_type') or 'Medical Record'}"
                )

                st.markdown(
                    "**Date & Time:** "
                    f"{format_datetime(medical_record_datetime(record))}"
                )

                st.markdown(
                    "**Facility:** "
                    f"{record.get('facility_name') or '—'}"
                )

                st.markdown(
                    "**Diagnosis:** "
                    f"{record.get('diagnosis') or '—'}"
                )

                st.markdown(
                    "**Treatment:** "
                    f"{record.get('treatment') or '—'}"
                )

                st.markdown(
                    "**Notes:** "
                    f"{record.get('notes') or '—'}"
                )

                st.divider()

        if st.button(
            "Close",
            key="followups_previous_medical_close",
            width="stretch",
        ):

            st.session_state.pop(
                "previous_medical_records_patient",
                None,
            )

            st.rerun()


# ============================================================
# HISTORY BUTTONS
# ============================================================

def render_history_buttons(
    patient,
    key_prefix,
):

    st.divider()

    section_title(
        "Patient History"
    )

    st.caption(
        "Review previous examinations and "
        "medical histories separately."
    )

    col1, col2 = st.columns(2)

    if col1.button(
        "View Examination Histories",
        key=(
            f"{key_prefix}_"
            "view_exam_history"
        ),
        icon=":material/history:",
        width="stretch",
    ):

        st.session_state[
            "previous_examinations_patient"
        ] = patient

        st.rerun()

    if col2.button(
        "View Previous Medical Histories",
        key=(
            f"{key_prefix}_"
            "view_medical_history"
        ),
        icon=":material/medical_information:",
        width="stretch",
    ):

        st.session_state[
            "previous_medical_records_patient"
        ] = patient

        st.rerun()


# ============================================================
# X-RAY REQUEST DETAILS
# ============================================================

@st.dialog(
    "X-Ray Request Details",
    width="medium",
)
def show_xray_request_dialog(
    examination,
):

    patient = (
        examination.get("patients")
        or {}
    )

    requested_at = (
        xray_request_datetime(
            examination
        )
    )

    waiting = waiting_minutes(
        requested_at
    )

    with st.container(
        key=DIALOG_KEY
    ):

        section_title(
            "Patient Information"
        )

        show_rows([
            (
                "Patient",
                patient_name(patient),
            ),
            (
                "Patient ID",
                patient_code(patient),
            ),
        ])

        st.divider()

        section_title(
            "X-Ray Request"
        )

        show_rows([
            (
                "Requested Examination",
                "Chest X-Ray",
            ),
            (
                "Requested At",
                format_datetime(
                    requested_at
                ),
            ),
            (
                "Time Since Request",
                format_waiting(
                    waiting
                ),
            ),
            (
                "Status",
                pill(
                    "Pending",
                    "amber",
                ),
            ),
        ])

        st.divider()

        st.info(
            "This request is view-only. "
            "The Radiologic Technologist will "
            "process the requested X-Ray."
        )

        if st.button(
            "Close",
            key="followups_xray_close",
            width="stretch",
        ):

            st.session_state.pop(
                "xray_request_patient",
                None,
            )

            st.rerun()


# ============================================================
# PATIENT-LEVEL FOLLOW-UP DIALOG (GROUPED)
# ============================================================

@st.dialog(
    "Patient Follow-Ups",
    width="large",
)
def show_patient_follow_ups_dialog(
    patient,
    follow_ups,
):
    """
    Lists ALL active follow-ups for one patient.

    The physician picks the specific follow-up
    to manage, which then opens the existing
    show_follow_up_dialog().
    """

    with st.container(key=DIALOG_KEY):

        # ----------------------------------------------------
        # PATIENT SUMMARY
        # ----------------------------------------------------

        section_title("Patient")

        show_rows([
            (
                "Patient",
                patient_name(patient),
            ),
            (
                "Patient ID",
                patient_code(patient),
            ),
            (
                "Active follow-ups",
                str(len(follow_ups)),
            ),
        ])

        st.divider()

        section_title(
            f"Active Follow-Ups ({len(follow_ups)})"
        )

        st.caption(
            "Select a follow-up to view details, "
            "start the examination, reschedule, "
            "or cancel it."
        )

        # ----------------------------------------------------
        # LIST EACH FOLLOW-UP
        # ----------------------------------------------------

        for follow_up in follow_ups:

            follow_up_id = get_follow_up_id(
                follow_up
            )

            status = get_follow_up_status(
                follow_up
            )

            source_exam = get_source_examination(
                follow_up
            )

            linked_exam = get_follow_up_examination(
                follow_up
            )

            scheduled_at = format_follow_up_datetime(
                follow_up
            )

            with st.expander(
                (
                    f"{scheduled_at} • "
                    f"{status}"
                ),
                expanded=False,
            ):

                # --------------------------------------------
                # STATUS
                # --------------------------------------------

                st.markdown(
                    f"**Status:** "
                    f"{pill(status, follow_up_status_tone(status))}",
                    unsafe_allow_html=True,
                )

                # --------------------------------------------
                # SCHEDULED DATE / TIME
                # --------------------------------------------

                st.markdown(
                    "**Scheduled:** "
                    f"{scheduled_at}"
                )

                # --------------------------------------------
                # SOURCE EXAMINATION
                # --------------------------------------------

                if source_exam:

                    st.markdown(
                        "**Source Examination:** "
                        f"{source_exam.get('examination_type') or 'Examination'}"
                    )

                    st.caption(
                        "Date: "
                        f"{format_datetime(examination_datetime(source_exam))}"
                    )

                # --------------------------------------------
                # LINKED FOLLOW-UP EXAMINATION
                # --------------------------------------------

                if linked_exam:

                    linked_status = (
                        linked_exam.get("status")
                        or "Pending"
                    )

                    linked_tone = (
                        "green"
                        if linked_status == "Completed"
                        else "amber"
                    )

                    st.markdown(
                        f"**Examination:** "
                        f"{pill(linked_status, linked_tone)}",
                        unsafe_allow_html=True,
                    )

                else:

                    st.caption(
                        "No follow-up examination "
                        "started yet."
                    )

                # --------------------------------------------
                # NOTES
                # --------------------------------------------

                notes = (
                    follow_up.get("notes")
                    or follow_up.get("follow_up_notes")
                )

                if notes:

                    st.markdown(
                        f"**Notes:** {notes}"
                    )

                # --------------------------------------------
                # MANAGE BUTTON
                # --------------------------------------------

                if st.button(
                    "Manage This Follow-Up",
                    key=(
                        f"manage_follow_up_"
                        f"{follow_up_id}"
                    ),
                    icon=":material/event_note:",
                    type="primary",
                    width="stretch",
                ):

                    st.session_state.pop(
                        "selected_patient_follow_ups",
                        None,
                    )

                    st.session_state[
                        "selected_follow_up"
                    ] = follow_up

                    st.rerun()

        st.divider()

        if st.button(
            "Close",
            key="patient_follow_ups_close",
            width="stretch",
        ):

            st.session_state.pop(
                "selected_patient_follow_ups",
                None,
            )

            st.rerun()


# ============================================================
# FOLLOW-UP DETAILS DIALOG
# ============================================================

@st.dialog(
    "Follow-Up Details",
    width="large",
)
def show_follow_up_dialog(
    follow_up,
):

    follow_up_id = get_follow_up_id(
        follow_up
    )

    patient = get_follow_up_patient(
        follow_up
    )

    source_exam = get_source_examination(
        follow_up
    )

    linked_exam = get_follow_up_examination(
        follow_up
    )

    status = get_follow_up_status(
        follow_up
    )

    # ----------------------------------------------------
    # RESOLVE STATE
    # ----------------------------------------------------

    linked_status = (
        linked_exam.get("status")
        if linked_exam
        else None
    )

    exam_completed = (
        linked_status == "Completed"
    )

    is_active = (
        status in ACTIVE_FOLLOW_UP_STATUSES
    )

    can_start = is_active and not linked_exam
    can_mark_completed = is_active and exam_completed
    can_reschedule_or_cancel = (
        is_active and not exam_completed
    )

    with st.container(
        key=DIALOG_KEY
    ):

        # ----------------------------------------------------
        # PATIENT
        # ----------------------------------------------------

        section_title(
            "Follow-Up Details"
        )

        follow_up_sequence = (
            linked_exam.get(
                "follow_up_sequence"
            )
            if linked_exam
            else None
        )

        if follow_up_sequence is not None:

            examination_display_name = (
                f"Follow-Up Examination "
                f"{int(follow_up_sequence):03d}"
            )

        else:

            examination_display_name = (
                linked_exam.get(
                    "examination_type"
                )
                if linked_exam
                else "Follow-Up Examination"
            ) or "Follow-Up Examination"

        show_rows([
            (
                "Examination",
                examination_display_name,
            ),
            (
                "Examination Date",
                format_datetime(
                    examination_datetime(
                        linked_exam
                    )
                )
                if linked_exam
                else "—",
            ),
            (
                "Status",
                pill(
                    linked_status or "Not Started",
                    (
                        "green"
                        if linked_status == "Completed"
                        else "amber"
                        if linked_status == "Pending"
                        else "grey"
                    ),
                ),
            ),
            (
                "Examination ID",
                (
                    linked_exam.get("examination_id")
                    if linked_exam
                    else "—"
                )
                or "—",
            ),
        ])

        # ----------------------------------------------------
        # SOURCE EXAMINATION
        # ----------------------------------------------------

        st.divider()

        section_title(
            "Source Examination"
        )

        if source_exam:

            source_status = (
                source_exam.get(
                    "status"
                )
                or "Unknown"
            )

            source_tone = (
                "green"
                if source_status
                == "Completed"
                else "amber"
            )

            show_rows([
                (
                    "Examination",
                    source_exam.get(
                        "examination_type"
                    )
                    or "Examination",
                ),
                (
                    "Examination Date",
                    format_datetime(
                        examination_datetime(
                            source_exam
                        )
                    ),
                ),
                (
                    "Diagnosis",
                    source_exam.get(
                        "diagnosis"
                    )
                    or "—",
                ),
                (
                    "Status",
                    pill(
                        source_status,
                        source_tone,
                    ),
                ),
            ])

        else:

            st.info(
                "The source examination "
                "could not be loaded."
            )

        # ----------------------------------------------------
        # FOLLOW-UP EXAMINATION
        # ----------------------------------------------------

        st.divider()

        section_title(
            "Follow-Up Examination"
        )

        if linked_exam:

            show_rows([
                (
                    "Examination",
                    linked_exam.get(
                        "examination_type"
                    )
                    or "Follow-Up Examination",
                ),
                (
                    "Examination Date",
                    format_datetime(
                        examination_datetime(
                            linked_exam
                        )
                    ),
                ),
                (
                    "Status",
                    pill(
                        linked_status or "Pending",
                        (
                            "green"
                            if linked_status == "Completed"
                            else "amber"
                        ),
                    ),
                ),
                (
                    "Examination ID",
                    linked_exam.get(
                        "examination_id"
                    )
                    or "—",
                ),
            ])

            if linked_status == "Pending":

                st.info(
                    "The follow-up examination "
                    "has been created and is "
                    "waiting in the Patient Queue "
                    "for physician review."
                )

            elif linked_status == "Completed":

                st.success(
                    "The follow-up examination "
                    "has been completed."
                )

        else:

            st.info(
                "No follow-up examination has "
                "been created yet."
            )

            st.caption(
                "When the patient arrives for "
                "this follow-up visit, start a "
                "new examination. The new "
                "examination will be placed in "
                "the Patient Queue."
            )

        # ----------------------------------------------------
        # NOTES
        # ----------------------------------------------------

        notes = (
            follow_up.get("notes")
            or follow_up.get(
                "follow_up_notes"
            )
        )

        if notes:

            st.divider()

            section_title(
                "Follow-Up Notes"
            )

            st.write(notes)

        # ----------------------------------------------------
        # ACTIONS
        # ----------------------------------------------------

        st.divider()

        # ====================================================
        # 1. START FOLLOW-UP EXAMINATION
        # ====================================================

        if can_start:

            st.markdown(
                "**Patient has arrived for the "
                "follow-up visit?**"
            )

            st.caption(
                "Start a new examination only "
                "when the patient is actually "
                "being seen for this follow-up."
            )

            if st.button(
                "Start Follow-Up Examination",
                key=(
                    f"start_follow_up_"
                    f"{follow_up_id}"
                ),
                icon=":material/clinical_notes:",
                type="primary",
                width="stretch",
            ):

                try:

                    patient_id = patient.get(
                        "patient_id"
                    )

                    if not patient_id:

                        st.error(
                            "Patient information "
                            "is missing."
                        )

                        return

                    examination_date = (
                        datetime.now(
                            timezone.utc
                        )
                    )

                    follow_up_sequence = (
                        get_next_follow_up_sequence(
                            patient_id=patient_id
                        )
                    )

                    new_exam = (
                        create_examination(
                            patient_id=patient_id,
                            examination_type=(
                                "Follow-Up Examination"
                            ),
                            examination_date=(
                                examination_date
                            ),
                            created_by=(
                                current_user_id()
                            ),
                            follow_up_sequence=(
                                follow_up_sequence
                            ),
                        )
                    )

                    if not new_exam:

                        st.error(
                            "The follow-up "
                            "examination could not "
                            "be created."
                        )

                        return

                    created_exam = new_exam[0]

                    new_exam_id = (
                        created_exam.get(
                            "examination_id"
                        )
                    )

                    if not new_exam_id:

                        st.error(
                            "The examination was "
                            "created but its ID "
                            "could not be found."
                        )

                        return

                    linked = (
                        link_follow_up_examination(
                            follow_up_id=(
                                follow_up_id
                            ),
                            follow_up_examination_id=(
                                new_exam_id
                            ),
                        )
                    )

                    if not linked:

                        st.error(
                            "The follow-up "
                            "examination was "
                            "created, but it could "
                            "not be linked to the "
                            "follow-up."
                        )

                        return

                    st.session_state.pop(
                        "selected_follow_up",
                        None,
                    )

                    remember(
                        "Follow-up examination "
                        "created successfully. "
                        "The patient is now in "
                        "the Patient Queue."
                    )

                    st.rerun()

                except Exception as error:

                    st.error(
                        "Failed to create the "
                        f"follow-up examination: {error}"
                    )

        # ====================================================
        # 2. EXAM IN PROGRESS (Pending)
        # ====================================================

        elif linked_exam and linked_status == "Pending":

            st.info(
                "This follow-up examination "
                "is already waiting in the "
                "Patient Queue."
            )

        # ====================================================
        # 3. EXAM COMPLETED → MARK FOLLOW-UP COMPLETED
        # ====================================================

        elif can_mark_completed:

            st.success(
                "The examination has been "
                "completed. This follow-up "
                "can now be marked as "
                "completed."
            )

            if st.button(
                "Mark Follow-Up Completed",
                key=(
                    f"complete_follow_up_"
                    f"{follow_up_id}"
                ),
                icon=":material/check_circle:",
                type="primary",
                width="stretch",
            ):

                try:

                    result = complete_follow_up(
                        follow_up_id
                    )

                    if result:

                        st.session_state.pop(
                            "selected_follow_up",
                            None,
                        )

                        remember(
                            "Follow-up completed "
                            "successfully."
                        )

                        st.rerun()

                    else:

                        st.error(
                            "The follow-up "
                            "could not be "
                            "completed."
                        )

                except Exception as error:

                    st.error(
                        "Failed to complete "
                        f"follow-up: {error}"
                    )

        # ====================================================
        # 4. RESCHEDULE / CANCEL
        #    Only while the exam is NOT completed
        # ====================================================

        if can_reschedule_or_cancel:

            st.divider()

            action_col1, action_col2 = (
                st.columns(2)
            )

            if action_col1.button(
                "Reschedule",
                key=(
                    f"reschedule_"
                    f"{follow_up_id}"
                ),
                icon=":material/event_repeat:",
                width="stretch",
            ):

                st.session_state[
                    "reschedule_follow_up_id"
                ] = follow_up_id

                st.rerun()

            if action_col2.button(
                "Cancel Follow-Up",
                key=(
                    f"cancel_"
                    f"{follow_up_id}"
                ),
                icon=":material/cancel:",
                width="stretch",
            ):

                try:

                    result = cancel_follow_up(
                        follow_up_id
                    )

                    if result:

                        st.session_state.pop(
                            "selected_follow_up",
                            None,
                        )

                        remember(
                            "Follow-up cancelled."
                        )

                        st.rerun()

                    else:

                        st.error(
                            "The follow-up could "
                            "not be cancelled."
                        )

                except Exception as error:

                    st.error(
                        "Failed to cancel "
                        f"follow-up: {error}"
                    )

        # ----------------------------------------------------
        # CLOSE
        # ----------------------------------------------------

        if st.button(
            "Close",
            key=(
                f"follow_up_close_"
                f"{follow_up_id}"
            ),
            width="stretch",
        ):

            st.session_state.pop(
                "selected_follow_up",
                None,
            )

            st.rerun()


# ============================================================
# RESCHEDULE FOLLOW-UP DIALOG
# ============================================================

@st.dialog(
    "Reschedule Follow-Up",
    width="medium",
)
def show_reschedule_dialog(
    follow_up,
):

    follow_up_id = get_follow_up_id(
        follow_up
    )

    # ========================================================
    # CURRENT FOLLOW-UP DATE
    # ========================================================

    current_date = (
        follow_up_date_value(
            follow_up
        )
        or date.today()
    )

    min_date = date.today()

    if current_date < min_date:
        current_date = min_date

    max_date = date(
        min_date.year + 10,
        min_date.month,
        min_date.day,
    )

    # ========================================================
    # CURRENT FOLLOW-UP TIME
    # ========================================================

    current_time = time(
        9,
        0,
    )

    raw_time = (
        follow_up.get(
            "follow_up_time"
        )
        or follow_up.get(
            "scheduled_time"
        )
    )

    if raw_time:

        try:

            current_time = time.fromisoformat(
                str(raw_time)[:8]
            )

        except Exception:

            pass

    # ========================================================
    # RESCHEDULE DIALOG
    # ========================================================

    with st.container(
        key=DIALOG_KEY
    ):

        section_title(
            "New Follow-Up Schedule"
        )

        st.caption(
            "Select a new date and time for the "
            "patient's follow-up examination."
        )

        new_date = st.date_input(
            "Follow-Up Date",
            value=current_date,
            min_value=min_date,
            max_value=max_date,
            key=(
                f"reschedule_date_"
                f"{follow_up_id}"
            ),
        )

        new_time = st.time_input(
            "Follow-Up Time",
            value=current_time,
            key=(
                f"reschedule_time_"
                f"{follow_up_id}"
            ),
        )

        st.divider()

        col1, col2 = st.columns(2)

        cancel = col1.button(
            "Cancel",
            key=(
                f"reschedule_cancel_"
                f"{follow_up_id}"
            ),
            width="stretch",
        )

        save = col2.button(
            "Save Schedule",
            key=(
                f"reschedule_save_"
                f"{follow_up_id}"
            ),
            type="primary",
            width="stretch",
        )

    # ========================================================
    # CANCEL
    # ========================================================

    if cancel:

        st.session_state.pop(
            "reschedule_follow_up_id",
            None,
        )

        st.session_state.pop(
            "selected_follow_up",
            None,
        )

        st.rerun()

    # ========================================================
    # SAVE
    # ========================================================

    if save:

        if new_date < min_date:

            st.error(
                "Please select today or a future date "
                "for the follow-up."
            )

            return

        try:

            result = reschedule_follow_up(
                follow_up_id=follow_up_id,
                new_date=new_date,
                new_time=new_time,
            )

            if result and result.get(
                "success"
            ):

                st.session_state.pop(
                    "reschedule_follow_up_id",
                    None,
                )

                st.session_state.pop(
                    "selected_follow_up",
                    None,
                )

                remember(
                    "Follow-up rescheduled successfully."
                )

                st.rerun()

            else:

                message = (
                    result.get(
                        "message"
                    )
                    if isinstance(
                        result,
                        dict,
                    )
                    else None
                )

                st.error(
                    message
                    or (
                        "The follow-up could not "
                        "be rescheduled."
                    )
                )

        except Exception as error:

            st.error(
                "Failed to reschedule "
                f"follow-up: {error}"
            )


# ============================================================
# EXAMINATION DIALOG
# ============================================================

@st.dialog(
    "Examine Patient",
    width="large",
)
def show_complete_exam_dialog(
    patient,
    examination,
):

    user_id = current_user_id()

    examination_id = examination[
        "examination_id"
    ]

    with st.container(
        key=DIALOG_KEY
    ):

        section_title(
            "Patient Information"
        )

        show_rows([
            (
                "Patient",
                patient_name(patient),
            ),
            (
                "Patient ID",
                patient_code(patient),
            ),
            (
                "Date of Birth",
                format_date(
                    patient.get(
                        "date_of_birth"
                    )
                ),
            ),
            (
                "Sex",
                patient.get(
                    "sex"
                )
                or "—",
            ),
            (
                "Examination Type",
                examination.get(
                    "examination_type"
                )
                or "Examination",
            ),
        ])

        render_history_buttons(
            patient,
            key_prefix=(
                f"followups_exam_"
                f"{examination_id}"
            ),
        )

        st.divider()

        section_title(
            "Clinical Data"
        )

        consents = (
            get_examination_consents(
                examination_id
            )
        )

        consent = (
            consents[0]
            if consents
            else None
        )

        vitals = (
            get_examination_vitals(
                examination_id
            )
        )

        if consent and consent.get(
            "given"
        ):

            st.markdown(
                "**Consent signed by:** "
                f"{consent.get('signed_by_name') or '—'}"
            )

            signature_path = (
                consent.get(
                    "signature_path"
                )
            )

            if signature_path:

                signature_url = (
                    get_consent_signature_url(
                        signature_path
                    )
                )

                if signature_url:

                    st.image(
                        signature_url,
                        width=200,
                        caption="Patient signature",
                    )

        else:

            st.warning(
                "No consent on file for "
                "this examination."
            )

        # ----------------------------------------------------
        # VITALS
        # ----------------------------------------------------

        section_title(
            "Vitals"
        )

        v1, v2, v3 = st.columns(3)

        bp_sys = v1.number_input(
            "BP systolic (mmHg)",
            min_value=0,
            max_value=300,
            step=1,
            value=int(
                get_vitals_value(
                    vitals,
                    "bp_systolic",
                )
                or 0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_bp_sys"
            ),
        )

        bp_dia = v2.number_input(
            "BP diastolic (mmHg)",
            min_value=0,
            max_value=200,
            step=1,
            value=int(
                get_vitals_value(
                    vitals,
                    "bp_diastolic",
                )
                or 0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_bp_dia"
            ),
        )

        temperature = v3.number_input(
            "Temperature (°C)",
            min_value=0.0,
            max_value=50.0,
            step=0.1,
            value=float(
                get_vitals_value(
                    vitals,
                    "temperature",
                )
                or 0.0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_temp"
            ),
        )

        v4, v5, v6 = st.columns(3)

        pulse_rate = v4.number_input(
            "Pulse rate (bpm)",
            min_value=0,
            max_value=300,
            step=1,
            value=int(
                get_vitals_value(
                    vitals,
                    "pulse_rate",
                )
                or 0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_pulse"
            ),
        )

        respiratory_rate = v5.number_input(
            "Respiratory rate (/min)",
            min_value=0,
            max_value=100,
            step=1,
            value=int(
                get_vitals_value(
                    vitals,
                    "respiratory_rate",
                )
                or 0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_rr"
            ),
        )

        weight = v6.number_input(
            "Weight (kg)",
            min_value=0.0,
            max_value=500.0,
            step=0.1,
            value=float(
                get_vitals_value(
                    vitals,
                    "weight_kg",
                )
                or 0.0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_weight"
            ),
        )

        v7, v8, v9 = st.columns(3)

        height = v7.number_input(
            "Height (cm)",
            min_value=0.0,
            max_value=300.0,
            step=0.1,
            value=float(
                get_vitals_value(
                    vitals,
                    "height_cm",
                )
                or 0.0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_height"
            ),
        )

        spo2 = v8.number_input(
            "SpO2 (%)",
            min_value=0,
            max_value=100,
            step=1,
            value=int(
                get_vitals_value(
                    vitals,
                    "spo2",
                )
                or 0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_spo2"
            ),
        )

        heart_rate = v9.number_input(
            "Heart rate (bpm)",
            min_value=0,
            max_value=300,
            step=1,
            value=int(
                get_vitals_value(
                    vitals,
                    "heart_rate",
                )
                or 0
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_heart_rate"
            ),
        )

        bmi = calculate_bmi(
            weight,
            height,
        )

        if bmi:

            label, tone = bmi_tone(
                bmi
            )

            st.markdown(
                f"**BMI:** {bmi} "
                f"{pill(label, tone)}",
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------
        # CLINICAL NOTES
        # ----------------------------------------------------

        st.divider()

        section_title(
            "Clinical Notes"
        )

        chief_complaint = st.text_area(
            "Chief complaint",
            value=(
                examination.get(
                    "chief_complaint"
                )
                or ""
            ),
            height=80,
            key=(
                f"followups_exam_"
                f"{examination_id}_chief"
            ),
        )

        hpi = st.text_area(
            "History of present illness",
            value=(
                examination.get(
                    "history_of_present_illness"
                )
                or ""
            ),
            height=120,
            key=(
                f"followups_exam_"
                f"{examination_id}_hpi"
            ),
        )

        physical_exam = st.text_area(
            "Physical examination",
            value=(
                examination.get(
                    "physical_examination"
                )
                or ""
            ),
            height=120,
            key=(
                f"followups_exam_"
                f"{examination_id}_physical"
            ),
        )

        # ----------------------------------------------------
        # ORDERS
        # ----------------------------------------------------

        st.divider()

        section_title(
            "Doctor Orders"
        )

        order = st.radio(
            "Select next step",
            [
                "No Request",
                "Chest X-Ray",
            ],
            key=(
                f"followups_exam_"
                f"{examination_id}_order"
            ),
            horizontal=True,
        )

        diagnosis = None
        plans = None
        disposition = None
        disposition_notes = None
        follow_up_date = None
        follow_up_notes = None

        if order == "No Request":

            diagnosis = st.text_area(
                "Diagnosis / Assessment",
                value=(
                    examination.get(
                        "diagnosis"
                    )
                    or ""
                ),
                height=100,
                key=(
                    f"followups_exam_"
                    f"{examination_id}_diagnosis"
                ),
            )

            plans = st.text_area(
                "Plans / Orders",
                value=(
                    examination.get(
                        "plans_orders"
                    )
                    or ""
                ),
                height=100,
                key=(
                    f"followups_exam_"
                    f"{examination_id}_plans"
                ),
            )

            st.divider()

            section_title(
                "Disposition"
            )

            disposition_options = [
                "Admission",
                "Treated and Sent Home",
                "Referred",
                "Refused Admission",
                "Nowhere When Called",
            ]

            current_disposition = (
                examination.get(
                    "disposition"
                )
            )

            disposition_index = (
                disposition_options.index(
                    current_disposition
                )
                if current_disposition
                in disposition_options
                else 0
            )

            disposition = st.selectbox(
                "Disposition",
                disposition_options,
                index=disposition_index,
                key=(
                    f"followups_exam_"
                    f"{examination_id}_"
                    "disposition"
                ),
            )

            disposition_notes = st.text_area(
                "Disposition notes",
                value=(
                    examination.get(
                        "disposition_notes"
                    )
                    or ""
                ),
                height=100,
                key=(
                    f"followups_exam_"
                    f"{examination_id}_"
                    "disposition_notes"
                ),
            )

        else:

            st.info(
                "A Chest X-Ray request will "
                "be created for the Radiologic "
                "Technologist."
            )

        # ----------------------------------------------------
        # ACTIONS
        # ----------------------------------------------------

        st.divider()

        cancel_col, save_col = st.columns(2)

        cancel_clicked = cancel_col.button(
            "Cancel",
            key=(
                f"followups_exam_"
                f"{examination_id}_cancel"
            ),
            width="stretch",
        )

        save_clicked = save_col.button(
            (
                "Request X-Ray"
                if order
                == "Chest X-Ray"
                else "Complete Examination"
            ),
            key=(
                f"followups_exam_"
                f"{examination_id}_save"
            ),
            type="primary",
            width="stretch",
        )

    # --------------------------------------------------------
    # ACTION HANDLING
    # --------------------------------------------------------

    if cancel_clicked:

        clear_dialog_state()

        st.rerun()

    if not save_clicked:

        return

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not chief_complaint.strip():

        st.error(
            "Chief complaint is required."
        )

        return

    if (
        order == "No Request"
        and not diagnosis.strip()
    ):

        st.error(
            "Diagnosis is required."
        )

        return

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    try:

        original_vitals = (
            vitals[0]
            if vitals
            else {}
        )

        if (
            (bp_sys or None)
            != original_vitals.get(
                "bp_systolic"
            )
            or
            (bp_dia or None)
            != original_vitals.get(
                "bp_diastolic"
            )
            or
            (temperature or None)
            != original_vitals.get(
                "temperature"
            )
        ):

            add_examination_vitals(
                examination_id=(
                    examination_id
                ),
                recorded_by=user_id,
                recorded_by_role="doctor",
                bp_systolic=(
                    bp_sys or None
                ),
                bp_diastolic=(
                    bp_dia or None
                ),
                temperature=(
                    temperature or None
                ),
            )

        if any([
            pulse_rate,
            respiratory_rate,
            weight,
            height,
            spo2,
            heart_rate,
        ]):

            add_examination_vitals(
                examination_id=(
                    examination_id
                ),
                recorded_by=user_id,
                recorded_by_role="doctor",
                pulse_rate=(
                    pulse_rate or None
                ),
                respiratory_rate=(
                    respiratory_rate or None
                ),
                weight_kg=(
                    weight or None
                ),
                height_cm=(
                    height or None
                ),
                spo2=(
                    spo2 or None
                ),
                heart_rate=(
                    heart_rate or None
                ),
                bmi=bmi,
            )

        # ----------------------------------------------------
        # NO X-RAY
        # ----------------------------------------------------

        if order == "No Request":

            update_examination(
                examination_id=(
                    examination_id
                ),
                status="Completed",
                reviewed_by=user_id,
                chief_complaint=(
                    chief_complaint.strip()
                    or None
                ),
                history_of_present_illness=(
                    hpi.strip()
                    or None
                ),
                physical_examination=(
                    physical_exam.strip()
                    or None
                ),
                diagnosis=(
                    diagnosis.strip()
                    or None
                ),
                plans_orders=(
                    plans.strip()
                    or None
                ),
                disposition=disposition,
                disposition_notes=(
                    disposition_notes.strip()
                    if disposition_notes
                    else None
                ),
            )

            follow_up_id = (
                st.session_state.get(
                    "active_follow_up_id"
                )
            )

            if follow_up_id:

                complete_follow_up(
                    follow_up_id
                )

                st.session_state.pop(
                    "active_follow_up_id",
                    None,
                )

            clear_dialog_state()

            remember(
                "Examination completed successfully."
            )

            st.rerun()

        # ----------------------------------------------------
        # X-RAY
        # ----------------------------------------------------

        update_examination(
            examination_id=(
                examination_id
            ),
            status="Awaiting X-Ray",
            reviewed_by=user_id,
            chief_complaint=(
                chief_complaint.strip()
                or None
            ),
            history_of_present_illness=(
                hpi.strip()
                or None
            ),
            physical_examination=(
                physical_exam.strip()
                or None
            ),
        )

        create_xray_request(
            examination_id=(
                examination_id
            ),
            hospital_id=(
                current_hospital_id()
            ),
            requested_by=user_id,
            body_part="Chest",
            priority="Routine",
            clinical_indication=(
                chief_complaint.strip()
                or None
            ),
        )

        clear_dialog_state()

        remember(
            "Chest X-Ray requested. "
            "Patient is now awaiting "
            "X-Ray processing."
        )

        st.rerun()

    except Exception as error:

        st.error(
            f"Failed to save examination: {error}"
        )


# ============================================================
# MULTIPLE EXAMINATIONS DIALOG
# ============================================================

@st.dialog(
    "Patient Examinations",
    width="medium",
)
def show_pending_exams_dialog(
    patient,
    examinations,
):

    with st.container(
        key=DIALOG_KEY
    ):

        show_rows([
            (
                "Patient",
                patient_name(patient),
            ),
            (
                "Patient ID",
                patient_code(patient),
            ),
        ])

        section_title(
            f"{len(examinations)} Examination(s)"
        )

        for examination in sorted(
            examinations,
            key=lambda item:
                item.get(
                    "created_at"
                )
                or "",
        ):

            waiting = waiting_minutes(
                examination.get(
                    "created_at"
                )
            )

            st.markdown(
                f"**{examination.get('examination_type') or 'Examination'}**"
            )

            st.caption(
                format_datetime(
                    examination_datetime(
                        examination
                    )
                )
            )

            st.markdown(
                pill(
                    format_waiting(
                        waiting
                    ),
                    waiting_tone(
                        waiting
                    ),
                ),
                unsafe_allow_html=True,
            )

            if st.button(
                "Examine Patient",
                key=(
                    "followups_open_pending_"
                    f"{examination['examination_id']}"
                ),
                type="primary",
                width="stretch",
            ):

                st.session_state.pop(
                    "pending_exams_patient",
                    None,
                )

                st.session_state[
                    "selected_examination"
                ] = examination

                st.session_state[
                    "edit_patient"
                ] = patient

                st.rerun()

            st.divider()

        if st.button(
            "Close",
            key="followups_pending_exams_close",
            width="stretch",
        ):

            st.session_state.pop(
                "pending_exams_patient",
                None,
            )

            st.rerun()


# ============================================================
# QUEUE METRICS
# ============================================================

def render_metrics(
    grouped,
    xray_requests,
    follow_ups,
):

    total_patients = len(
        grouped
    )

    total_exams = sum(
        len(item["exams"])
        for item in grouped
    )

    xray_count = len(
        xray_requests
    )

    follow_up_count = len(
        [
            item
            for item in follow_ups
            if get_follow_up_status(item)
            in ACTIVE_FOLLOW_UP_STATUSES
        ]
    )

    m1, m2, m3, m4 = st.columns(4)

    with m1:

        metric_card(
            "Patients waiting",
            total_patients,
            "groups",
            tone="blue",
        )

    with m2:

        metric_card(
            "Pending examinations",
            total_exams,
            "pending_actions",
            tone="amber",
        )

    with m3:

        metric_card(
            "Pending X-Ray requests",
            xray_count,
            "radiology",
            tone="blue",
        )

    with m4:

        metric_card(
            "Active follow-ups",
            follow_up_count,
            "event",
            tone="amber",
        )


# ============================================================
# PATIENT QUEUE TABLE
# ============================================================

def render_queue_table(
    grouped,
    key_prefix="queue",
):

    if not grouped:

        empty_state(
            "No examinations are currently "
            "waiting for physician review."
        )

        return

    with st.container(
        key=(
            "physician_followups_queue_"
            f"{key_prefix}"
        )
    ):

        table_header(
            QUEUE_HEADERS,
            QUEUE_WIDTHS,
            key_prefix,
        )

        for item in grouped:

            patient = item[
                "patient"
            ]

            examinations = item[
                "exams"
            ]

            waiting = item[
                "oldest_waiting"
            ]

            patient_id = patient.get(
                "patient_id"
            )

            with table_row(
                f"{key_prefix}_row_{patient_id}",
                QUEUE_WIDTHS,
            ) as columns:

                name_cell(
                    columns[0],
                    patient_name(
                        patient
                    ),
                    sub=patient_code(
                        patient
                    ),
                )

                text_cell(
                    columns[1],
                    str(
                        len(
                            examinations
                        )
                    ),
                )

                pill_cell(
                    columns[2],
                    format_waiting(
                        waiting
                    ),
                    waiting_tone(
                        waiting
                    ),
                )

                if columns[3].button(
                    "History",
                    key=(
                        f"{key_prefix}_"
                        f"history_{patient_id}"
                    ),
                    icon=":material/folder_open:",
                    width="stretch",
                ):

                    clear_dialog_state()

                    st.session_state[
                        "history_patient"
                    ] = patient

                    st.rerun()

                if len(examinations) == 1:

                    if columns[4].button(
                        "Examine",
                        key=(
                            f"{key_prefix}_"
                            f"examine_{patient_id}"
                        ),
                        icon=":material/clinical_notes:",
                        type="primary",
                        width="stretch",
                    ):

                        clear_dialog_state()

                        st.session_state[
                            "selected_examination"
                        ] = examinations[0]

                        st.session_state[
                            "edit_patient"
                        ] = patient

                        st.rerun()

                else:

                    if columns[4].button(
                        "View Exams",
                        key=(
                            f"{key_prefix}_"
                            f"view_{patient_id}"
                        ),
                        icon=":material/list:",
                        type="primary",
                        width="stretch",
                    ):

                        clear_dialog_state()

                        st.session_state[
                            "pending_exams_patient"
                        ] = {
                            "patient": patient,
                            "exams": examinations,
                        }

                        st.rerun()


# ============================================================
# X-RAY REQUEST TABLE
# ============================================================

def render_xray_request_table(
    xray_requests,
    key_prefix="xray",
):

    if not xray_requests:

        empty_state(
            "You have no pending X-Ray requests."
        )

        return

    with st.container(
        key=(
            "physician_followups_xray_"
            f"{key_prefix}"
        )
    ):

        table_header(
            XRAY_QUEUE_HEADERS,
            XRAY_QUEUE_WIDTHS,
            key_prefix,
        )

        for request in xray_requests:

            patient = (
                request.get(
                    "patients"
                )
                or {}
            )

            request_id = request.get(
                "request_id"
            )

            requested_at = (
                xray_request_datetime(
                    request
                )
            )

            waiting = waiting_minutes(
                requested_at
            )

            with table_row(
                f"{key_prefix}_row_{request_id}",
                XRAY_QUEUE_WIDTHS,
            ) as columns:

                name_cell(
                    columns[0],
                    patient_name(
                        patient
                    ),
                    sub=patient_code(
                        patient
                    ),
                )

                pill_cell(
                    columns[1],
                    format_waiting(
                        waiting
                    ),
                    waiting_tone(
                        waiting
                    ),
                )

                text_cell(
                    columns[2],
                    format_datetime(
                        requested_at
                    ),
                )

                pill_cell(
                    columns[3],
                    "Pending",
                    "amber",
                )

                if columns[4].button(
                    "View",
                    key=(
                        f"{key_prefix}_"
                        f"view_{request_id}"
                    ),
                    icon=":material/visibility:",
                    width="stretch",
                ):

                    clear_dialog_state()

                    st.session_state[
                        "xray_request_patient"
                    ] = request

                    st.rerun()


# ============================================================
# FOLLOW-UP TABLE
# ============================================================

def render_follow_up_table(
    follow_ups,
    key_prefix="followups",
):

    grouped = group_active_follow_ups_by_patient(follow_ups)

    if not grouped:

        empty_state(
            "There are no scheduled follow-up "
            "visits requiring action."
        )

        return

    with st.container(
        key=(
            "physician_followups_table_"
            f"{key_prefix}"
        )
    ):

        table_header(
            FOLLOW_UP_HEADERS,
            FOLLOW_UP_WIDTHS,
            key_prefix,
        )

        for entry in grouped:

            patient = entry["patient"]
            patient_id = patient.get("patient_id")

            next_follow_up = entry["next_follow_up"]
            all_follow_ups = entry["follow_ups"]

            source_exam = get_source_examination(
                next_follow_up
            )

            # ------------------------------------------------
            # STATUS PILL
            #
            # Priority:
            #   1. If ANY follow-up is Rescheduled -> amber
            #   2. Else use the next follow-up's own status
            # ------------------------------------------------

            has_rescheduled = any(
                get_follow_up_status(item) == "Rescheduled"
                for item in all_follow_ups
            )

            if has_rescheduled:
                status_label = "Rescheduled"
                status_tone = "amber"
            else:
                status_label = get_follow_up_status(
                    next_follow_up
                )
                status_tone = follow_up_status_tone(
                    status_label
                )

            # ------------------------------------------------
            # FOLLOW-UP COUNT BADGE
            # ------------------------------------------------

            patient_sub = patient_code(patient)

            if len(all_follow_ups) > 1:
                patient_sub = (
                    f"{patient_sub} • "
                    f"{len(all_follow_ups)} follow-ups"
                )

            with table_row(
                f"{key_prefix}_row_{patient_id}",
                FOLLOW_UP_WIDTHS,
            ) as columns:

                name_cell(
                    columns[0],
                    patient_name(patient),
                    sub=patient_sub,
                )

                text_cell(
                    columns[1],
                    format_follow_up_datetime(
                        next_follow_up
                    ),
                )

                text_cell(
                    columns[2],
                    source_exam.get(
                        "examination_type"
                    )
                    or "Examination",
                )

                pill_cell(
                    columns[3],
                    status_label,
                    status_tone,
                )

                if columns[4].button(
                    "Manage",
                    key=(
                        f"{key_prefix}_"
                        f"manage_{patient_id}"
                    ),
                    icon=":material/event_note:",
                    type="primary",
                    width="stretch",
                ):

                    clear_dialog_state()

                    st.session_state[
                        "selected_patient_follow_ups"
                    ] = {
                        "patient": patient,
                        "follow_ups": all_follow_ups,
                    }

                    st.rerun()


# ============================================================
# PAGE
# ============================================================

def show():

    # --------------------------------------------------------
    # CSS
    # --------------------------------------------------------

    load_css("patient_queue.css")

    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    # --------------------------------------------------------
    # ACCESS
    # --------------------------------------------------------

    if role_id == ROLE_SUPERADMIN:

        filter_hospital = None

    elif role_id in DOCTOR_ROLES:

        filter_hospital = hospital_id

    elif role_id == ROLE_HOSPITAL_ADMIN:

        filter_hospital = hospital_id

    else:

        st.error(
            "You don't have access to "
            "the physician follow-up page."
        )

        return

    # --------------------------------------------------------
    # PAGE
    # --------------------------------------------------------

    with st.container(key=PAGE_KEY):

        page_header(
            "Follow-Up Management",
            (
                "Review patients awaiting physician "
                "care, monitor pending X-Ray requests, "
                "and manage scheduled follow-up visits."
            ),
        )

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key="physician_followups_refresh",
            width="stretch",
        ):

            st.rerun()

        # ----------------------------------------------------
        # LOAD PENDING EXAMINATIONS
        # ----------------------------------------------------

        try:

            pending = get_pending_examinations(
                hospital_id=filter_hospital
            )

        except Exception as error:

            st.error(
                "Failed to load patient queue: "
                f"{error}"
            )

            pending = []

        # ----------------------------------------------------
        # LOAD X-RAY REQUESTS
        # ----------------------------------------------------

        try:

            xray_requests = get_pending_xray_requests(
                hospital_id=filter_hospital
            )

        except Exception as error:

            st.error(
                "Failed to load X-Ray requests: "
                f"{error}"
            )

            xray_requests = []

        # Physicians only see requests
        # they created.

        if role_id in DOCTOR_ROLES:

            user_id = current_user_id()

            xray_requests = [
                request
                for request in xray_requests
                if str(request.get("requested_by"))
                == str(user_id)
            ]

        # ----------------------------------------------------
        # LOAD FOLLOW-UPS
        # ----------------------------------------------------

        try:

            follow_ups = get_hospital_follow_ups(
                hospital_id=filter_hospital
            )

            follow_ups = follow_ups or []

        except Exception as error:

            st.error(
                "Failed to load follow-ups: "
                f"{error}"
            )

            follow_ups = []

        # ----------------------------------------------------
        # GROUP DATA
        # ----------------------------------------------------

        grouped = group_pending_by_patient(pending)

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        render_metrics(
            grouped,
            xray_requests,
            follow_ups,
        )

        st.divider()

        # ====================================================
        # SECTION 1
        # ====================================================

        section_title(
            "Patients Awaiting Physician Review"
        )

        st.caption(
            "Patients who currently have an "
            "examination waiting for physician "
            "review."
        )

        render_queue_table(
            grouped,
            key_prefix="pending",
        )

        # ====================================================
        # SECTION 2
        # ====================================================

        st.divider()

        section_title(
            "Pending X-Ray Requests"
        )

        st.caption(
            "Chest X-Ray requests that are currently "
            "waiting for Radiologic Technologist "
            "processing."
        )

        render_xray_request_table(
            xray_requests,
            key_prefix="xray",
        )

        # ====================================================
        # SECTION 3
        # ====================================================

        st.divider()

        section_title(
            "Follow-Up Visits Requiring Action"
        )

        st.caption(
            "Scheduled follow-up visits that have "
            "not yet been completed. When the patient "
            "returns, start the follow-up examination "
            "to place the patient in the Patient Queue."
        )

        render_follow_up_table(
            follow_ups,
            key_prefix="followup",
        )

    # ========================================================
    # DIALOGS
    # ========================================================

    # --------------------------------------------------------
    # 1. COMPLETE EXAMINATION
    # --------------------------------------------------------

    if st.session_state.get("selected_examination"):

        examination = st.session_state[
            "selected_examination"
        ]

        patient = st.session_state.get("edit_patient")

        if patient:

            show_complete_exam_dialog(
                patient,
                examination,
            )

    # --------------------------------------------------------
    # 2. MULTIPLE PENDING EXAMINATIONS
    # --------------------------------------------------------

    elif st.session_state.get("pending_exams_patient"):

        data = st.session_state[
            "pending_exams_patient"
        ]

        show_pending_exams_dialog(
            data["patient"],
            data["exams"],
        )

    # --------------------------------------------------------
    # 3. X-RAY REQUEST DETAILS
    # --------------------------------------------------------

    elif st.session_state.get("xray_request_patient"):

        show_xray_request_dialog(
            st.session_state["xray_request_patient"]
        )

    # --------------------------------------------------------
    # 4. PATIENT-LEVEL FOLLOW-UPS (GROUPED VIEW)
    # --------------------------------------------------------

    elif st.session_state.get("selected_patient_follow_ups"):

        data = st.session_state[
            "selected_patient_follow_ups"
        ]

        show_patient_follow_ups_dialog(
            data["patient"],
            data["follow_ups"],
        )

    # --------------------------------------------------------
    # 5. SINGLE FOLLOW-UP DETAILS
    # --------------------------------------------------------

    elif st.session_state.get("selected_follow_up"):

        follow_up = st.session_state[
            "selected_follow_up"
        ]

        follow_up_id = get_follow_up_id(follow_up)

        try:

            refreshed = get_follow_up(follow_up_id)

            if refreshed:

                follow_up = refreshed

                st.session_state[
                    "selected_follow_up"
                ] = refreshed

        except Exception:

            pass

        show_follow_up_dialog(follow_up)

    # --------------------------------------------------------
    # 6. RESCHEDULE FOLLOW-UP
    # --------------------------------------------------------

    elif st.session_state.get("reschedule_follow_up_id"):

        follow_up_id = st.session_state[
            "reschedule_follow_up_id"
        ]

        try:

            follow_up = get_follow_up(follow_up_id)

            if follow_up:

                show_reschedule_dialog(follow_up)

            else:

                st.session_state.pop(
                    "reschedule_follow_up_id",
                    None,
                )

        except Exception as error:

            st.session_state.pop(
                "reschedule_follow_up_id",
                None,
            )

            st.error(
                "Failed to load follow-up: "
                f"{error}"
            )

    # --------------------------------------------------------
    # 7. PATIENT HISTORY DIALOG
    # --------------------------------------------------------

    elif st.session_state.get("history_patient"):

        show_patient_history_dialog(
            st.session_state["history_patient"]
        )

    # --------------------------------------------------------
    # 8. PREVIOUS EXAMINATIONS DIALOG
    # --------------------------------------------------------

    elif st.session_state.get("previous_examinations_patient"):

        show_previous_examinations_dialog(
            st.session_state[
                "previous_examinations_patient"
            ]
        )

    # --------------------------------------------------------
    # 9. PREVIOUS MEDICAL RECORDS DIALOG
    # --------------------------------------------------------

    elif st.session_state.get("previous_medical_records_patient"):

        show_previous_medical_records_dialog(
            st.session_state[
                "previous_medical_records_patient"
            ]
        )