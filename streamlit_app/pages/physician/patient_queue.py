import streamlit as st

from datetime import datetime, timezone

from backend.fetches import (
    get_pending_examinations,
    get_medical_records_by_patient,
    get_pending_xray_requests,
    get_examinations_by_patient,
    get_examination_consents,
    get_examination_vitals,
    get_consent_signature_url,
)

from backend.crud import (
    update_examination,
    add_examination_vitals,
    create_xray_request,
)

from streamlit_app.components.ui import (
    load_css,
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

DISPOSITION_OPTIONS = [
    "Admission",
    "Treated and Sent Home",
    "Referred",
    "Refused Admission",
    "Nowhere When Called",
]

FOLLOW_UP_DISPOSITIONS = [
    "Treated and Sent Home",
    "Referred",
    "Refused Admission",
]


# ============================================================
# QUEUE TABLE
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


# ============================================================
# X-RAY REQUEST TABLE
# ============================================================

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

def format_datetime(value):
    """
    Displays a complete date and time.

    Example:
    September 25, 2026 at 02:30 PM
    """

    if not value:
        return "—"

    try:

        if isinstance(value, datetime):

            dt = value

        else:

            value = str(value)

            if value.endswith("Z"):

                value = value.replace(
                    "Z",
                    "+00:00",
                )

            dt = datetime.fromisoformat(
                value
            )

        if dt.tzinfo is None:

            return dt.strftime(
                "%B %d, %Y at %I:%M %p"
            )

        return dt.astimezone().strftime(
            "%B %d, %Y at %I:%M %p"
        )

    except Exception:

        return str(value)


def examination_datetime(examination):
    """
    Prefer examination date/time and fall back
    to created_at.
    """

    return (
        examination.get("examination_date")
        or examination.get("created_at")
    )


def medical_record_datetime(record):
    """
    Prefer record date/time and fall back
    to created_at.
    """

    return (
        record.get("record_date")
        or record.get("created_at")
    )


def xray_request_datetime(examination):
    """
    Determines the date/time that the X-Ray request
    was created.

    The examination's updated_at is intentionally not
    preferred because it may change for reasons unrelated
    to the X-Ray request.

    Current fallback:
        created_at

    If the xray_requests table later exposes
    requested_at, that should be used directly.
    """

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

        now = datetime.now(
            timezone.utc
        )

        delta = now - created

        return max(
            0,
            int(
                delta.total_seconds()
                // 60
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

    return (
        f"{hours}h "
        f"{minutes % 60}m"
    )


# ============================================================
# BMI
# ============================================================

def calculate_bmi(
    weight_kg,
    height_cm,
):

    try:

        weight = float(
            weight_kg
        )

        height = (
            float(height_cm)
            / 100
        )

        if (
            weight <= 0
            or height <= 0
        ):

            return None

        return round(
            weight
            / (height * height),
            2,
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


def bmi_tone(
    bmi_value,
):

    if bmi_value is None:

        return (
            "—",
            "grey",
        )

    if bmi_value < 18.5:

        return (
            "Underweight",
            "blue",
        )

    if bmi_value < 25:

        return (
            "Normal",
            "green",
        )

    if bmi_value < 30:

        return (
            "Overweight",
            "amber",
        )

    return (
        "Obese",
        "red",
    )


def get_vitals_value(
    vitals_list,
    field_name,
):

    for vital in vitals_list:

        if vital.get(field_name) is not None:

            return vital[field_name]

    return None


# ============================================================
# STATE CLEANUP
# ============================================================

def clear_queue_dialog_state():

    for key in (
        "selected_examination",
        "edit_patient",
        "history_patient",
        "pending_exams_patient",
        "xray_request_patient",
    ):

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

        by_patient[
            patient_id
        ]["exams"].append(
            examination
        )

        waiting = waiting_minutes(
            examination.get(
                "created_at"
            )
        )

        if (
            waiting
            > by_patient[
                patient_id
            ]["oldest_waiting"]
        ):

            by_patient[
                patient_id
            ]["oldest_waiting"] = waiting

    grouped = list(
        by_patient.values()
    )

    grouped.sort(
        key=lambda item: (
            item["oldest_waiting"]
        ),
        reverse=True,
    )

    return grouped


# ============================================================
# GET X-RAY REQUESTS
# ============================================================

def get_physician_xray_requests(
    examinations,
):
    """
    Extracts examinations where the physician
    requested a Chest X-Ray.

    These records are displayed separately from
    the normal patient examination queue.

    They are VIEW-ONLY on this page.

    A request is considered active while its
    examination status is:

        Awaiting X-Ray

    or:

        Pending X-Ray

    """

    user_id = current_user_id()

    requests = []

    for examination in examinations:

        status = (
            examination.get("status")
            or ""
        )

        examination_type = (
            examination.get(
                "examination_type"
            )
            or ""
        )

        reviewed_by = (
            examination.get(
                "reviewed_by"
            )
        )

        is_xray_status = status in (
            "Awaiting X-Ray",
            "Pending X-Ray",
        )

        is_chest_xray = (
            "x-ray"
            in examination_type.lower()
            or
            "xray"
            in examination_type.lower()
            or
            examination_type.lower()
            == "chest"
        )

        requested_by_current_physician = (
            not user_id
            or not reviewed_by
            or str(reviewed_by)
            == str(user_id)
        )

        if (
            is_xray_status
            and (
                is_chest_xray
                or status
                == "Awaiting X-Ray"
            )
            and requested_by_current_physician
        ):

            requests.append(
                examination
            )

    requests.sort(
        key=lambda item: (
            xray_request_datetime(item)
            or ""
        ),
        reverse=True,
    )

    return requests


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
        key="physician_history_dialog"
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
                patient.get("sex")
                or "—",
            ),
        ])

        st.divider()

        # ====================================================
        # EXAMINATION HISTORY
        # ====================================================

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
                key=lambda item: (
                    examination_datetime(
                        item
                    )
                    or ""
                ),
                reverse=True,
            ):

                status = (
                    examination.get(
                        "status"
                    )
                    or "Unknown"
                )

                status_tone = (
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
                    f"{pill(
                        status,
                        status_tone
                    )}",
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

        # ====================================================
        # EXTERNAL / PREVIOUS MEDICAL RECORDS
        # ====================================================

        section_title(
            "Previous Medical / External Records"
        )

        try:

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
                key=lambda item: (
                    medical_record_datetime(
                        item
                    )
                    or ""
                ),
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
            key="physician_history_close",
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
            key=lambda item: (
                examination_datetime(
                    item
                )
                or ""
            ),
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
                f"{format_datetime(
                    examination_datetime(
                        examination
                    )
                )}"
            )

            st.markdown(
                "**Status:** "
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
        key="previous_exam_close",
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

    records = (
        get_medical_records_by_patient(
            patient_id
        )
    )

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
            key=lambda item: (
                medical_record_datetime(
                    item
                )
                or ""
            ),
            reverse=True,
        ):

            st.markdown(
                f"### "
                f"{record.get('record_type') or 'Medical Record'}"
            )

            st.markdown(
                "**Date & Time:** "
                f"{format_datetime(
                    medical_record_datetime(
                        record
                    )
                )}"
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
        key="previous_medical_records_close",
        width="stretch",
    ):

        st.session_state.pop(
            "previous_medical_records_patient",
            None,
        )

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
        key="physician_xray_request_dialog"
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
            key=(
                "physician_xray_request_close"
            ),
            width="stretch",
        ):

            st.session_state.pop(
                "xray_request_patient",
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
        "Open previous examinations and previous "
        "medical histories separately to keep "
        "the examination screen clear."
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
# DISPOSITION
# ============================================================

def render_disposition_block(
    examination,
    key_prefix,
):

    result = {
        "disposition": None,
        "disp_notes": None,
        "follow_up_date": None,
        "follow_up_notes": None,
    }

    st.divider()

    section_title(
        "Disposition"
    )

    current_disposition = (
        examination.get(
            "disposition"
        )
    )

    disposition_index = (
        DISPOSITION_OPTIONS.index(
            current_disposition
        )
        if current_disposition
        in DISPOSITION_OPTIONS
        else 0
    )

    disposition = st.selectbox(
        "Disposition",
        DISPOSITION_OPTIONS,
        index=disposition_index,
        key=(
            f"{key_prefix}_"
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
            f"{key_prefix}_"
            "disposition_notes"
        ),
    )

    result[
        "disposition"
    ] = disposition

    result[
        "disp_notes"
    ] = disposition_notes

    if disposition in FOLLOW_UP_DISPOSITIONS:

        st.divider()

        section_title(
            "Follow-Up"
        )

        follow_up_date = st.date_input(
            "Follow-up date",
            value=None,
            key=(
                f"{key_prefix}_"
                "follow_up_date"
            ),
        )

        follow_up_notes = st.text_area(
            "Follow-up notes",
            value="",
            height=80,
            key=(
                f"{key_prefix}_"
                "follow_up_notes"
            ),
        )

        result[
            "follow_up_date"
        ] = follow_up_date

        result[
            "follow_up_notes"
        ] = follow_up_notes

    return result


# ============================================================
# COMPLETE EXAMINATION
# ============================================================

@st.dialog(
    "Examine Patient",
    width="large",
)
def show_complete_exam_dialog(
    patient,
    examination,
):

    user_id = current_user().get(
        "user_id"
    )

    examination_id = examination[
        "examination_id"
    ]

    with st.container(
        key="physician_examine_dialog"
    ):

        # ----------------------------------------------------
        # PATIENT INFORMATION
        # ----------------------------------------------------

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
                patient.get("sex")
                or "—",
            ),
        ])

        # ----------------------------------------------------
        # HISTORY BUTTONS
        # ----------------------------------------------------

        render_history_buttons(
            patient,
            key_prefix=(
                f"exam_{examination_id}"
            ),
        )

        st.divider()

        # ----------------------------------------------------
        # NURSE DATA
        # ----------------------------------------------------

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

        if (
            consent
            and consent.get("given")
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
                        caption=(
                            "Patient signature"
                        ),
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
                f"exam_{examination_id}_"
                "bp_sys"
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
                f"exam_{examination_id}_"
                "bp_dia"
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
                f"exam_{examination_id}_"
                "temp"
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
                f"exam_{examination_id}_"
                "pulse"
            ),
        )

        respiratory_rate = (
            v5.number_input(
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
                    f"exam_{examination_id}_"
                    "rr"
                ),
            )
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
                f"exam_{examination_id}_"
                "weight"
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
                f"exam_{examination_id}_"
                "height"
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
                f"exam_{examination_id}_"
                "spo2"
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
                f"exam_{examination_id}_"
                "heart_rate"
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
                f"exam_{examination_id}_"
                "chief"
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
                f"exam_{examination_id}_"
                "hpi"
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
                f"exam_{examination_id}_"
                "physical"
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
                f"exam_{examination_id}_"
                "order"
            ),
            horizontal=True,
        )

        diagnosis = None
        plans = None
        disposition_result = None

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
                    f"exam_{examination_id}_"
                    "diagnosis"
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
                    f"exam_{examination_id}_"
                    "plans"
                ),
            )

            disposition_result = (
                render_disposition_block(
                    examination,
                    key_prefix=(
                        f"exam_{examination_id}"
                        "_disp"
                    ),
                )
            )

        else:

            st.info(
                "A chest X-Ray request will "
                "be created for the "
                "Radiologic Technologist."
            )

        # ----------------------------------------------------
        # ACTIONS
        # ----------------------------------------------------

        st.divider()

        cancel_col, save_col = (
            st.columns(2)
        )

        cancel_clicked = (
            cancel_col.button(
                "Cancel",
                key=(
                    f"exam_{examination_id}_"
                    "cancel"
                ),
                width="stretch",
            )
        )

        save_clicked = (
            save_col.button(
                (
                    "Request X-Ray"
                    if order
                    == "Chest X-Ray"
                    else "Examine Patient"
                ),
                key=(
                    f"exam_{examination_id}_"
                    "save"
                ),
                type="primary",
                width="stretch",
            )
        )

    if cancel_clicked:

        clear_queue_dialog_state()

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
                    respiratory_rate
                    or None
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

        # ====================================================
        # NO X-RAY
        # ====================================================

        if order == "No Request":

            follow_up_date = (
                disposition_result[
                    "follow_up_date"
                ]
            )

            follow_up_notes = (
                disposition_result[
                    "follow_up_notes"
                ]
            )

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
                disposition=(
                    disposition_result[
                        "disposition"
                    ]
                ),
                disposition_notes=(
                    disposition_result[
                        "disp_notes"
                    ].strip()
                    or None
                ),
                follow_up_date=(
                    follow_up_date.isoformat()
                    if follow_up_date
                    else None
                ),
                follow_up_notes=(
                    follow_up_notes.strip()
                    if follow_up_notes
                    else None
                ),
            )

            clear_queue_dialog_state()

            remember(
                "Examination completed successfully."
            )

            st.rerun()

        # ====================================================
        # X-RAY REQUEST
        # ====================================================

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

        clear_queue_dialog_state()

        remember(
            "Chest X-Ray requested. "
            "Patient is now awaiting X-Ray result."
        )

        st.rerun()

    except Exception as error:

        st.error(
            f"Failed to save examination: {error}"
        )


# ============================================================
# QUEUE METRICS
# ============================================================

def render_metrics(
    grouped,
    xray_requests,
    key_prefix="metrics",
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

    if grouped:

        longest = max(
            item["oldest_waiting"]
            for item in grouped
        )

        average = (
            sum(
                item["oldest_waiting"]
                for item in grouped
            )
            // total_patients
        )

    else:

        longest = 0
        average = 0

    m1, m2, m3, m4 = (
        st.columns(4)
    )

    with m1:

        metric_card(
            "Patients waiting",
            total_patients,
            "patients",
            tone="blue",
        )

    with m2:

        metric_card(
            "Pending examinations",
            total_exams,
            "examinations",
            tone="amber",
        )

    with m3:

        metric_card(
            "X-Ray requests",
            xray_count,
            "pending",
            tone="blue",
        )

    with m4:

        metric_card(
            "Longest wait",
            format_waiting(
                longest
            ),
            "waiting",
            tone="red",
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
            f"physician_queue_table_"
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
                (
                    f"{key_prefix}_"
                    f"row_{patient_id}"
                ),
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
                    icon=(
                        ":material/"
                        "folder_open:"
                    ),
                    width="stretch",
                ):

                    clear_queue_dialog_state()

                    st.session_state[
                        "history_patient"
                    ] = patient

                    st.rerun()

                if len(
                    examinations
                ) == 1:

                    if columns[4].button(
                        "Examine",
                        key=(
                            f"{key_prefix}_"
                            f"examine_{patient_id}"
                        ),
                        icon=(
                            ":material/"
                            "clinical_notes:"
                        ),
                        type="primary",
                        width="stretch",
                    ):

                        clear_queue_dialog_state()

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
                        icon=(
                            ":material/list:"
                        ),
                        type="primary",
                        width="stretch",
                    ):

                        clear_queue_dialog_state()

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
            f"physician_xray_table_"
            f"{key_prefix}"
        )
    ):

        table_header(
            XRAY_QUEUE_HEADERS,
            XRAY_QUEUE_WIDTHS,
            key_prefix,
        )

        for request in xray_requests:

            # ------------------------------------------------
            # PATIENT
            # ------------------------------------------------

            patient = (
                request.get(
                    "patients"
                )
                or {}
            )

            patient_id = patient.get(
                "patient_id"
            )

            # ------------------------------------------------
            # X-RAY REQUEST
            # ------------------------------------------------

            request_id = request.get(
                "request_id"
            )

            # ------------------------------------------------
            # REQUESTED TIME
            # ------------------------------------------------

            requested_at = (
                xray_request_datetime(
                    request
                )
            )

            waiting = waiting_minutes(
                requested_at
            )

            # ------------------------------------------------
            # TABLE ROW
            # ------------------------------------------------

            with table_row(
                (
                    f"{key_prefix}_"
                    f"row_{request_id}"
                ),
                XRAY_QUEUE_WIDTHS,
            ) as columns:

                # --------------------------------------------
                # PATIENT NAME
                # --------------------------------------------

                name_cell(
                    columns[0],
                    patient_name(
                        patient
                    ),
                    sub=patient_code(
                        patient
                    ),
                )

                # --------------------------------------------
                # WAITING TIME
                # --------------------------------------------

                pill_cell(
                    columns[1],
                    format_waiting(
                        waiting
                    ),
                    waiting_tone(
                        waiting
                    ),
                )

                # --------------------------------------------
                # REQUESTED AT
                # --------------------------------------------

                text_cell(
                    columns[2],
                    format_datetime(
                        requested_at
                    ),
                )

                # --------------------------------------------
                # STATUS
                # --------------------------------------------

                pill_cell(
                    columns[3],
                    "Pending",
                    "amber",
                )

                # --------------------------------------------
                # VIEW
                # --------------------------------------------

                if columns[4].button(
                    "View",
                    key=(
                        f"{key_prefix}_"
                        f"view_{request_id}"
                    ),
                    icon=(
                        ":material/visibility:"
                    ),
                    width="stretch",
                ):

                    clear_queue_dialog_state()

                    st.session_state[
                        "xray_request_patient"
                    ] = request

                    st.rerun()


# ============================================================
# MULTIPLE EXAMINATIONS
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
        key=(
            "physician_pending_"
            "exams_dialog"
        )
    ):

        show_rows([
            (
                "Patient",
                patient_name(
                    patient
                ),
            ),
            (
                "Patient ID",
                patient_code(
                    patient
                ),
            ),
        ])

        section_title(
            f"{len(examinations)} "
            "Examination(s)"
        )

        for examination in sorted(
            examinations,
            key=lambda item: (
                item.get(
                    "created_at"
                )
                or ""
            ),
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
                f"{pill(
                    format_waiting(
                        waiting
                    ),
                    waiting_tone(
                        waiting
                    )
                )}",
                unsafe_allow_html=True,
            )

            if st.button(
                "Examine Patient",
                key=(
                    "open_pending_exam_"
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
            key=(
                "pending_exams_close"
            ),
            width="stretch",
        ):

            st.session_state.pop(
                "pending_exams_patient",
                None,
            )

            st.rerun()


# ============================================================
# PAGE
# ============================================================

def show():

    # --------------------------------------------------------
    # PHYSICIAN PAGE CSS
    # --------------------------------------------------------

    load_css(
        "patient_queue.css"
    )

    show_flash_message()

    role_id = current_role_id()

    hospital_id = (
        current_hospital_id()
    )

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
            "the patient queue."
        )

        return

    # --------------------------------------------------------
    # PAGE
    # --------------------------------------------------------

    with st.container(
        key="physician_patient_queue_page"
    ):

        page_header(
            "Patient Queue",
            (
                "Review patients awaiting physician "
                "examination and monitor your pending "
                "X-Ray requests."
            ),
        )

        if st.button(
            "Refresh",
            icon=":material/refresh:",
            key=(
                "physician_queue_refresh"
            ),
            width="stretch",
        ):

            st.rerun()

        # ----------------------------------------------------
        # LOAD EXAMINATIONS
        # ----------------------------------------------------

        try:

            pending = (
                get_pending_examinations(
                    hospital_id=filter_hospital
                )
            )

        except Exception as error:

            st.error(
                "Failed to load patient queue: "
                f"{error}"
            )

            pending = []

        # ----------------------------------------------------
        # SPLIT QUEUES
        # ----------------------------------------------------

        # ----------------------------------------------------
        # PHYSICIAN PENDING EXAMINATIONS
        # ----------------------------------------------------

        # get_pending_examinations() already filters:
        #
        #     examinations.status = "Pending"
        #
        # Therefore, this list is used for the normal
        # pending examination queue.

        physician_pending = pending


        # ----------------------------------------------------
        # PENDING X-RAY REQUESTS
        # ----------------------------------------------------

        # X-Ray requests are stored in the separate
        # xray_requests table.
        #
        # Do NOT derive these from `pending`, because
        # `pending` only contains examinations whose
        # status is "Pending".

        try:

            xray_requests = get_pending_xray_requests(
                hospital_id=filter_hospital
            )

        except Exception as error:

            st.error(
                f"Failed to load X-Ray requests: {error}"
            )

            xray_requests = []


        # ----------------------------------------------------
        # PER-PHYSICIAN X-RAY FILTER
        # ----------------------------------------------------

        # Physicians only see requests they created.
        #
        # Hospital administrators / Super Admin can see
        # all pending X-Ray requests for the hospital.

        if role_id in DOCTOR_ROLES:

            user_id = current_user_id()

            xray_requests = [
                request
                for request in xray_requests
                if str(
                    request.get("requested_by")
                ) == str(user_id)
            ]


        # ----------------------------------------------------
        # GROUP NORMAL PENDING EXAMINATIONS
        # ----------------------------------------------------

        grouped = group_pending_by_patient(
            physician_pending
        )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        render_metrics(
            grouped,
            xray_requests,
        )

        st.divider()

        # ====================================================
        # SECTION 1
        # ====================================================

        section_title(
            "Patients Awaiting Physician Review"
        )

        st.caption(
            "Patients who currently have an examination "
            "waiting for physician review."
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
            "View-only list of Chest X-Ray requests "
            "you have made. These requests remain here "
            "until the X-Ray workflow is completed."
        )

        render_xray_request_table(
            xray_requests,
            key_prefix="xray",
        )

    # ========================================================
    # DIALOGS
    # ========================================================

    if st.session_state.get(
        "selected_examination"
    ):

        examination = (
            st.session_state[
                "selected_examination"
            ]
        )

        patient = (
            st.session_state.get(
                "edit_patient"
            )
        )

        if patient:

            show_complete_exam_dialog(
                patient,
                examination,
            )

    elif st.session_state.get(
        "pending_exams_patient"
    ):

        data = (
            st.session_state[
                "pending_exams_patient"
            ]
        )

        show_pending_exams_dialog(
            data["patient"],
            data["exams"],
        )

    elif st.session_state.get(
        "xray_request_patient"
    ):

        show_xray_request_dialog(
            st.session_state[
                "xray_request_patient"
            ]
        )

    elif st.session_state.get(
        "history_patient"
    ):

        show_patient_history_dialog(
            st.session_state[
                "history_patient"
            ]
        )

    elif st.session_state.get(
        "previous_examinations_patient"
    ):

        show_previous_examinations_dialog(
            st.session_state[
                "previous_examinations_patient"
            ]
        )

    elif st.session_state.get(
        "previous_medical_records_patient"
    ):

        show_previous_medical_records_dialog(
            st.session_state[
                "previous_medical_records_patient"
            ]
        )