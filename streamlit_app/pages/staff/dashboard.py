
# ============================================================
# LUNGSIGHT AI - STAFF / NURSE DASHBOARD
# streamlit_app/pages/staff/dashboard.py
# ============================================================

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from backend.fetches import (
    get_hospital_patients,
    get_pending_examinations,
)

from backend.backend_utils.followup_utils import (
    get_hospital_follow_ups,
)

from streamlit_app.components.ui import (
    refresh_button,
    full_name,
    safe,
)

from shared.assets import load_css


MANILA_TZ = ZoneInfo("Asia/Manila")
ACTIVE_FOLLOW_UP_STATUSES = {"Scheduled", "Rescheduled"}


# ============================================================
# GENERAL HELPERS
# ============================================================

def current_hospital_id():
    user = st.session_state.get("user") or {}
    return user.get("hospital_id")


def navigate(page):
    st.session_state.current_page = page
    st.rerun()


def get_patient(row):
    patient = row.get("patients") or {}

    if isinstance(patient, list):
        return patient[0] if patient else {}

    return patient


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    ) or "Unknown Patient"


def to_manila_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        moment = value

    elif isinstance(value, date):
        return value

    else:
        try:
            moment = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return None

    if moment.tzinfo is None:
        # Database timestamps are expected to be UTC.
        # Do not use this for naive local timestamps.
        from datetime import timezone
        moment = moment.replace(tzinfo=timezone.utc)

    return moment.astimezone(MANILA_TZ).date()


def display_date(value):
    if not value:
        return "—"

    try:
        day = date.fromisoformat(str(value)[:10])
        return day.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return "—"


def display_time(value):
    if not value:
        return "—"

    try:
        return datetime.strptime(
            str(value)[:8],
            "%H:%M:%S",
        ).strftime("%I:%M %p")
    except (ValueError, TypeError):
        return str(value)


# ============================================================
# DASHBOARD DATA
# ============================================================

def load_dashboard_data(hospital_id):
    """
    Reuse existing fetch functions.

    No inserts, updates, deletes, or new backend modules.
    """

    patients = get_hospital_patients(hospital_id)

    examinations = get_pending_examinations(
        hospital_id=hospital_id
    )

    follow_ups = get_hospital_follow_ups(
        hospital_id=hospital_id
    )

    return {
        "patients": patients,
        "examinations": examinations,
        "follow_ups": follow_ups,
    }


def calculate_statistics(data):
    today = datetime.now(MANILA_TZ).date()

    patients = data["patients"]
    examinations = data["examinations"]
    follow_ups = data["follow_ups"]

    registered_today = sum(
        1
        for patient in patients
        if to_manila_date(patient.get("created_at")) == today
    )

    active_follow_ups = [
        row
        for row in follow_ups
        if row.get("status") in ACTIVE_FOLLOW_UP_STATUSES
    ]

    follow_ups_today = sum(
        1
        for row in active_follow_ups
        if str(row.get("follow_up_date") or "")[:10]
        == today.isoformat()
    )

    upcoming_follow_ups = [
        row
        for row in active_follow_ups
        if str(row.get("follow_up_date") or "")[:10]
        >= today.isoformat()
    ]

    upcoming_follow_ups.sort(
        key=lambda row: (
            str(row.get("follow_up_date") or ""),
            str(row.get("follow_up_time") or ""),
        )
    )

    return {
        "total_patients": len(patients),
        "registered_today": registered_today,
        "pending_examinations": len(examinations),
        "follow_ups_today": follow_ups_today,
        "upcoming_follow_ups": upcoming_follow_ups,
    }


# ============================================================
# DASHBOARD HEADER
# ============================================================

def dashboard_header():
    title_col, refresh_col = st.columns(
        [8, 0.7],
        vertical_alignment="center",
    )

    with title_col:
        st.markdown(
            """
            <div class="staff-db-header">
                <h1>Staff / Nurse Dashboard</h1>
                <p>
                    Manage patient registrations, monitor
                    examinations, and stay updated on follow-ups.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with refresh_col:
        # Keep your existing shared refresh button.
        refresh_button("staff_dashboard_refresh")


# ============================================================
# METRIC CARDS
# ============================================================

def metric_card(title, value, icon, tone):
    """Render a dashboard metric card without Markdown parsing issues."""

    html = (
        f'<div class="staff-db-metric staff-db-{safe(tone)}">'
        f'<div class="staff-db-metric-icon">'
        f'<span class="material-symbols-rounded">{safe(icon)}</span>'
        f'</div>'
        f'<div class="staff-db-metric-info">'
        f'<div class="staff-db-metric-label">{safe(title)}</div>'
        f'<div class="staff-db-metric-value">{value:,}</div>'
        f'</div>'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)


def metrics_section(stats):
    columns = st.columns(4, gap="small")

    metrics = [
        (
            "TOTAL PATIENTS",
            stats["total_patients"],
            "groups",
            "teal",
        ),
        (
            "REGISTERED TODAY",
            stats["registered_today"],
            "person_add",
            "green",
        ),
        (
            "PENDING EXAMINATIONS",
            stats["pending_examinations"],
            "assignment",
            "blue",
        ),
        (
            "FOLLOW-UPS TODAY",
            stats["follow_ups_today"],
            "event_available",
            "amber",
        ),
    ]

    for column, metric in zip(columns, metrics):
        with column:
            metric_card(*metric)


# ============================================================
# SECTION HEADINGS
# ============================================================

def section_heading(title, icon, subtitle=None):
    """Render a section heading with a properly formatted icon."""

    html = (
        '<div class="staff-db-section-title">'
        f'<span class="material-symbols-rounded">{safe(icon)}</span>'
        f'<span>{safe(title)}</span>'
        '</div>'
    )

    st.markdown(html, unsafe_allow_html=True)

    if subtitle:
        st.caption(subtitle)


# ============================================================
# PATIENT REGISTRATION CHART
# ============================================================

def registration_chart(patients):
    section_heading(
        "Patient Registrations",
        "trending_up",
        "New patient registrations over the last 7 days",
    )

    today = datetime.now(MANILA_TZ).date()

    days = [
        today - timedelta(days=offset)
        for offset in range(6, -1, -1)
    ]

    counts = {day: 0 for day in days}

    for patient in patients:
        created_day = to_manila_date(
            patient.get("created_at")
        )

        if created_day in counts:
            counts[created_day] += 1

    chart_data = pd.DataFrame(
        {
            "Registrations": [counts[day] for day in days]
        },
        index=pd.DatetimeIndex(days, name="Date"),
    )

    st.line_chart(
        chart_data,
        y="Registrations",
        color="#079CA5",
        height=245,
    )

    total_week = sum(counts.values())

    st.caption(
        f"{total_week} patient registration(s) "
        "in the last 7 days."
    )


# ============================================================
# PENDING EXAMINATIONS
# ============================================================

def examinations_section(examinations):
    section_heading(
        "Pending Examinations",
        "assignment",
        "Patients awaiting examination processing",
    )

    if not examinations:
        st.info("No pending examinations.")
    else:
        for examination in examinations[:4]:
            patient = get_patient(examination)

            name = patient_name(patient)

            code = (
                patient.get("patient_code")
                or "No patient ID"
            )

            examination_type = (
                examination.get("examination_type")
                or "General Examination"
            )

            with st.container(border=True):
                left, right = st.columns(
                    [3, 1],
                    vertical_alignment="center",
                )

                with left:
                    st.markdown(
                        f"**{safe(name)}**"
                    )
                    st.caption(
                        f"{code} · {examination_type}"
                    )

                with right:
                    st.markdown(
                        '<span class="staff-db-pending">'
                        'Pending</span>',
                        unsafe_allow_html=True,
                    )

    if st.button(
        "View All Examinations",
        key="staff_dashboard_examinations",
        icon=":material/arrow_forward:",
        width="stretch",
    ):
        navigate("Examinations")


# ============================================================
# UPCOMING FOLLOW-UPS
# ============================================================

def follow_ups_section(follow_ups):
    section_heading(
        "Upcoming Follow-Ups",
        "calendar_month",
        "Scheduled and rescheduled appointments",
    )

    if not follow_ups:
        st.info("No upcoming follow-up appointments.")
    else:
        for follow_up in follow_ups[:4]:
            patient = get_patient(follow_up)

            name = patient_name(patient)

            appointment_date = display_date(
                follow_up.get("follow_up_date")
            )

            appointment_time = display_time(
                follow_up.get("follow_up_time")
            )

            with st.container(border=True):
                left, right = st.columns(
                    [3, 2],
                    vertical_alignment="center",
                )

                with left:
                    st.markdown(
                        f"**{safe(name)}**"
                    )
                    st.caption(
                        follow_up.get("follow_up_code")
                        or "Follow-Up Appointment"
                    )

                with right:
                    st.markdown(
                        f"**{safe(appointment_date)}**"
                    )
                    st.caption(appointment_time)

    if st.button(
        "View All Follow-Ups",
        key="staff_dashboard_followups",
        icon=":material/arrow_forward:",
        width="stretch",
    ):
        navigate("Follow-Ups")


# ============================================================
# QUICK ACTIONS
# ============================================================

def quick_actions_section():
    section_heading(
        "Quick Actions",
        "bolt",
        "Frequently used staff functions",
    )

    actions = [
        (
            "Register Patient",
            "person_add",
            "Register Patient",
        ),
        (
            "Patient Records",
            "folder_shared",
            "Patient Records",
        ),
        (
            "Examinations",
            "assignment",
            "Examinations",
        ),
        (
            "Follow-Ups",
            "event_available",
            "Follow-Ups",
        ),
    ]

    for start in (0, 2):
        columns = st.columns(2, gap="small")

        for offset, column in enumerate(columns):
            label, icon, page = actions[start + offset]

            with column:
                if st.button(
                    label,
                    icon=f":material/{icon}:",
                    key=f"staff_quick_action_{start + offset}",
                    width="stretch",
                ):
                    navigate(page)


# ============================================================
# MAIN DASHBOARD
# ============================================================

def show():
    # Existing CSS loader
    load_css("staff_css/dashboard.css")

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    dashboard_header()

    # --------------------------------------------------------
    # HOSPITAL CONTEXT
    # --------------------------------------------------------

    hospital_id = current_hospital_id()

    if not hospital_id:
        st.error(
            "Your account has no assigned hospital. "
            "Please contact your administrator."
        )
        return

    # --------------------------------------------------------
    # FETCH DATA
    # --------------------------------------------------------

    try:
        with st.spinner("Loading dashboard..."):
            data = load_dashboard_data(hospital_id)
            stats = calculate_statistics(data)

    except Exception:
        st.error(
            "Unable to load dashboard data. "
            "Please try refreshing the page."
        )
        return

    # --------------------------------------------------------
    # METRIC CARDS
    # --------------------------------------------------------

    metrics_section(stats)

    st.write("")

    # --------------------------------------------------------
    # FIRST ROW
    # --------------------------------------------------------

    chart_col, examinations_col = st.columns(
        [1.15, 1],
        gap="medium",
    )

    with chart_col:
        with st.container(border=True):
            registration_chart(data["patients"])

    with examinations_col:
        with st.container(border=True):
            examinations_section(
                data["examinations"]
            )

    # --------------------------------------------------------
    # SECOND ROW
    # --------------------------------------------------------

    followups_col, actions_col = st.columns(
        [1.15, 1],
        gap="medium",
    )

    with followups_col:
        with st.container(border=True):
            follow_ups_section(
                stats["upcoming_follow_ups"]
            )

    with actions_col:
        with st.container(border=True):
            quick_actions_section()
