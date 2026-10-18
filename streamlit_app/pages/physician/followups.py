# streamlit_app/pages/physician/followups.py

"""
Physician — Follow-Ups.

Two views:
  View 1 — Patient list (with patient-level follow-up summary)
  View 2 — Patient follow-up detail (with FU ID + parent + previous)
"""

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


ROLE_SUPERADMIN = 1
ROLE_RADIOLOGIST = 3
ROLE_HOSPITAL_ADMIN = 6

DOCTOR_ROLES = [ROLE_RADIOLOGIST]
ADMIN_ROLES = [ROLE_SUPERADMIN, ROLE_HOSPITAL_ADMIN]

ACTIVE_FOLLOW_UP_STATUSES = ["Scheduled", "Rescheduled"]


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
    return patient.get("patient_code") or patient.get("patient_id")


# ============================================================
# EXAMINATION HELPERS
# ============================================================

def source_examination(fu):
    ex = fu.get("source_examination") or {}
    if isinstance(ex, list):
        return ex[0] if ex else {}
    return ex


def follow_up_examination(fu):
    ex = fu.get("follow_up_examination") or {}
    if isinstance(ex, list):
        return ex[0] if ex else {}
    return ex


def get_follow_up_id(fu):
    return fu.get("follow_up_id") or fu.get("id")


def get_follow_up_status(fu):
    return fu.get("status") or "Scheduled"


# ============================================================
# DATE / TIME
# ============================================================

def format_datetime(date_value, time_value=None):
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
                time_obj = datetime.strptime(time_text[:8], "%H:%M:%S")
                return f"{formatted_date} at {time_obj.strftime('%I:%M %p')}"
            except Exception:
                try:
                    time_obj = datetime.strptime(time_text[:5], "%H:%M")
                    return f"{formatted_date} at {time_obj.strftime('%I:%M %p')}"
                except Exception:
                    return f"{formatted_date} at {time_text}"
        return formatted_date
    except Exception:
        if time_value:
            return f"{date_value} at {time_value}"
        return str(date_value)


def follow_up_datetime(fu):
    return format_datetime(fu.get("follow_up_date"), fu.get("follow_up_time"))


# ============================================================
# STATUS
# ============================================================

def status_tone(status):
    s = str(status or "").strip().lower()
    return {
        "scheduled": "blue",
        "completed": "green",
        "missed": "red",
        "cancelled": "red",
        "rescheduled": "amber",
    }.get(s, "grey")


# ============================================================
# STATE
# ============================================================

def clear_follow_up_state():
    for k in (
        "selected_follow_up_patient",
        "selected_follow_up_patient_id",
        "follow_up_action_id",
        "reschedule_follow_up_id",
        "cancel_follow_up_id",
        "missed_follow_up_id",
        "physician_parent_view",
        "physician_prev_fu_view",
    ):
        st.session_state.pop(k, None)


def select_patient(patient):
    st.session_state["selected_follow_up_patient"] = patient
    st.session_state["selected_follow_up_patient_id"] = patient.get("patient_id")
    st.rerun()


# ============================================================
# DIALOG — PARENT CONSULT
# ============================================================

@st.dialog("Parent General Consult", width="medium")
def show_parent_consult_dialog(exam):

    if not exam:
        st.error("No consultation data.")
        return

    section_title(exam.get("examination_type") or "General Consult")

    show_rows([
        ("Date", format_datetime(exam.get("examination_date"))),
        ("Status", exam.get("status") or "—"),
        ("Chief Complaint", exam.get("chief_complaint") or "—"),
        ("HPI", exam.get("history_of_present_illness") or "—"),
        ("Physical Exam", exam.get("physical_examination") or "—"),
        ("Diagnosis", exam.get("diagnosis") or "—"),
        ("Plans / Orders", exam.get("plans_orders") or "—"),
        ("Disposition", exam.get("disposition") or "—"),
    ])

    st.divider()

    if st.button("Close", key="physician_parent_close", use_container_width=True):
        st.session_state.pop("physician_parent_view", None)
        st.rerun()


# ============================================================
# DIALOG — PREVIOUS FOLLOW-UP
# ============================================================

@st.dialog("Previous Follow-Up", width="medium")
def show_previous_follow_up_dialog(fu):

    if not fu:
        st.error("No previous follow-up data.")
        return

    section_title(fu.get("follow_up_code") or "Previous Follow-Up")

    show_rows([
        ("Scheduled", follow_up_datetime(fu)),
        ("Status", fu.get("status") or "—"),
        ("Notes", fu.get("notes") or "—"),
    ])

    linked = follow_up_examination(fu)

    if linked:
        st.divider()
        section_title("Examination")
        show_rows([
            ("Examination", linked.get("examination_type") or "—"),
            ("Date", format_datetime(linked.get("examination_date"))),
            ("Diagnosis", linked.get("diagnosis") or "—"),
            ("Status", linked.get("status") or "—"),
        ])

    st.divider()

    if st.button("Close", key="physician_prev_fu_close", use_container_width=True):
        st.session_state.pop("physician_prev_fu_view", None)
        st.rerun()


# ============================================================
# DIALOG — RESCHEDULE / CANCEL / MISSED (unchanged)
# ============================================================

@st.dialog("Reschedule Follow-Up", width="medium")
def show_reschedule_dialog(fu):

    fu_id = get_follow_up_id(fu)

    default_date = fu.get("follow_up_date")
    if isinstance(default_date, str):
        try:
            default_date = date.fromisoformat(default_date[:10])
        except Exception:
            default_date = date.today()
    if not isinstance(default_date, date):
        default_date = date.today()
    if default_date < date.today():
        default_date = date.today()

    default_time = fu.get("follow_up_time")
    if isinstance(default_time, str):
        try:
            default_time = time.fromisoformat(default_time[:8])
        except Exception:
            default_time = time(9, 0)
    if not isinstance(default_time, time):
        default_time = time(9, 0)

    section_title("New Schedule")

    new_date = st.date_input(
        "New Follow-Up Date",
        value=default_date,
        min_value=date.today(),
        key=f"physician_reschedule_date_{fu_id}",
    )

    new_time = st.time_input(
        "New Follow-Up Time",
        value=default_time,
        key=f"physician_reschedule_time_{fu_id}",
    )

    st.divider()

    col1, col2 = st.columns(2)

    if col1.button(
        "Cancel",
        key=f"physician_reschedule_cancel_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("reschedule_follow_up_id", None)
        st.session_state.pop("selected_follow_up_patient", None)
        st.rerun()

    if col2.button(
        "Save Schedule",
        key=f"physician_reschedule_save_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = reschedule_follow_up(
            fu_id,
            new_date,
            new_time.strftime("%H:%M:%S"),
        )
        if result.get("success"):
            st.session_state.pop("reschedule_follow_up_id", None)
            remember("Follow-up rescheduled successfully.")
            st.rerun()
        else:
            st.error(result.get("message", "Failed to reschedule."))


@st.dialog("Cancel Follow-Up", width="small")
def show_cancel_dialog(fu):

    fu_id = get_follow_up_id(fu)
    patient = fu.get("patients") or {}

    st.warning("Cancel this follow-up? This cannot be undone from here.")
    show_rows([
        ("Patient", patient_name(patient)),
        ("Scheduled", follow_up_datetime(fu)),
    ])

    st.divider()

    col1, col2 = st.columns(2)

    if col1.button(
        "Keep Follow-Up",
        key=f"physician_cancel_keep_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("cancel_follow_up_id", None)
        st.rerun()

    if col2.button(
        "Yes, Cancel",
        key=f"physician_cancel_confirm_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = cancel_follow_up(fu_id)
        if result.get("success"):
            st.session_state.pop("cancel_follow_up_id", None)
            remember("Follow-up cancelled.")
            st.rerun()
        else:
            st.error(result.get("message", "Failed to cancel."))


@st.dialog("Mark Follow-Up Missed", width="small")
def show_missed_dialog(fu):

    fu_id = get_follow_up_id(fu)
    patient = fu.get("patients") or {}

    st.warning("Mark this follow-up as missed?")
    show_rows([
        ("Patient", patient_name(patient)),
        ("Scheduled", follow_up_datetime(fu)),
    ])

    st.divider()

    col1, col2 = st.columns(2)

    if col1.button(
        "Cancel",
        key=f"physician_missed_cancel_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("missed_follow_up_id", None)
        st.rerun()

    if col2.button(
        "Mark Missed",
        key=f"physician_missed_confirm_{fu_id}",
        type="primary",
        width="stretch",
    ):
        result = update_follow_up_status(fu_id, "Missed")
        if result.get("success"):
            st.session_state.pop("missed_follow_up_id", None)
            remember("Follow-up marked as missed.")
            st.rerun()
        else:
            st.error(result.get("message", "Failed to update follow-up."))


# ============================================================
# DIALOG — FOLLOW-UP ACTION (Manage)
# ============================================================

@st.dialog("Follow-Up Details", width="medium")
def show_follow_up_action_dialog(fu, patient):

    fu_id = get_follow_up_id(fu)
    status = get_follow_up_status(fu)
    linked_exam = follow_up_examination(fu)
    linked_status = linked_exam.get("status") if linked_exam else None
    exam_completed = (linked_status == "Completed")
    is_active = status in ACTIVE_FOLLOW_UP_STATUSES

    section_title("Follow-Up Details")

    show_rows([
        ("Code", fu.get("follow_up_code") or "—"),
        ("Patient", patient_name(patient)),
        ("Patient ID", patient_code(patient)),
        ("Schedule", follow_up_datetime(fu)),
        ("Status", pill(status, status_tone(status))),
    ])

    st.divider()

    # Source
    ex_source = source_examination(fu)
    section_title("Source Examination")
    if ex_source:
        show_rows([
            ("Examination", ex_source.get("examination_type") or "—"),
            ("Date", format_datetime(ex_source.get("examination_date"))),
            ("Diagnosis", ex_source.get("diagnosis") or "—"),
        ])
    else:
        st.caption("No source examination linked.")

    st.divider()

    section_title("Follow-Up Examination")
    if linked_exam:
        show_rows([
            ("Examination", linked_exam.get("examination_type") or "—"),
            ("Date", format_datetime(linked_exam.get("examination_date"))),
            ("Diagnosis", linked_exam.get("diagnosis") or "—"),
            ("Status", linked_exam.get("status") or "—"),
        ])
    else:
        st.info("No follow-up examination linked yet.")

    # Notes
    notes = fu.get("notes")
    if notes:
        st.divider()
        section_title("Notes")
        st.write(notes)

    st.divider()

    if status in ("Completed", "Cancelled", "Missed"):
        if st.button(
            "Close",
            key=f"physician_followup_close_{fu_id}",
            width="stretch",
        ):
            st.session_state.pop("selected_follow_up_patient", None)
            st.rerun()
        return

    # Active
    if is_active and exam_completed:
        st.success("Examination completed. You may close this follow-up.")

        if st.button(
            "Mark Follow-Up Completed",
            key=f"physician_complete_{fu_id}",
            type="primary",
            width="stretch",
        ):
            result = complete_follow_up(fu_id)
            if result.get("success"):
                remember("Follow-up marked as completed.")
                st.rerun()
            else:
                st.error(result.get("message", "Failed to complete."))

    if is_active and not linked_exam:
        if st.button(
            "Mark Follow-Up Missed",
            key=f"physician_open_missed_{fu_id}",
            width="stretch",
        ):
            st.session_state["missed_follow_up_id"] = fu_id
            st.rerun()

    if is_active and not exam_completed:
        st.divider()
        col1, col2 = st.columns(2)

        if col1.button(
            "Reschedule",
            key=f"physician_open_reschedule_{fu_id}",
            width="stretch",
        ):
            st.session_state["reschedule_follow_up_id"] = fu_id
            st.rerun()

        if col2.button(
            "Cancel Follow-Up",
            key=f"physician_open_cancel_{fu_id}",
            width="stretch",
        ):
            st.session_state["cancel_follow_up_id"] = fu_id
            st.rerun()

    st.divider()

    if st.button(
        "Close",
        key=f"physician_followup_close2_{fu_id}",
        width="stretch",
    ):
        st.session_state.pop("selected_follow_up_patient", None)
        st.rerun()


# ============================================================
# VIEW 1 — PATIENT LIST
# ============================================================

def render_patient_list(patients, selected_patient_id=None):

    if not patients:
        empty_state("No patients currently have follow-up schedules.")
        return

    section_title("Patients With Follow-Ups")
    st.caption(
        "Select a patient to open their follow-up file — upcoming visits, "
        "past outcomes, and linked examinations."
    )

    for patient in patients:
        patient_id = patient.get("patient_id")
        is_selected = (patient_id == selected_patient_id)

        with st.container(key=f"physician_patient_list_{patient_id}"):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{patient_name(patient)}**")
                st.caption(patient_code(patient))
            with col2:
                if st.button(
                    "Selected" if is_selected else "Open",
                    key=f"physician_patient_{patient_id}",
                    type="primary" if is_selected else "secondary",
                    width="stretch",
                ):
                    select_patient(patient)


# ============================================================
# VIEW 2 — PATIENT FOLLOW-UPS (per patient)
# ============================================================

def render_physician_follow_up_card(fu, patient):

    fu_id = get_follow_up_id(fu)
    code = fu.get("follow_up_code") or "—"
    status = get_follow_up_status(fu)

    prev_id = fu.get("previous_follow_up_id")
    prev_fu = None
    if prev_id:
        try:
            prev_fu = get_follow_up(prev_id)
        except Exception:
            prev_fu = None

    with st.container(key=f"physician_fu_card_{fu_id}"):

        col_code, col_date, col_status = st.columns([1.4, 3, 1.2])

        with col_code:
            st.markdown(
                f"<div class='pf-fu-code'>{code}</div>",
                unsafe_allow_html=True,
            )

        with col_date:
            st.markdown(
                f"<div class='pf-fu-when'>"
                f"{follow_up_datetime(fu)}"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_status:
            pill(status, status_tone(status))

        if fu.get("notes"):
            st.markdown(
                f"<p class='pf-fu-notes'>{fu.get('notes')}</p>",
                unsafe_allow_html=True,
            )

        col_parent, col_prev, col_manage = st.columns([1, 1, 1])

        ex_source = source_examination(fu)

        with col_parent:
            if ex_source:
                if st.button(
                    "See Parent Consult",
                    key=f"physician_fu_parent_{fu_id}",
                    icon=":material/arrow_forward:",
                    use_container_width=True,
                ):
                    st.session_state["physician_parent_view"] = ex_source
                    st.rerun()
            else:
                st.caption("No parent")

        with col_prev:
            if prev_fu:
                if st.button(
                    "See Previous Follow-Up",
                    key=f"physician_fu_prev_{fu_id}",
                    icon=":material/arrow_forward:",
                    use_container_width=True,
                ):
                    st.session_state["physician_prev_fu_view"] = prev_fu
                    st.rerun()
            else:
                st.caption("First follow-up")

        with col_manage:
            if st.button(
                "Manage",
                key=f"physician_fu_manage_{fu_id}",
                icon=":material/settings:",
                type="primary",
                use_container_width=True,
            ):
                show_follow_up_action_dialog(fu, patient)


def render_patient_followups(patient):

    patient_id = patient.get("patient_id")

    if st.button(
        "Back to Patients",
        icon=":material/arrow_back:",
        key="physician_followups_back",
    ):
        clear_follow_up_state()
        st.rerun()

    patient_summary_card(
        patient,
        meta_rows=[
            ("Date of Birth", format_date(patient.get("date_of_birth"))),
            ("Sex", patient.get("sex") or "—"),
            ("Contact", patient.get("contact_number") or "—"),
        ],
    )

    upcoming = get_upcoming_follow_ups_by_patient(patient_id) or []

    section_title(
        "Upcoming Follow-Ups",
        caption=f"{len(upcoming)} active",
    )

    if not upcoming:
        empty_state("This patient has no upcoming follow-up visits.")
    else:
        for fu in upcoming:
            render_physician_follow_up_card(fu, patient)

    history = get_follow_up_history(patient_id) or []

    section_title(
        "Follow-Up History",
        caption=f"{len(history)} record(s)",
    )

    if not history:
        empty_state("No previous follow-up history found for this patient.")
    else:
        for fu in history:
            render_physician_follow_up_card(fu, patient)


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("followups.css")
    show_flash_message()

    role_id = current_role_id()
    hospital_id = current_hospital_id()

    if role_id not in (DOCTOR_ROLES + ADMIN_ROLES):
        st.error("You don't have access to Follow-Ups.")
        return

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

    effective_hospital_id = (
        None if role_id == ROLE_SUPERADMIN else hospital_id
    )

    patients = get_patients_with_follow_ups(
        hospital_id=effective_hospital_id
    ) or []

    upcoming_patients = get_patients_with_upcoming_follow_ups(
        hospital_id=effective_hospital_id
    ) or []

    follow_up_counts = get_follow_up_counts(
        hospital_id=effective_hospital_id
    ) or {}

    kpi_strip([
        ("Patients With Follow-Ups", len(patients), "blue"),
        ("Upcoming Follow-Ups", len(upcoming_patients), "amber"),
        ("Scheduled", follow_up_counts.get("scheduled", 0), "green"),
        ("Completed", follow_up_counts.get("completed", 0), "teal"),
    ])

    selected_patient = st.session_state.get("selected_follow_up_patient")

    if selected_patient:
        render_patient_followups(selected_patient)
    else:
        render_patient_list(patients)

    # --------------------------------------------------------
    # DIALOG DISPATCHER
    # --------------------------------------------------------

    if st.session_state.get("physician_parent_view"):
        show_parent_consult_dialog(
            st.session_state["physician_parent_view"]
        )
        return

    if st.session_state.get("physician_prev_fu_view"):
        show_previous_follow_up_dialog(
            st.session_state["physician_prev_fu_view"]
        )
        return

    if st.session_state.get("reschedule_follow_up_id"):
        fu_id = st.session_state["reschedule_follow_up_id"]
        try:
            fu = get_follow_up(fu_id)
            if fu:
                show_reschedule_dialog(fu)
            else:
                st.session_state.pop("reschedule_follow_up_id", None)
        except Exception as error:
            st.session_state.pop("reschedule_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")

    elif st.session_state.get("cancel_follow_up_id"):
        fu_id = st.session_state["cancel_follow_up_id"]
        try:
            fu = get_follow_up(fu_id)
            if fu:
                show_cancel_dialog(fu)
            else:
                st.session_state.pop("cancel_follow_up_id", None)
        except Exception as error:
            st.session_state.pop("cancel_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")

    elif st.session_state.get("missed_follow_up_id"):
        fu_id = st.session_state["missed_follow_up_id"]
        try:
            fu = get_follow_up(fu_id)
            if fu:
                show_missed_dialog(fu)
            else:
                st.session_state.pop("missed_follow_up_id", None)
        except Exception as error:
            st.session_state.pop("missed_follow_up_id", None)
            st.error(f"Failed to load follow-up: {error}")