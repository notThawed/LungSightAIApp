
# ============================================================
# LUNGSIGHT AI — RADIOLOGY TECHNOLOGIST DASHBOARD
# streamlit_app/pages/radtech/dashboard.py
# ============================================================

from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from backend.fetches import (
    get_pending_xray_examinations,
    get_xray_ready_examinations,
    get_pending_xray_requests,
    convert_to_manila_time,
)

from shared.assets import load_css
from streamlit_app.components.ui import (
    refresh_button,
    full_name,
    safe,
)


MANILA_TZ = ZoneInfo("Asia/Manila")
UTC = timezone.utc

# These labels must match radtech_layout.py.
PAGE_QUEUE = "X-ray Queus"
PAGE_ANALYZE = "Analyze X-Ray"
PAGE_EXAMINATIONS = "Manage Examinations"
PAGE_RECORDS = "Patient Records"


# ============================================================
# AUTHENTICATED HOSPITAL CONTEXT
# ============================================================

def current_hospital_id():
    user = st.session_state.get("user") or {}

    # Never run unrestricted hospital queries.
    return user.get("hospital_id")


def navigate(page):
    st.session_state.current_page = page
    st.rerun()


# ============================================================
# DATE AND PATIENT HELPERS
# ============================================================

def parse_datetime(value):
    if not value:
        return None

    try:
        if isinstance(value, datetime):
            result = value
        else:
            result = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

        if result.tzinfo is None:
            result = result.replace(tzinfo=UTC)

        return result.astimezone(MANILA_TZ)

    except (TypeError, ValueError):
        return None


def format_datetime(value):
    moment = parse_datetime(value)

    if not moment:
        return "—"

    return moment.strftime("%b %d, %Y · %I:%M %p")


def waiting_minutes(value):
    moment = parse_datetime(value)

    if not moment:
        return None

    now = datetime.now(MANILA_TZ)

    return max(
        0,
        int((now - moment).total_seconds() // 60),
    )


def format_wait(minutes):
    if minutes is None:
        return "—"

    hours, remainder = divmod(minutes, 60)

    if hours:
        return f"{hours}h {remainder}m"

    return f"{remainder} min"


def get_patient(record):
    patient = record.get("patients") or {}

    if isinstance(patient, list):
        return patient[0] if patient else {}

    return patient


def patient_name(patient):
    return full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    ) or "Unknown patient"


# ============================================================
# LOAD EXISTING BACKEND DATA
# ============================================================

def load_dashboard_data(hospital_id):
    """
    Reuse existing backend/fetches.py functions.

    No additional backend module or database writes.
    """

    awaiting = get_pending_xray_examinations(
        hospital_id=hospital_id
    )

    ready = get_xray_ready_examinations(
        hospital_id=hospital_id
    )

    requests = get_pending_xray_requests(
        hospital_id=hospital_id
    )

    # Additional defensive check on the returned request data.
    requests = [
        row for row in requests
        if str(row.get("hospital_id")) == str(hospital_id)
    ]

    return {
        "awaiting": awaiting,
        "ready": ready,
        "requests": requests,
    }


# ============================================================
# METRIC CARDS
# ============================================================

def metric_card(title, value, icon, tone, subtitle=""):
    """
    Build HTML without indentation to prevent Streamlit
    from displaying HTML as Markdown code.
    """

    html = (
        f'<div class="rd-metric rd-{safe(tone)}">'
        '<div class="rd-metric-icon">'
        f'<span class="material-symbols-rounded">{safe(icon)}</span>'
        '</div>'
        '<div class="rd-metric-content">'
        f'<div class="rd-metric-label">{safe(title)}</div>'
        f'<div class="rd-metric-value">{safe(value)}</div>'
        f'<div class="rd-metric-subtitle">{safe(subtitle)}</div>'
        '</div>'
        '</div>'
    )

    st.markdown(html, unsafe_allow_html=True)


def render_metrics(data):
    awaiting = data["awaiting"]
    ready = data["ready"]
    requests = data["requests"]

    waits = [
        minutes
        for row in requests
        if (
            minutes := waiting_minutes(
                row.get("requested_at")
            )
        ) is not None
    ]

    longest_wait = max(waits) if waits else None

    cards = [
        (
            "PENDING X-RAY REQUESTS",
            len(requests),
            "assignment",
            "teal",
            "Requests awaiting action",
        ),
        (
            "AWAITING X-RAY",
            len(awaiting),
            "radiology",
            "green",
            "Examinations awaiting imaging",
        ),
        (
            "X-RAY READY",
            len(ready),
            "check_circle",
            "blue",
            "Ready examinations",
        ),
        (
            "LONGEST REQUEST WAIT",
            format_wait(longest_wait),
            "schedule",
            "amber",
            "Oldest pending request",
        ),
    ]

    columns = st.columns(4, gap="small")

    for column, card in zip(columns, cards):
        with column:
            metric_card(*card)


# ============================================================
# SECTION HEADING
# ============================================================

def section_heading(title, icon, subtitle=None):
    html = (
        '<div class="rd-section-heading">'
        f'<span class="material-symbols-rounded">{safe(icon)}</span>'
        f'<span>{safe(title)}</span>'
        '</div>'
    )

    st.markdown(html, unsafe_allow_html=True)

    if subtitle:
        st.caption(subtitle)


# ============================================================
# X-RAY REQUEST QUEUE
# ============================================================

def render_request_queue(requests):
    section_heading(
        "X-Ray Request Queue",
        "clinical_notes",
        "Pending requests, ordered by request time.",
    )

    if not requests:
        st.info("No pending X-ray requests.")
    else:
        ordered = sorted(
            requests,
            key=lambda row: (
                parse_datetime(row.get("requested_at"))
                or datetime.max.replace(tzinfo=MANILA_TZ)
            ),
        )

        header = (
            '<div class="rd-table-header">'
            '<span>Patient</span>'
            '<span>Body Part</span>'
            '<span>Waiting</span>'
            '<span>Priority</span>'
            '</div>'
        )
        st.markdown(header, unsafe_allow_html=True)

        for request in ordered[:5]:
            patient = get_patient(request)

            name = patient_name(patient)
            code = patient.get("patient_code") or "—"

            body_part = request.get("body_part") or "—"
            priority = request.get("priority") or "—"

            wait = format_wait(
                waiting_minutes(request.get("requested_at"))
            )

            html = (
                '<div class="rd-table-row">'
                '<div class="rd-patient">'
                f'<strong>{safe(name)}</strong>'
                f'<small>{safe(code)}</small>'
                '</div>'
                f'<span>{safe(body_part)}</span>'
                f'<span>{safe(wait)}</span>'
                '<div>'
                f'<span class="rd-priority">{safe(priority)}</span>'
                '</div>'
                '</div>'
            )

            st.markdown(html, unsafe_allow_html=True)

    if st.button(
        "View Full X-Ray Queue",
        key="rd_view_queue",
        icon=":material/arrow_forward:",
        width="stretch",
    ):
        navigate(PAGE_QUEUE)


# ============================================================
# REQUEST ACTIVITY CHART
# ============================================================

def render_activity_chart(requests):
    section_heading(
        "X-Ray Request Activity",
        "monitoring",
        "Pending requests created during the last 7 days.",
    )

    today = datetime.now(MANILA_TZ).date()

    days = [
        today - timedelta(days=offset)
        for offset in range(6, -1, -1)
    ]

    counts = Counter()

    for request in requests:
        moment = parse_datetime(
            request.get("requested_at")
        )

        if moment:
            counts[moment.date()] += 1

    chart = pd.DataFrame(
        {
            "Requests": [
                counts.get(day, 0)
                for day in days
            ]
        },
        index=pd.DatetimeIndex(days, name="Date"),
    )

    st.line_chart(
        chart,
        y="Requests",
        color="#079CA5",
        height=250,
    )

    st.caption(
        "This chart shows currently pending requests "
        "by request date, not all historical X-ray activity."
    )


# ============================================================
# READY EXAMINATIONS
# ============================================================

def render_ready_examinations(examinations):
    section_heading(
        "X-Ray Ready Examinations",
        "task_alt",
        "Examinations currently marked X-Ray Ready.",
    )

    if not examinations:
        st.info("No examinations currently marked X-Ray Ready.")

    else:
        for examination in examinations[:4]:
            patient = get_patient(examination)

            name = patient_name(patient)
            code = patient.get("patient_code") or "—"

            with st.container(border=True):
                left, right = st.columns(
                    [3, 1],
                    vertical_alignment="center",
                )

                with left:
                    st.markdown(f"**{safe(name)}**")
                    st.caption(
                        f"{code} · "
                        f"{examination.get('examination_type') or 'Examination'}"
                    )

                with right:
                    st.markdown(
                        '<span class="rd-ready-badge">'
                        'X-Ray Ready</span>',
                        unsafe_allow_html=True,
                    )

    if st.button(
        "View Examinations",
        key="rd_view_examinations",
        icon=":material/arrow_forward:",
        width="stretch",
    ):
        navigate(PAGE_EXAMINATIONS)


# ============================================================
# QUICK ACTIONS
# ============================================================

def render_quick_actions():
    section_heading(
        "Quick Actions",
        "bolt",
        "Frequently used radiology tools.",
    )

    actions = [
        ("X-Ray Queue", "list_alt", PAGE_QUEUE),
        ("Analyze X-Ray", "radiology", PAGE_ANALYZE),
        ("Examinations", "assignment", PAGE_EXAMINATIONS),
        ("Patient Records", "folder_shared", PAGE_RECORDS),
    ]

    for start in (0, 2):
        columns = st.columns(2, gap="small")

        for offset, column in enumerate(columns):
            label, icon, page = actions[start + offset]

            with column:
                if st.button(
                    label,
                    icon=f":material/{icon}:",
                    key=f"rd_action_{start + offset}",
                    width="stretch",
                ):
                    navigate(page)


# ============================================================
# MAIN DASHBOARD
# ============================================================

def show():
    load_css("radtech_css/dashboard.css")

    user = st.session_state.get("user") or {}

    # RadTech role ID is defined in the existing role modules.
    if str(user.get("role_id")) != "4":
        st.error(
            "You do not have access to the "
            "Radiology Technologist Dashboard."
        )
        return

    hospital_id = current_hospital_id()

    if not hospital_id:
        st.error(
            "Your account has no assigned hospital. "
            "Please contact your administrator."
        )
        return

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    title_col, refresh_col = st.columns(
        [8, 0.7],
        vertical_alignment="center",
    )

    with title_col:
        st.markdown(
            '<div class="rd-header">'
            '<h1>Radiology Technologist Dashboard</h1>'
            '<p>Imaging workflow and X-ray request overview.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    with refresh_col:
        refresh_button("radtech_dashboard_refresh")

    # --------------------------------------------------------
    # FETCH DATA
    # --------------------------------------------------------

    try:
        with st.spinner("Loading radiology dashboard..."):
            data = load_dashboard_data(hospital_id)

    except Exception:
        st.error(
            "Unable to load the radiology dashboard. "
            "Please try refreshing the page."
        )
        return

    # --------------------------------------------------------
    # METRIC CARDS
    # --------------------------------------------------------

    render_metrics(data)

    st.write("")

    # --------------------------------------------------------
    # FIRST ROW
    # --------------------------------------------------------

    queue_col, chart_col = st.columns(
        [1.15, 1],
        gap="medium",
    )

    with queue_col:
        with st.container(border=True):
            render_request_queue(data["requests"])

    with chart_col:
        with st.container(border=True):
            render_activity_chart(data["requests"])

    # --------------------------------------------------------
    # SECOND ROW
    # --------------------------------------------------------

    ready_col, actions_col = st.columns(
        [1.15, 1],
        gap="medium",
    )

    with ready_col:
        with st.container(border=True):
            render_ready_examinations(data["ready"])

    with actions_col:
        with st.container(border=True):
            render_quick_actions()
