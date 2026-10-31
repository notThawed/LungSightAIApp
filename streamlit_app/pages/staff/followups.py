# streamlit_app/pages/staff/followups.py

"""
Staff — Follow-Ups.

3 views:
  View 1 — Landing: search + today's scheduled + KPI
  View 2 — FU detail: patient + appointment + parent + previous + actions
  View 3 — Confirm arrival dialog
"""

import streamlit as st

from datetime import date, datetime, time as time_cls
from zoneinfo import ZoneInfo

from backend.backend_utils.followup_utils import (
    get_scheduled_follow_ups_for_date,
    search_follow_ups,
    get_follow_up,
    mark_follow_up_arrived,
    get_follow_up_counts,
    cancel_follow_up,
    reschedule_follow_up,
)

from streamlit_app.components.ui import (
    page_header,
    empty_state,
    section_title,
    show_rows,
    full_name,
    pill,
    metric_card,
    remember,
    safe,
    show_flash_message,
)

from shared.assets import load_css


ROLE_SUPERADMIN = 1
ROLE_STAFF = 7
ROLE_HOSPITAL_ADMIN = 6

MANILA_TZ = ZoneInfo("Asia/Manila")
KEY_SELECTED_FU = "staff_selected_fu"


# ============================================================
# USER HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_role_id():
    return current_user().get("role_id")


def current_hospital_id():
    return current_user().get("hospital_id")


def current_user_id():
    return current_user().get("user_id")


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )


def patient_code(patient):
    return patient.get("patient_code") or patient.get("patient_id")


def patient_age(dob):
    if not dob:
        return "—"
    try:
        if isinstance(dob, str):
            d = date.fromisoformat(str(dob)[:10])
        elif isinstance(dob, date):
            d = dob
        else:
            return "—"
        today = date.today()
        age = today.year - d.year
        if (today.month, today.day) < (d.month, d.day):
            age -= 1
        return age
    except Exception:
        return "—"


# ============================================================
# DATE / TIME
# ============================================================

def format_time(value):
    if not value:
        return "—"
    try:
        if isinstance(value, time_cls):
            return value.strftime("%I:%M %p")
        return datetime.strptime(str(value)[:8], "%H:%M:%S").strftime("%I:%M %p")
    except Exception:
        return str(value)


def format_date_only(value):
    if not value:
        return "—"
    try:
        if isinstance(value, date):
            return value.strftime("%B %d, %Y")
        return date.fromisoformat(str(value)[:10]).strftime("%B %d, %Y")
    except Exception:
        return str(value)


def format_appointment(fu):
    return f"{format_date_only(fu.get('follow_up_date'))} · {format_time(fu.get('follow_up_time'))}"


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
    }.get(s, "slate")


# ============================================================
# NAVIGATION
# ============================================================

def go_to_fu_detail(fu):
    st.session_state[KEY_SELECTED_FU] = fu
    st.rerun()


def back_to_landing():
    st.session_state.pop(KEY_SELECTED_FU, None)
    st.rerun()


# ============================================================
# DIALOG — CONFIRM ARRIVAL
# ============================================================

@st.dialog("Confirm Patient Arrival", width="small")
def show_confirm_arrival_dialog(fu):

    fu_id = fu.get("follow_up_id")
    code = fu.get("follow_up_code") or "—"
    patient = fu.get("patients") or {}
    if isinstance(patient, list):
        patient = patient[0] if patient else {}

    source = fu.get("source_examination") or {}
    if isinstance(source, list):
        source = source[0] if source else {}

    st.markdown(f"**Follow-Up {code}**")

    show_rows([
        ("Patient", patient_name(patient)),
        ("Patient ID", patient_code(patient)),
        ("Scheduled", format_appointment(fu)),
        (
            "Parent",
            f"{source.get('examination_type') or 'General Consult'} · "
            f"{format_date_only(source.get('examination_date'))}",
        ),
    ])

    st.divider()
    st.caption(
        "By confirming, you will create a new Follow-Up Examination "
        "and send the patient to the Physician Queue."
    )
    st.divider()

    cancel_col, confirm_col = st.columns(2)

    if cancel_col.button(
        "Cancel",
        key=f"staff_fu_arrive_cancel_{fu_id}",
        use_container_width=True,
    ):
        st.rerun()

    if confirm_col.button(
        "Confirm Arrival",
        key=f"staff_fu_arrive_confirm_{fu_id}",
        type="primary",
        use_container_width=True,
    ):
        result = mark_follow_up_arrived(fu_id, current_user_id())

        if result.get("success"):
            remember(
                "Patient checked in. Follow-up examination created "
                "and sent to Physician Queue."
            )
            st.session_state.pop("staff_fu_arrival_target", None)
            back_to_landing()
        else:
            st.error(
                f"Could not check in patient: "
                f"{result.get('message', 'Unknown error')}"
            )


# ============================================================
# VIEW 1 — LANDING
# ============================================================

def render_kpi_strip(todays, counts):

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card("Scheduled Today", len(todays), "event", tone="blue")

    with col2:
        metric_card(
            "Pending Arrival",
            len(todays),
            "schedule",
            tone="amber",
        )

    with col3:
        metric_card(
            "Total Follow-Ups",
            counts.get("scheduled", 0) + counts.get("rescheduled", 0),
            "calendar_month",
            tone="green",
        )


def render_search_bar():

    st.markdown(
        "<p class='sf-search-label'>Search follow-up</p>",
        unsafe_allow_html=True,
    )

    with st.form("staff_fu_search_form", clear_on_submit=False):
        col_input, col_btn = st.columns([5, 1])

        with col_input:
            query = st.text_input(
                "Search",
                placeholder="Enter FU ID (e.g. FU-2026-00042) or patient name",
                label_visibility="collapsed",
                key="staff_fu_search_query",
            )

        with col_btn:
            submitted = st.form_submit_button(
                "Search",
                type="primary",
                use_container_width=True,
            )

    if not submitted:
        return

    if not query or not query.strip():
        st.warning("Please enter a Follow-Up ID or patient name.")
        return

    results = search_follow_ups(
        query.strip(),
        hospital_id=current_hospital_id(),
    )

    if not results:
        st.warning(f"No follow-up found matching **{query.strip()}**.")
        return

    if len(results) == 1:
        go_to_fu_detail(results[0])
        return

    st.markdown(
        f"<div class='sf-search-results-banner'>"
        f"<span class='material-symbols-rounded'>search_check</span>"
        f"<span>Found <b>{len(results)}</b> follow-up appointment(s) matching &ldquo;{safe(query.strip())}&rdquo;</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='sf-table-header'>"
        "<span>Follow-Up ID</span>"
        "<span>Patient Details</span>"
        "<span>Scheduled Time</span>"
        "<span>Parent Consult</span>"
        "<span>Status</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    for fu in results:
        render_today_fu_card(fu, show_arrived=False)


def render_today_fu_card(fu, show_arrived=True):

    fu_id = fu.get("follow_up_id")
    code = fu.get("follow_up_code") or "—"
    status = fu.get("status") or "Scheduled"
    patient = fu.get("patients") or {}
    if isinstance(patient, list):
        patient = patient[0] if patient else {}

    source = fu.get("source_examination") or {}
    if isinstance(source, list):
        source = source[0] if source else {}

    parent_summary = (
        f"{source.get('examination_type') or 'General Consult'} · "
        f"{format_date_only(source.get('examination_date'))}"
    )

    with st.container(key=f"sf_fu_card_{fu_id}"):

        cols = st.columns([1.6, 2.5, 2.2, 2.2, 1.2], vertical_alignment="center")

        with cols[0]:
            st.markdown(
                f"<div class='sf-fu-code-badge'>"
                f"<span class='material-symbols-rounded sf-code-icon'>tag</span>"
                f"<span>{safe(code)}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with cols[1]:
            st.markdown(
                f"<div class='sf-fu-patient'>{safe(patient_name(patient))}</div>"
                f"<div class='sf-fu-sub'><span class='material-symbols-rounded sf-sub-icon'>badge</span>{safe(patient_code(patient))}</div>",
                unsafe_allow_html=True,
            )

        with cols[2]:
            st.markdown(
                f"<div class='sf-fu-schedule'>"
                f"<span class='material-symbols-rounded sf-sched-icon'>calendar_today</span>"
                f"<span class='sf-sched-text'>{safe(format_appointment(fu))}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with cols[3]:
            st.markdown(
                f"<div class='sf-fu-parent'>"
                f"<span class='material-symbols-rounded sf-parent-icon'>medical_information</span>"
                f"<span class='sf-parent-text'>{safe(parent_summary)}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with cols[4]:
            pill(status, status_tone(status))

        btn_cols = st.columns([1, 1, 3, 1], vertical_alignment="center")

        with btn_cols[0]:
            if st.button(
                "View",
                key=f"sf_fu_view_{fu_id}",
                icon=":material/visibility:",
                use_container_width=True,
            ):
                go_to_fu_detail(fu)

        with btn_cols[1]:
            if show_arrived and status in ("Scheduled", "Rescheduled"):
                if st.button(
                    "Arrived",
                    key=f"sf_fu_arrived_{fu_id}",
                    icon=":material/check_circle:",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state["staff_fu_arrival_target"] = fu
                    st.rerun()


def render_landing():

    hospital_id = current_hospital_id()
    today = date.today()

    todays = get_scheduled_follow_ups_for_date(today, hospital_id) or []
    counts = get_follow_up_counts(hospital_id=hospital_id) or {}

    render_kpi_strip(todays, counts)
    st.divider()
    render_search_bar()
    st.divider()

    section_title(
        "Today's Scheduled Follow-Ups",
        f"{len(todays)} appointment(s) · {format_date_only(today)}",
    )

    if not todays:
        empty_state("No follow-up appointments are scheduled for today.")
    else:
        st.markdown(
            "<div class='sf-table-header'>"
            "<span>Follow-Up ID</span>"
            "<span>Patient Details</span>"
            "<span>Scheduled Time</span>"
            "<span>Parent Consult</span>"
            "<span>Status</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        for fu in todays:
            render_today_fu_card(fu)


# ============================================================
# VIEW 2 — FU DETAIL
# ============================================================

@st.dialog("Parent General Consult", width="medium")
def show_parent_consult_dialog(exam):

    if not exam:
        st.error("No consultation data.")
        return

    st.markdown(
        "<div class='sf-detail-header'>"
        f"<p class='sf-detail-title'>"
        f"{exam.get('examination_type') or 'General Consult'}</p>"
        f"<p class='sf-detail-sub'>"
        f"{format_date_only(exam.get('examination_date'))}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    show_rows([
        ("Status", exam.get("status") or "—"),
        ("Chief Complaint", exam.get("chief_complaint") or "—"),
        ("HPI", exam.get("history_of_present_illness") or "—"),
        ("Physical Exam", exam.get("physical_examination") or "—"),
        ("Diagnosis", exam.get("diagnosis") or "—"),
        ("Plans / Orders", exam.get("plans_orders") or "—"),
        ("Disposition", exam.get("disposition") or "—"),
    ])

    st.divider()

    if st.button(
        "Close",
        key="staff_parent_consult_close",
        use_container_width=True,
    ):
        st.session_state.pop("staff_fu_parent_view", None)
        st.rerun()


def render_fu_detail():

    fu = st.session_state.get(KEY_SELECTED_FU)
    if not fu:
        back_to_landing()
        return

    try:
        refreshed = get_follow_up(fu.get("follow_up_id"))
        if refreshed:
            fu = refreshed
            st.session_state[KEY_SELECTED_FU] = refreshed
    except Exception:
        pass

    code = fu.get("follow_up_code") or "—"
    status = fu.get("status") or "Scheduled"
    patient = fu.get("patients") or {}
    if isinstance(patient, list):
        patient = patient[0] if patient else {}

    source = fu.get("source_examination") or {}
    if isinstance(source, list):
        source = source[0] if source else {}

    prev_id = fu.get("previous_follow_up_id")
    prev_fu = None
    if prev_id:
        try:
            prev_fu = get_follow_up(prev_id)
        except Exception:
            prev_fu = None

    if st.button(
        "Back to Follow-Ups",
        key="staff_fu_detail_back",
        icon=":material/arrow_back:",
    ):
        back_to_landing()

    st.markdown(
        "<div class='sf-detail-header'>"
        "<div class='sf-detail-eyebrow'>"
        "<span class='material-symbols-rounded sf-eyebrow-icon'>medical_services</span>"
        "<span>Patient Follow-Up Dossier</span>"
        "</div>"
        "<div class='sf-detail-title-row'>"
        f"<p class='sf-detail-title'>Follow-Up {safe(code)}</p>"
        f"<span class='sf-detail-pill'><span class='material-symbols-rounded'>event_available</span>{safe(format_appointment(fu))}</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        st.markdown(
            "<div class='sf-card'>"
            "<div class='sf-card-header-bar'>"
            "<span class='material-symbols-rounded sf-card-icon'>person</span>"
            "<span class='sf-card-eyebrow'>Patient Demographics</span>"
            "</div>"
            f"<p class='sf-card-title'>{safe(patient_name(patient))}</p>"
            "<div class='sf-card-row'>"
            f"<span>Patient ID</span><b class='sf-mono-code'>{safe(patient_code(patient))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Age / Gender</span>"
            f"<b>{safe(str(patient_age(patient.get('date_of_birth'))))} yrs / "
            f"{safe(patient.get('sex') or '—')}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Contact</span>"
            f"<b>{safe(patient.get('contact_number') or '—')}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            "<div class='sf-card'>"
            "<div class='sf-card-header-bar'>"
            "<span class='material-symbols-rounded sf-card-icon'>calendar_month</span>"
            "<span class='sf-card-eyebrow'>Appointment Schedule</span>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Status</span><b>{pill(status, status_tone(status))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Scheduled Date</span>"
            f"<b>{safe(format_date_only(fu.get('follow_up_date')))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Scheduled Time</span>"
            f"<b>{safe(format_time(fu.get('follow_up_time')))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Clinical Notes</span>"
            f"<b>{safe(fu.get('notes') or 'None recorded')}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    section_title("Parent General Consult")

    if source:
        st.markdown(
            "<div class='sf-card sf-card--info'>"
            "<div class='sf-card-header-bar'>"
            "<span class='material-symbols-rounded sf-card-icon sf-card-icon-blue'>clinical_notes</span>"
            "<span class='sf-card-eyebrow'>Initial Clinical Encounter</span>"
            "</div>"
            f"<p class='sf-card-title'>"
            f"{safe(source.get('examination_type') or 'General Consult')}</p>"
            "<div class='sf-card-row'>"
            f"<span>Consult Date</span>"
            f"<b>{safe(format_date_only(source.get('examination_date')))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Chief Complaint</span>"
            f"<b>{safe(source.get('chief_complaint') or '—')}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Working Diagnosis</span>"
            f"<b>{safe(source.get('diagnosis') or '—')}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("No parent consultation linked.")

    section_title("Previous Follow-Up")

    if prev_fu:
        st.markdown(
            "<div class='sf-card sf-card--info'>"
            "<div class='sf-card-header-bar'>"
            "<span class='material-symbols-rounded sf-card-icon sf-card-icon-teal'>history</span>"
            "<span class='sf-card-eyebrow'>Prior Follow-Up History</span>"
            "</div>"
            f"<p class='sf-card-title'>"
            f"{safe(prev_fu.get('follow_up_code') or 'Previous Follow-Up')}</p>"
            "<div class='sf-card-row'>"
            f"<span>Scheduled</span>"
            f"<b>{safe(format_appointment(prev_fu))}</b>"
            "</div>"
            "<div class='sf-card-row'>"
            f"<span>Status</span>"
            f"<b>{pill(prev_fu.get('status') or '—', status_tone(prev_fu.get('status')))}</b>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("No previous follow-up — this is the first.")

    st.divider()

    col_arrive, col_view, col_resched, col_cancel = st.columns(4)

    if col_arrive.button(
        "Mark as Arrived",
        key=f"staff_fu_arrive_detail_{fu.get('follow_up_id')}",
        icon=":material/check_circle:",
        type="primary",
        use_container_width=True,
        disabled=status not in ("Scheduled", "Rescheduled"),
    ):
        st.session_state["staff_fu_arrival_target"] = fu
        st.rerun()

    if col_view.button(
        "View Full Parent",
        key=f"staff_fu_view_parent_{fu.get('follow_up_id')}",
        icon=":material/open_in_new:",
        use_container_width=True,
    ):
        st.session_state["staff_fu_parent_view"] = source
        st.rerun()

    if col_resched.button(
        "Reschedule",
        key=f"staff_fu_resched_{fu.get('follow_up_id')}",
        icon=":material/event_repeat:",
        use_container_width=True,
        disabled=status not in ("Scheduled", "Rescheduled"),
    ):
        st.session_state["staff_fu_reschedule_target"] = fu
        st.rerun()

    if col_cancel.button(
        "Cancel",
        key=f"staff_fu_cancel_{fu.get('follow_up_id')}",
        icon=":material/cancel:",
        use_container_width=True,
        disabled=status not in ("Scheduled", "Rescheduled"),
    ):
        st.session_state["staff_fu_cancel_target"] = fu
        st.rerun()


# ============================================================
# DIALOG — RESCHEDULE
# ============================================================

@st.dialog("Reschedule Follow-Up", width="small")
def show_reschedule_dialog(fu):

    fu_id = fu.get("follow_up_id")

    try:
        default_date = date.fromisoformat(str(fu.get("follow_up_date"))[:10])
    except Exception:
        default_date = date.today()

    if default_date < date.today():
        default_date = date.today()

    st.markdown(
        f"Reschedule **{fu.get('follow_up_code') or 'this follow-up'}**."
    )

    new_date = st.date_input(
        "New Date",
        value=default_date,
        min_value=date.today(),
        key=f"staff_fu_resched_date_{fu_id}",
    )

    try:
        default_time = time_cls.fromisoformat(str(fu.get("follow_up_time"))[:8])
    except Exception:
        default_time = time_cls(9, 0)

    new_time = st.time_input(
        "New Time",
        value=default_time,
        key=f"staff_fu_resched_time_{fu_id}",
    )

    st.divider()

    cancel_col, save_col = st.columns(2)

    if cancel_col.button(
        "Cancel",
        key=f"staff_fu_resched_cancel_{fu_id}",
        use_container_width=True,
    ):
        st.session_state.pop("staff_fu_reschedule_target", None)
        st.rerun()

    if save_col.button(
        "Save",
        key=f"staff_fu_resched_save_{fu_id}",
        type="primary",
        use_container_width=True,
    ):
        result = reschedule_follow_up(
            fu_id,
            new_date,
            new_time.strftime("%H:%M:%S"),
        )

        if result.get("success"):
            remember("Follow-up rescheduled.")
            st.session_state.pop("staff_fu_reschedule_target", None)
            st.rerun()
        else:
            st.error(result.get("message", "Failed to reschedule."))


# ============================================================
# DIALOG — CANCEL
# ============================================================

@st.dialog("Cancel Follow-Up", width="small")
def show_cancel_dialog(fu):

    fu_id = fu.get("follow_up_id")

    st.warning(f"Cancel follow-up **{fu.get('follow_up_code') or ''}**?")
    st.caption(
        "This cannot be undone from here. A new follow-up can "
        "be scheduled by the physician if needed."
    )

    st.divider()

    keep_col, cancel_col = st.columns(2)

    if keep_col.button(
        "Keep Follow-Up",
        key=f"staff_fu_cancel_keep_{fu_id}",
        use_container_width=True,
    ):
        st.session_state.pop("staff_fu_cancel_target", None)
        st.rerun()

    if cancel_col.button(
        "Yes, Cancel",
        key=f"staff_fu_cancel_confirm_{fu_id}",
        type="primary",
        use_container_width=True,
    ):
        result = cancel_follow_up(fu_id)

        if result.get("success"):
            remember("Follow-up cancelled.")
            st.session_state.pop("staff_fu_cancel_target", None)
            st.rerun()
        else:
            st.error(result.get("message", "Failed to cancel."))


# ============================================================
# PAGE
# ============================================================

def show():

    load_css("staff_css/followup.css")
    show_flash_message()

    role_id = current_role_id()

    if role_id not in (ROLE_STAFF, ROLE_HOSPITAL_ADMIN, ROLE_SUPERADMIN):
        st.error("You don't have access to Follow-Ups.")
        return

    with st.container(key="staff_followups_root"):

        page_header(
            "Follow-Ups",
            "Search and manage patient follow-up appointments.",
        )

        if st.session_state.get(KEY_SELECTED_FU):
            render_fu_detail()
        else:
            render_landing()

    # Dialog dispatcher
    if st.session_state.get("staff_fu_arrival_target"):
        show_confirm_arrival_dialog(
            st.session_state["staff_fu_arrival_target"]
        )

    elif st.session_state.get("staff_fu_parent_view"):
        show_parent_consult_dialog(
            st.session_state["staff_fu_parent_view"]
        )

    elif st.session_state.get("staff_fu_reschedule_target"):
        show_reschedule_dialog(
            st.session_state["staff_fu_reschedule_target"]
        )

    elif st.session_state.get("staff_fu_cancel_target"):
        show_cancel_dialog(
            st.session_state["staff_fu_cancel_target"]
        )