import streamlit as st
import pathlib as Path

from backend.backend_utils.followup_utils import (
    get_patients_with_follow_ups,
    get_patients_with_upcoming_follow_ups,
    get_upcoming_follow_ups_by_patient,
    get_follow_up_history,
    update_follow_up_status,
    reschedule_follow_up,
    cancel_follow_up,
    complete_follow_up,
)

from streamlit_app.components.ui import (
    load_css,
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    pill,
    metric_card,
    remember,
    show_flash_message,
)


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_HOSPITAL_ADMIN = 6

DOCTOR_ROLES = [
    ROLE_RADIOLOGIST,
]

ADMIN_ROLES = [
    ROLE_SUPERADMIN,
    ROLE_HOSPITAL_ADMIN,
]


# ============================================================
# USER HELPERS
# ============================================================

def current_user():

    return (
        st.session_state.get("user")
        or {}
    )


def current_role_id():

    return current_user().get(
        "role_id"
    )


def current_hospital_id():

    return current_user().get(
        "hospital_id"
    )


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
# DATE / TIME
# ============================================================

def format_datetime(
    date_value,
    time_value=None,
):

    if not date_value:

        return "—"

    try:

        from datetime import datetime

        date_text = str(
            date_value
        )

        if date_text.endswith("Z"):

            date_text = date_text.replace(
                "Z",
                "+00:00",
            )

        if "T" in date_text:

            dt = datetime.fromisoformat(
                date_text
            )

            if dt.tzinfo is not None:

                dt = dt.astimezone()

            return dt.strftime(
                "%B %d, %Y at %I:%M %p"
            )

        date_obj = datetime.strptime(
            date_text,
            "%Y-%m-%d",
        )

        formatted_date = date_obj.strftime(
            "%B %d, %Y"
        )

        if time_value:

            time_text = str(
                time_value
            )

            try:

                time_obj = datetime.strptime(
                    time_text[:8],
                    "%H:%M:%S",
                )

                return (
                    f"{formatted_date} at "
                    f"{time_obj.strftime('%I:%M %p')}"
                )

            except Exception:

                try:

                    time_obj = datetime.strptime(
                        time_text[:5],
                        "%H:%M",
                    )

                    return (
                        f"{formatted_date} at "
                        f"{time_obj.strftime('%I:%M %p')}"
                    )

                except Exception:

                    return (
                        f"{formatted_date} at "
                        f"{time_text}"
                    )

        return formatted_date

    except Exception:

        if time_value:

            return (
                f"{date_value} at "
                f"{time_value}"
            )

        return str(
            date_value
        )


def follow_up_datetime(
    follow_up,
):

    return format_datetime(
        follow_up.get(
            "follow_up_date"
        ),
        follow_up.get(
            "follow_up_time"
        ),
    )


# ============================================================
# STATUS
# ============================================================

def status_tone(
    status,
):

    normalized = (
        str(status or "")
        .strip()
        .lower()
    )

    if normalized == "scheduled":

        return "blue"

    if normalized == "completed":

        return "green"

    if normalized == "missed":

        return "red"

    if normalized == "cancelled":

        return "red"

    if normalized == "rescheduled":

        return "amber"

    return "gray"


# ============================================================
# STATE
# ============================================================

def clear_follow_up_state():

    for key in (
        "selected_follow_up_patient",
        "selected_follow_up_patient_id",
        "follow_up_action",
        "follow_up_action_id",
    ):

        st.session_state.pop(
            key,
            None,
        )


def select_patient(
    patient,
):

    st.session_state[
        "selected_follow_up_patient"
    ] = patient

    st.session_state[
        "selected_follow_up_patient_id"
    ] = patient.get(
        "patient_id"
    )

    st.rerun()


# ============================================================
# FOLLOW-UP ACTION DIALOG
# ============================================================

@st.dialog(
    "Follow-Up",
    width="medium",
)
def show_follow_up_action_dialog(
    follow_up,
    patient,
):

    follow_up_id = follow_up.get(
        "follow_up_id"
    )

    status = (
        follow_up.get("status")
        or "Scheduled"
    )

    section_title(
        "Follow-Up Details"
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
            "Schedule",
            follow_up_datetime(
                follow_up
            ),
        ),
        (
            "Status",
            pill(
                status,
                status_tone(status),
            ),
        ),
    ])

    st.divider()

    examination = (
        follow_up.get(
            "examinations"
        )
        or {}
    )

    if examination:

        section_title(
            "Related Examination"
        )

        show_rows([
            (
                "Examination",
                examination.get(
                    "examination_type"
                )
                or "—",
            ),
            (
                "Examination Date",
                format_datetime(
                    examination.get(
                        "examination_date"
                    )
                ),
            ),
            (
                "Diagnosis",
                examination.get(
                    "diagnosis"
                )
                or "—",
            ),
        ])

        st.divider()

    current_notes = (
        follow_up.get(
            "notes"
        )
        or ""
    )

    notes = st.text_area(
        "Follow-Up Notes",
        value=current_notes,
        height=120,
        key=(
            f"physician_followup_notes_"
            f"{follow_up_id}"
        ),
    )

    st.divider()

    # ========================================================
    # COMPLETED
    # ========================================================

    if status == "Completed":

        st.success(
            "This follow-up has already been completed."
        )

        if st.button(
            "Close",
            key=(
                f"physician_followup_close_"
                f"completed_{follow_up_id}"
            ),
            width="stretch",
        ):

            st.rerun()

        return

    # ========================================================
    # COMPLETE / MISSED
    # ========================================================

    if status in (
        "Scheduled",
        "Rescheduled",
    ):

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "Mark Completed",
                key=(
                    f"physician_complete_"
                    f"{follow_up_id}"
                ),
                type="primary",
                width="stretch",
            ):

                result = complete_follow_up(
                    follow_up_id,
                    notes=(
                        notes.strip()
                        or None
                    ),
                )

                if result.get("success"):

                    remember(
                        "Follow-up marked as completed."
                    )

                    st.rerun()

                else:

                    st.error(
                        result.get(
                            "message",
                            "Failed to complete follow-up.",
                        )
                    )

        with col2:

            if st.button(
                "Mark Missed",
                key=(
                    f"physician_missed_"
                    f"{follow_up_id}"
                ),
                width="stretch",
            ):

                result = update_follow_up_status(
                    follow_up_id,
                    "Missed",
                )

                if result.get("success"):

                    remember(
                        "Follow-up marked as missed."
                    )

                    st.rerun()

                else:

                    st.error(
                        result.get(
                            "message",
                            "Failed to update follow-up.",
                        )
                    )

    # ========================================================
    # RESCHEDULE
    # ========================================================

    if status not in (
        "Completed",
        "Cancelled",
    ):

        st.divider()

        section_title(
            "Reschedule"
        )

        new_date = st.date_input(
            "New Follow-Up Date",
            key=(
                f"physician_reschedule_date_"
                f"{follow_up_id}"
            ),
        )

        new_time = st.time_input(
            "New Follow-Up Time",
            key=(
                f"physician_reschedule_time_"
                f"{follow_up_id}"
            ),
        )

        if st.button(
            "Reschedule Follow-Up",
            key=(
                f"physician_reschedule_"
                f"{follow_up_id}"
            ),
            width="stretch",
        ):

            result = reschedule_follow_up(
                follow_up_id,
                new_date,
                new_time.strftime(
                    "%H:%M:%S"
                ),
                notes.strip() or None,
            )

            if result.get("success"):

                remember(
                    "Follow-up rescheduled successfully."
                )

                st.rerun()

            else:

                st.error(
                    result.get(
                        "message",
                        "Failed to reschedule follow-up.",
                    )
                )

    # ========================================================
    # CANCEL
    # ========================================================

    if status not in (
        "Completed",
        "Cancelled",
    ):

        st.divider()

        if st.button(
            "Cancel Follow-Up",
            key=(
                f"physician_cancel_"
                f"{follow_up_id}"
            ),
            width="stretch",
        ):

            result = cancel_follow_up(
                follow_up_id
            )

            if result.get("success"):

                remember(
                    "Follow-up cancelled."
                )

                st.rerun()

            else:

                st.error(
                    result.get(
                        "message",
                        "Failed to cancel follow-up.",
                    )
                )


# ============================================================
# PATIENT LIST
# ============================================================

def render_patient_list(
    patients,
    selected_patient_id=None,
):

    if not patients:

        empty_state(
            "No patients currently have follow-up schedules."
        )

        return

    section_title(
        "Patients With Follow-Ups"
    )

    st.caption(
        "Select a patient to view their follow-up schedule and history."
    )

    for patient in patients:

        patient_id = patient.get(
            "patient_id"
        )

        is_selected = (
            patient_id
            == selected_patient_id
        )

        col1, col2 = st.columns(
            [4, 1]
        )

        with col1:

            st.markdown(
                f"**{patient_name(patient)}**"
            )

            st.caption(
                patient_code(patient)
            )

        with col2:

            if st.button(
                "Selected"
                if is_selected
                else "View",
                key=(
                    f"physician_patient_"
                    f"{patient_id}"
                ),
                type=(
                    "primary"
                    if is_selected
                    else "secondary"
                ),
                width="stretch",
            ):

                select_patient(
                    patient
                )

        st.divider()


# ============================================================
# PATIENT FOLLOW-UP VIEW
# ============================================================

def render_patient_followups(
    patient,
):

    patient_id = patient.get(
        "patient_id"
    )

    st.divider()

    section_title(
        f"Follow-Ups — {patient_name(patient)}"
    )

    st.caption(
        f"Patient ID: {patient_code(patient)}"
    )

    if st.button(
        "Back to Patients",
        icon=":material/arrow_back:",
        key="physician_followups_back",
    ):

        clear_follow_up_state()

        st.rerun()

    # ========================================================
    # UPCOMING
    # ========================================================

    upcoming = (
        get_upcoming_follow_ups_by_patient(
            patient_id
        )
    )

    section_title(
        f"Upcoming Follow-Ups ({len(upcoming)})"
    )

    if not upcoming:

        st.info(
            "This patient has no upcoming follow-ups."
        )

    else:

        for follow_up in upcoming:

            status = (
                follow_up.get(
                    "status"
                )
                or "Scheduled"
            )

            examination = (
                follow_up.get(
                    "examinations"
                )
                or {}
            )

            with st.container(
                border=True
            ):

                col1, col2 = st.columns(
                    [4, 1]
                )

                with col1:

                    st.markdown(
                        f"### "
                        f"{follow_up_datetime(follow_up)}"
                    )

                    st.markdown(
                        f"**Status:** "
                        f"{pill(
                            status,
                            status_tone(status),
                        )}",
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        f"**Reason / Notes:** "
                        f"{follow_up.get('notes') or '—'}"
                    )

                    if examination:

                        st.caption(
                            "Related examination: "
                            f"{examination.get('examination_type') or '—'}"
                        )

                with col2:

                    if st.button(
                        "Manage",
                        key=(
                            f"physician_manage_"
                            f"{follow_up['follow_up_id']}"
                        ),
                        type="primary",
                        width="stretch",
                    ):

                        show_follow_up_action_dialog(
                            follow_up,
                            patient,
                        )

    # ========================================================
    # HISTORY
    # ========================================================

    st.divider()

    history = (
        get_follow_up_history(
            patient_id
        )
    )

    section_title(
        f"Follow-Up History ({len(history)})"
    )

    if not history:

        st.info(
            "No previous follow-up history found."
        )

    else:

        for follow_up in history:

            status = (
                follow_up.get(
                    "status"
                )
                or "Unknown"
            )

            examination = (
                follow_up.get(
                    "examinations"
                )
                or {}
            )

            with st.container(
                border=True
            ):

                st.markdown(
                    f"**{follow_up_datetime(follow_up)}**"
                )

                st.markdown(
                    f"**Status:** "
                    f"{pill(
                        status,
                        status_tone(status),
                    )}",
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"**Notes:** "
                    f"{follow_up.get('notes') or '—'}"
                )

                if examination:

                    st.caption(
                        "Related examination: "
                        f"{examination.get('examination_type') or '—'}"
                    )


# ============================================================
# METRICS
# ============================================================

def render_metrics(
    patients,
    upcoming_patients,
):

    total_patients = len(
        patients
    )

    upcoming_total = len(
        upcoming_patients
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        metric_card(
            "Patients With Follow-Ups",
            total_patients,
            "event",
            tone="blue",
        )

    with col2:

        metric_card(
            "Patients With Upcoming Follow-Ups",
            upcoming_total,
            "event_repeat",
            tone="red",
        )

    with col3:

        metric_card(
            "Scheduled Follow-Ups",
            upcoming_total,
            "calendar_month",
            tone="green",
        )


# ============================================================
# PAGE
# ============================================================

def show():

    load_css(
        "manage_examinations.css"
    )

    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    if role_id not in (
        DOCTOR_ROLES
        + ADMIN_ROLES
    ):

        st.error(
            "You don't have access to Follow Ups."
        )

        return

    page_header(
        "Follow Ups",
        "Monitor patient follow-up schedules and follow-up history.",
    )

    if st.button(
        "Refresh",
        icon=":material/refresh:",
        key="physician_followups_refresh",
        width="stretch",
    ):

        st.rerun()

    # ========================================================
    # LOAD PATIENTS
    # ========================================================

    effective_hospital_id = (
        None
        if role_id == ROLE_SUPERADMIN
        else hospital_id
    )

    patients = (
        get_patients_with_follow_ups(
            hospital_id=effective_hospital_id
        )
    )

    upcoming_patients = (
        get_patients_with_upcoming_follow_ups(
            hospital_id=effective_hospital_id
        )
    )

    # ========================================================
    # METRICS
    # ========================================================

    render_metrics(
        patients,
        upcoming_patients,
    )

    # ========================================================
    # SELECTED PATIENT
    # ========================================================

    selected_patient = (
        st.session_state.get(
            "selected_follow_up_patient"
        )
    )

    selected_patient_id = (
        st.session_state.get(
            "selected_follow_up_patient_id"
        )
    )

    if selected_patient:

        render_patient_followups(
            selected_patient
        )

    else:

        st.divider()

        render_patient_list(
            patients,
            selected_patient_id,
        )