import streamlit as st

from datetime import date, datetime, time

from backend.backend_utils.followup_utils import (
    get_patients_with_follow_ups,
    get_patients_with_upcoming_follow_ups,
    get_upcoming_follow_ups_by_patient,
    get_follow_up_history,
    get_follow_up_counts,
    get_follow_up,
    update_follow_up_status,
    reschedule_follow_up,
    cancel_follow_up,
    complete_follow_up,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    format_date,
    pill,
    remember,
    show_flash_message,
    kpi_strip,
    patient_summary_card,
    follow_up_entry_header,
)

from shared.assets import load_css



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


ACTIVE_FOLLOW_UP_STATUSES = [
    "Scheduled",
    "Rescheduled",
]


# ============================================================
# USER HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


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
# EXAMINATION HELPERS
# ============================================================

def source_examination(follow_up):
    """
    Return the original examination that created
    the follow-up.
    """

    examination = (
        follow_up.get("source_examination")
        or {}
    )

    if isinstance(examination, list):
        return examination[0] if examination else {}

    return examination


def follow_up_examination(follow_up):
    """
    Return the new examination performed during
    the actual follow-up visit.
    """

    examination = (
        follow_up.get("follow_up_examination")
        or {}
    )

    if isinstance(examination, list):
        return examination[0] if examination else {}

    return examination


def get_follow_up_id(follow_up):
    return (
        follow_up.get("follow_up_id")
        or follow_up.get("id")
    )


def get_follow_up_status(follow_up):
    return follow_up.get("status") or "Scheduled"


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
        date_text = str(date_value)

        if date_text.endswith("Z"):
            date_text = date_text.replace("Z", "+00:00")

        if "T" in date_text:
            dt = datetime.fromisoformat(date_text)

            if dt.tzinfo is not None:
                dt = dt.astimezone()

            return dt.strftime("%B %d, %Y at %I:%M %p")

        date_obj = datetime.strptime(date_text, "%Y-%m-%d")

        formatted_date = date_obj.strftime("%B %d, %Y")

        if time_value:
            time_text = str(time_value)

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
                    return f"{formatted_date} at {time_text}"

        return formatted_date

    except Exception:
        if time_value:
            return f"{date_value} at {time_value}"

        return str(date_value)


def follow_up_datetime(follow_up):
    return format_datetime(
        follow_up.get("follow_up_date"),
        follow_up.get("follow_up_time"),
    )


# ============================================================
# STATUS
# ============================================================

def status_tone(status):
    normalized = str(status or "").strip().lower()

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

    return "grey"


# ============================================================
# STATE
# ============================================================

def clear_follow_up_state():
    for key in (
        "selected_follow_up_patient",
        "selected_follow_up_patient_id",
        "follow_up_action_id",
        "reschedule_follow_up_id",
        "cancel_follow_up_id",
        "missed_follow_up_id",
    ):
        st.session_state.pop(key, None)


def select_patient(patient):
    st.session_state["selected_follow_up_patient"] = patient
    st.session_state["selected_follow_up_patient_id"] = patient.get(
        "patient_id"
    )
    st.rerun()


# ============================================================
# CARDS
# ============================================================

def render_source_examination(follow_up):
    examination = source_examination(follow_up)

    if not examination:
        st.info("No source examination is linked to this follow-up.")
        return

    section_title("Source Examination")

    show_rows([
        (
            "Examination",
            examination.get("examination_type") or "—",
        ),
        (
            "Examination Date",
            format_datetime(examination.get("examination_date")),
        ),
        (
            "Diagnosis",
            examination.get("diagnosis") or "—",
        ),
        (
            "Status",
            examination.get("status") or "—",
        ),
    ])


def render_follow_up_examination(follow_up):
    examination = follow_up_examination(follow_up)

    section_title("Follow-Up Examination")

    if not examination:
        st.info(
            "No follow-up examination has been linked yet. "
            "The patient has not yet been seen for this "
            "follow-up visit."
        )
        return

    show_rows([
        (
            "Examination",
            examination.get("examination_type") or "—",
        ),
        (
            "Examination Date",
            format_datetime(examination.get("examination_date")),
        ),
        (
            "Diagnosis",
            examination.get("diagnosis") or "—",
        ),
        (
            "Status",
            examination.get("status") or "—",
        ),
    ])


# ============================================================
# ACTION DIALOGS
# ============================================================

@st.dialog("Reschedule Follow-Up", width="medium")
def show_reschedule_dialog(follow_up):
    follow_up_id = get_follow_up_id(follow_up)

    # --------------------------------------------------------
    # DEFAULT DATE
    # --------------------------------------------------------

    default_date = follow_up.get("follow_up_date")

    if isinstance(default_date, str):
        try:
            default_date = date.fromisoformat(default_date[:10])
        except Exception:
            default_date = date.today()

    if not isinstance(default_date, date):
        default_date = date.today()

    if default_date < date.today():
        default_date = date.today()

    # --------------------------------------------------------
    # DEFAULT TIME
    # --------------------------------------------------------

    default_time = follow_up.get("follow_up_time")

    if isinstance(default_time, str):
        try:
            default_time = time.fromisoformat(default_time[:8])
        except Exception:
            default_time = time(9, 0)

    if not isinstance(default_time, time):
        default_time = time(9, 0)

    # --------------------------------------------------------
    # FORM
    # --------------------------------------------------------

    section_title("New Schedule")

    st.caption(
        "Choose a new date and time for this patient's "
        "follow-up visit."
    )

    new_date = st.date_input(
        "New Follow-Up Date",
        value=default_date,
        min_value=date.today(),
        key=f"physician_reschedule_date_{follow_up_id}",
    )

    new_time = st.time_input(
        "New Follow-Up Time",
        value=default_time,
        key=f"physician_reschedule_time_{follow_up_id}",
    )

    st.divider()

    col1, col2 = st.columns(2)

    if col1.button(
        "Cancel",
        key=f"physician_reschedule_cancel_{follow_up_id}",
        width="stretch",
    ):
        st.session_state.pop("reschedule_follow_up_id", None)
        st.session_state.pop("selected_follow_up_patient", None)
        st.rerun()

    if col2.button(
        "Save Schedule",
        key=f"physician_reschedule_save_{follow_up_id}",
        type="primary",
        width="stretch",
    ):
        result = reschedule_follow_up(
            follow_up_id,
            new_date,
            new_time.strftime("%H:%M:%S"),
        )

        if result.get("success"):
            st.session_state.pop("reschedule_follow_up_id", None)
            remember("Follow-up rescheduled successfully.")
            st.rerun()
        else:
            st.error(
                result.get(
                    "message",
                    "Failed to reschedule follow-up.",
                )
            )


@st.dialog("Cancel Follow-Up", width="small")
def show_cancel_dialog(follow_up):
    follow_up_id = get_follow_up_id(follow_up)

    patient = follow_up.get("patients") or {}

    st.warning(
        "Cancel this follow-up? This cannot be undone "
        "from here, but a new follow-up can be scheduled "
        "from the Patient Queue."
    )

    show_rows([
        ("Patient", patient_name(patient)),
        ("Scheduled", follow_up_datetime(follow_up)),
    ])

    st.divider()

    col1, col2 = st.columns(2)

    if col1.button(
        "Keep Follow-Up",
        key=f"physician_cancel_keep_{follow_up_id}",
        width="stretch",
    ):
        st.session_state.pop("cancel_follow_up_id", None)
        st.rerun()

    if col2.button(
        "Yes, Cancel",
        key=f"physician_cancel_confirm_{follow_up_id}",
        type="primary",
        width="stretch",
    ):
        result = cancel_follow_up(follow_up_id)

        if result.get("success"):
            st.session_state.pop("cancel_follow_up_id", None)
            remember("Follow-up cancelled.")
            st.rerun()
        else:
            st.error(
                result.get(
                    "message",
                    "Failed to cancel follow-up.",
                )
            )


@st.dialog("Mark Follow-Up Missed", width="small")
def show_missed_dialog(follow_up):
    follow_up_id = get_follow_up_id(follow_up)

    patient = follow_up.get("patients") or {}

    st.warning(
        "Mark this follow-up as missed? Use this when "
        "the patient did not arrive for their scheduled "
        "visit."
    )

    show_rows([
        ("Patient", patient_name(patient)),
        ("Scheduled", follow_up_datetime(follow_up)),
    ])

    st.divider()

    col1, col2 = st.columns(2)

    if col1.button(
        "Cancel",
        key=f"physician_missed_cancel_{follow_up_id}",
        width="stretch",
    ):
        st.session_state.pop("missed_follow_up_id", None)
        st.rerun()

    if col2.button(
        "Mark Missed",
        key=f"physician_missed_confirm_{follow_up_id}",
        type="primary",
        width="stretch",
    ):
        result = update_follow_up_status(follow_up_id, "Missed")

        if result.get("success"):
            st.session_state.pop("missed_follow_up_id", None)
            remember("Follow-up marked as missed.")
            st.rerun()
        else:
            st.error(
                result.get(
                    "message",
                    "Failed to update follow-up.",
                )
            )


# ============================================================
# FOLLOW-UP ACTION DIALOG (MANAGE)
# ============================================================

@st.dialog("Follow-Up Details", width="medium")
def show_follow_up_action_dialog(follow_up, patient):

    follow_up_id = get_follow_up_id(follow_up)
    status = get_follow_up_status(follow_up)

    linked_exam = follow_up_examination(follow_up)
    linked_status = (
        linked_exam.get("status") if linked_exam else None
    )
    exam_completed = (linked_status == "Completed")

    is_active = status in ACTIVE_FOLLOW_UP_STATUSES

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    section_title("Follow-Up Details")

    show_rows([
        ("Patient", patient_name(patient)),
        ("Patient ID", patient_code(patient)),
        ("Schedule", follow_up_datetime(follow_up)),
        (
            "Status",
            pill(status, status_tone(status)),
        ),
    ])

    st.divider()

    # --------------------------------------------------------
    # SOURCE + FOLLOW-UP EXAMINATION
    # --------------------------------------------------------

    render_source_examination(follow_up)

    st.divider()

    render_follow_up_examination(follow_up)

    st.divider()

    # --------------------------------------------------------
    # NOTES (read-only here — edits belong in the queue)
    # --------------------------------------------------------

    notes = (
        follow_up.get("notes")
        or follow_up.get("follow_up_notes")
        or ""
    )

    if notes:
        section_title("Notes")
        st.write(notes)
        st.divider()

    # --------------------------------------------------------
    # STATE MESSAGES
    # --------------------------------------------------------

    if status == "Completed":
        st.success("This follow-up has already been completed.")

        if st.button(
            "Close",
            key=f"physician_followup_close_completed_{follow_up_id}",
            width="stretch",
        ):
            st.session_state.pop("selected_follow_up_patient", None)
            st.rerun()

        return

    if status == "Cancelled":
        st.warning("This follow-up has been cancelled.")

        if st.button(
            "Close",
            key=f"physician_followup_close_cancelled_{follow_up_id}",
            width="stretch",
        ):
            st.session_state.pop("selected_follow_up_patient", None)
            st.rerun()

        return

    if status == "Missed":
        st.warning("This follow-up was marked as missed.")

        if st.button(
            "Close",
            key=f"physician_followup_close_missed_{follow_up_id}",
            width="stretch",
        ):
            st.session_state.pop("selected_follow_up_patient", None)
            st.rerun()

        return

    # --------------------------------------------------------
    # LINKED EXAMINATION HINT
    # --------------------------------------------------------

    if is_active and not linked_exam:
        st.info(
            "The patient has not yet been seen for this "
            "follow-up. Start the examination from the "
            "**Patient Queue** when they arrive."
        )

    elif is_active and linked_status == "Pending":
        st.info(
            "The follow-up examination is still in the "
            "**Patient Queue**, waiting for physician review."
        )

    # --------------------------------------------------------
    # ACTIONS
    # --------------------------------------------------------

    st.divider()

    # --------------------------------------------------------
    # MARK COMPLETED (manual correction only)
    # Only when the linked exam is already Completed.
    # --------------------------------------------------------

    if is_active and exam_completed:

        st.success(
            "The examination has been completed. "
            "You may formally close this follow-up."
        )

        if st.button(
            "Mark Follow-Up Completed",
            key=f"physician_complete_{follow_up_id}",
            type="primary",
            width="stretch",
        ):
            result = complete_follow_up(follow_up_id)

            if result.get("success"):
                remember("Follow-up marked as completed.")
                st.rerun()
            else:
                st.error(
                    result.get(
                        "message",
                        "Failed to complete follow-up.",
                    )
                )

    # --------------------------------------------------------
    # MARK MISSED
    # Only while the patient hasn't been seen (no linked exam)
    # --------------------------------------------------------

    if is_active and not linked_exam:

        if st.button(
            "Mark Follow-Up Missed",
            key=f"physician_open_missed_{follow_up_id}",
            width="stretch",
        ):
            st.session_state["missed_follow_up_id"] = follow_up_id
            st.rerun()

    # --------------------------------------------------------
    # RESCHEDULE / CANCEL
    # Only while the exam is NOT completed.
    # --------------------------------------------------------

    if is_active and not exam_completed:

        st.divider()

        col1, col2 = st.columns(2)

        if col1.button(
            "Reschedule",
            key=f"physician_open_reschedule_{follow_up_id}",
            width="stretch",
        ):
            st.session_state["reschedule_follow_up_id"] = follow_up_id
            st.rerun()

        if col2.button(
            "Cancel Follow-Up",
            key=f"physician_open_cancel_{follow_up_id}",
            width="stretch",
        ):
            st.session_state["cancel_follow_up_id"] = follow_up_id
            st.rerun()

    # --------------------------------------------------------
    # CLOSE
    # --------------------------------------------------------

    st.divider()

    if st.button(
        "Close",
        key=f"physician_followup_close_{follow_up_id}",
        width="stretch",
    ):
        st.session_state.pop("selected_follow_up_patient", None)
        st.rerun()


# ============================================================
# PATIENT LIST
# ============================================================

def render_patient_list(patients, selected_patient_id=None):

    if not patients:
        empty_state("No patients currently have follow-up schedules.")
        return

    section_title("Patients With Follow-Ups")

    st.caption(
        "Select a patient to open their follow-up file — "
        "upcoming visits, past outcomes, and linked "
        "examinations."
    )

    for patient in patients:

        patient_id = patient.get("patient_id")
        is_selected = (patient_id == selected_patient_id)

        with st.container(
            key=f"physician_patient_list_{patient_id}"
        ):

            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(
                    f"**{patient_name(patient)}**"
                )
                st.caption(patient_code(patient))

            with col2:
                if st.button(
                    "Selected" if is_selected else "Open",
                    key=f"physician_patient_{patient_id}",
                    type=(
                        "primary" if is_selected else "secondary"
                    ),
                    width="stretch",
                ):
                    select_patient(patient)


# ============================================================
# PATIENT FOLLOW-UP VIEW
# ============================================================

def render_patient_followups(patient):

    patient_id = patient.get("patient_id")

    if st.button(
        "Back to Patients",
        icon=":material/arrow_back:",
        key="physician_followups_back",
    ):
        clear_follow_up_state()
        st.rerun()

    # --------------------------------------------------------
    # SUMMARY CARD
    # --------------------------------------------------------

    patient_summary_card(
        patient,
        meta_rows=[
            (
                "Date of Birth",
                format_date(patient.get("date_of_birth")),
            ),
            (
                "Sex",
                patient.get("sex") or "—",
            ),
            (
                "Contact",
                patient.get("contact_number") or "—",
            ),
        ],
    )

    # ========================================================
    # UPCOMING FOLLOW-UPS
    # ========================================================

    upcoming = get_upcoming_follow_ups_by_patient(patient_id) or []

    section_title(
        "Upcoming Follow-Ups",
        caption=f"{len(upcoming)} active",
    )

    if not upcoming:

        empty_state(
            "This patient has no upcoming follow-up visits."
        )

    else:

        for follow_up in upcoming:

            follow_up_id = get_follow_up_id(follow_up)

            status = get_follow_up_status(follow_up)

            source_exam = source_examination(follow_up)
            follow_exam = follow_up_examination(follow_up)

            with st.container(
                key=f"physician_followup_upcoming_{follow_up_id}"
            ):

                follow_up_entry_header(
                    follow_up_datetime(follow_up),
                    status,
                    status_tone(status),
                )

                col1, col2 = st.columns([4, 1])

                with col1:

                    st.markdown(
                        f"**Reason / Notes:** "
                        f"{follow_up.get('notes') or '—'}"
                    )

                    if source_exam:
                        st.caption(
                            "Source examination: "
                            f"{source_exam.get('examination_type') or '—'}"
                        )
                        if source_exam.get("diagnosis"):
                            st.caption(
                                "Source diagnosis: "
                                f"{source_exam.get('diagnosis')}"
                            )

                    if follow_exam:
                        st.caption(
                            "Follow-up examination: "
                            f"{follow_exam.get('examination_type') or '—'}"
                        )
                        if follow_exam.get("diagnosis"):
                            st.caption(
                                "Follow-up diagnosis: "
                                f"{follow_exam.get('diagnosis')}"
                            )
                    else:
                        st.caption(
                            "Follow-up examination: Not linked yet"
                        )

                with col2:

                    if st.button(
                        "Manage",
                        key=f"physician_manage_{follow_up_id}",
                        type="primary",
                        width="stretch",
                    ):
                        show_follow_up_action_dialog(
                            follow_up,
                            patient,
                        )

    # ========================================================
    # FOLLOW-UP HISTORY
    # ========================================================

    history = get_follow_up_history(patient_id) or []

    section_title(
        "Follow-Up History",
        caption=f"{len(history)} record(s)",
    )

    if not history:

        empty_state(
            "No previous follow-up history found for this patient."
        )

    else:

        for follow_up in history:

            follow_up_id = get_follow_up_id(follow_up)

            status = get_follow_up_status(follow_up)

            source_exam = source_examination(follow_up)
            follow_exam = follow_up_examination(follow_up)

            with st.container(
                key=f"physician_followup_history_{follow_up_id}"
            ):

                follow_up_entry_header(
                    follow_up_datetime(follow_up),
                    status,
                    status_tone(status),
                )

                st.markdown(
                    f"**Notes:** "
                    f"{follow_up.get('notes') or '—'}"
                )

                if source_exam:
                    st.caption(
                        "Source examination: "
                        f"{source_exam.get('examination_type') or '—'}"
                    )
                    if source_exam.get("diagnosis"):
                        st.caption(
                            "Source diagnosis: "
                            f"{source_exam.get('diagnosis')}"
                        )

                if follow_exam:
                    st.caption(
                        "Follow-up examination: "
                        f"{follow_exam.get('examination_type') or '—'}"
                    )
                    if follow_exam.get("diagnosis"):
                        st.caption(
                            "Follow-up diagnosis: "
                            f"{follow_exam.get('diagnosis')}"
                        )
                else:
                    st.caption(
                        "Follow-up examination: Not linked"
                    )


# ============================================================
# PAGE
# ============================================================

def show():

    # --------------------------------------------------------
    # CSS — resolves to physician_css/followups.css
    # --------------------------------------------------------

    load_css("followups.css")

    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    if role_id not in (DOCTOR_ROLES + ADMIN_ROLES):
        st.error("You don't have access to Follow-Ups.")
        return

    # --------------------------------------------------------
    # PAGE HEADER
    # --------------------------------------------------------

    page_header(
        "Follow-Ups",
        "Longitudinal view of each patient's follow-up care — "
        "upcoming visits, past outcomes, and linked examinations.",
    )

    if st.button(
        "Refresh",
        icon=":material/refresh:",
        key="physician_followups_refresh",
        width="stretch",
    ):
        st.rerun()

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    effective_hospital_id = (
        None
        if role_id == ROLE_SUPERADMIN
        else hospital_id
    )

    patients = get_patients_with_follow_ups(
        hospital_id=effective_hospital_id
    ) or []

    upcoming_patients = (
        get_patients_with_upcoming_follow_ups(
            hospital_id=effective_hospital_id
        ) or []
    )

    follow_up_counts = get_follow_up_counts(
        hospital_id=effective_hospital_id
    ) or {}

    # --------------------------------------------------------
    # KPI STRIP
    # --------------------------------------------------------

    kpi_strip([
        (
            "Patients With Follow-Ups",
            len(patients),
            "blue",
        ),
        (
            "Upcoming Follow-Ups",
            len(upcoming_patients),
            "amber",
        ),
        (
            "Scheduled",
            follow_up_counts.get("scheduled", 0),
            "green",
        ),
        (
            "Completed",
            follow_up_counts.get("completed", 0),
            "teal",
        ),
    ])

    # --------------------------------------------------------
    # VIEW SWITCH
    # --------------------------------------------------------

    selected_patient = st.session_state.get(
        "selected_follow_up_patient"
    )

    if selected_patient:
        render_patient_followups(selected_patient)
    else:
        render_patient_list(patients)

    # ========================================================
    # ACTION DIALOGS (dispatched by session state)
    # ========================================================

    # --------------------------------------------------------
    # RESCHEDULE
    # --------------------------------------------------------

    if st.session_state.get("reschedule_follow_up_id"):

        follow_up_id = st.session_state["reschedule_follow_up_id"]

        try:
            follow_up = get_follow_up(follow_up_id)

            if follow_up:
                show_reschedule_dialog(follow_up)
            else:
                st.session_state.pop(
                    "reschedule_follow_up_id", None
                )

        except Exception as error:
            st.session_state.pop("reschedule_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")

    # --------------------------------------------------------
    # CANCEL
    # --------------------------------------------------------

    elif st.session_state.get("cancel_follow_up_id"):

        follow_up_id = st.session_state["cancel_follow_up_id"]

        try:
            follow_up = get_follow_up(follow_up_id)

            if follow_up:
                show_cancel_dialog(follow_up)
            else:
                st.session_state.pop(
                    "cancel_follow_up_id", None
                )

        except Exception as error:
            st.session_state.pop("cancel_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")

    # --------------------------------------------------------
    # MISSED
    # --------------------------------------------------------

    elif st.session_state.get("missed_follow_up_id"):

        follow_up_id = st.session_state["missed_follow_up_id"]

        try:
            follow_up = get_follow_up(follow_up_id)

            if follow_up:
                show_missed_dialog(follow_up)
            else:
                st.session_state.pop(
                    "missed_follow_up_id", None
                )

        except Exception as error:
            st.session_state.pop("missed_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")