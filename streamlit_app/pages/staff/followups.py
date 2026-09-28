import streamlit as st

from backend.backend_utils.followup_utils import (
    get_patients_with_follow_ups,
    get_upcoming_follow_ups_by_patient,
    get_follow_up_history,
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
    show_flash_message,
)


# ============================================================
# CONFIG
# ============================================================

ROLE_SUPERADMIN = 1
ROLE_STAFF = 7
ROLE_HOSPITAL_ADMIN = 6


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

                return (
                    f"{formatted_date} at "
                    f"{time_text}"
                )

        return formatted_date

    except Exception:

        return str(date_value)


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

    st.session_state.pop(
        "staff_selected_follow_up_patient",
        None,
    )

    st.session_state.pop(
        "staff_selected_follow_up_patient_id",
        None,
    )


def select_patient(
    patient,
):

    st.session_state[
        "staff_selected_follow_up_patient"
    ] = patient

    st.session_state[
        "staff_selected_follow_up_patient_id"
    ] = patient.get(
        "patient_id"
    )

    st.rerun()


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
        "Select a patient to view their follow-up schedules and history."
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
                key=f"staff_followup_patient_{patient_id}",
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
        key="staff_followups_back",
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
            "No upcoming follow-ups."
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
                    f"**Notes:** "
                    f"{follow_up.get('notes') or '—'}"
                )

                if examination:

                    st.caption(
                        "Related examination: "
                        f"{examination.get('examination_type') or '—'}"
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
):

    total = len(
        patients
    )

    metric_card(
        "Patients With Follow-Ups",
        total,
        "event",
        tone="blue",
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
        ROLE_STAFF,
        ROLE_HOSPITAL_ADMIN,
        ROLE_SUPERADMIN,
    ):

        st.error(
            "You don't have access to Follow Ups."
        )

        return

    page_header(
        "Follow Ups",
        "View patient follow-up schedules and follow-up history.",
    )

    if st.button(
        "Refresh",
        icon=":material/refresh:",
        key="staff_followups_refresh",
        width="stretch",
    ):

        st.rerun()

    patients = (
        get_patients_with_follow_ups(
            hospital_id=(
                None
                if role_id == ROLE_SUPERADMIN
                else hospital_id
            )
        )
    )

    render_metrics(
        patients
    )

    selected_patient = (
        st.session_state.get(
            "staff_selected_follow_up_patient"
        )
    )

    selected_patient_id = (
        st.session_state.get(
            "staff_selected_follow_up_patient_id"
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