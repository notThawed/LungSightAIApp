
"""Hospital Administrator dashboard — hospital-scoped operational overview."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from backend.fetches import get_hospital_staff
from backend.backend_utils.subscription_usage import (
    get_hospital_subscription,
    get_remaining_usage,
)
from backend.supabase_client import admin_supabase
from streamlit_app.components.ui import refresh_button


# ============================================================
# CONFIGURATION
# ============================================================

CSS_PATH = (
    Path(__file__).resolve().parents[3]
    / "shared/theme/css_content/hospital_admin_css/dashboard.css"
)

# Existing sidebar page keys.
ACTIONS = (
    ("Manage Staff", "Manage Users", "groups", "mint"),
    ("Patient Records", "Manage Patients", "folder_shared", "blue"),
    ("Subscriptions", "Subscription Usage", "workspace_premium", "gold"),
    ("Reports", "Hospital Reports", "bar_chart", "violet"),
)


# ============================================================
# SVG ICONS
# ============================================================

ICONS = {
    "users": (
        '<circle cx="9" cy="8" r="3"/>'
        '<path d="M3 20v-2a6 6 0 0 1 12 0v2"/>'
        '<circle cx="18" cy="9" r="2"/>'
        '<path d="M17 15a4 4 0 0 1 4 4v1"/>'
    ),
    "patients": (
        '<circle cx="12" cy="7" r="4"/>'
        '<path d="M4 21v-2a8 8 0 0 1 16 0v2"/>'
    ),
    "staff": (
        '<path d="M8 3v6a4 4 0 0 0 8 0V3M6 3h4m4 0h4"/>'
        '<path d="M12 13v2a5 5 0 0 0 10 0v-1"/>'
        '<circle cx="22" cy="12" r="1"/>'
    ),
    "exam": (
        '<rect x="3" y="3" width="18" height="18" rx="4"/>'
        '<circle cx="12" cy="12" r="5"/>'
        '<path d="M9 12h6m-3-3v6"/>'
    ),
    "brain": (
        '<path d="M12 5a4 4 0 0 0-7 2 4 4 0 0 0-1 7"/>'
        '<path d="M4 14a4 4 0 0 0 5 6l3-2"/>'
        '<path d="M12 5a4 4 0 0 1 7 2 4 4 0 0 1 1 7"/>'
        '<path d="M20 14a4 4 0 0 1-5 6l-3-2"/>'
        '<path d="M12 5v13M8 9l4 3m4-3-4 3"/>'
    ),
    "chart": (
        '<path d="M4 20V9h4v11M10 20V4h4v16M16 20v-8h4v8"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M12 7v5l4 2"/>'
    ),
    "layers": (
        '<path d="m12 3 9 5-9 5-9-5 9-5Z"/>'
        '<path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>'
    ),
    "bolt": (
        '<path d="M13 2 5 13h6l-1 9 9-12h-6z"/>'
    ),
    "crown": (
        '<path d="m2 7 5 5 5-8 5 8 5-5-2 13H4L2 7Z"/>'
    ),
    "check": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="m7 12 3 3 7-7"/>'
    ),
}


# ============================================================
# HELPERS
# ============================================================

def _safe(value):
    """Escape values before rendering HTML."""

    return escape(
        str(value if value is not None else ""),
        quote=True,
    )


def _icon(name, cls="had-icon"):
    """Return a self-contained SVG icon."""

    return (
        f'<svg class="{cls}" '
        'viewBox="0 0 24 24" '
        'fill="none" '
        'stroke="currentColor" '
        'stroke-width="1.8" '
        'stroke-linecap="round" '
        'stroke-linejoin="round" '
        'aria-hidden="true">'
        f'{ICONS.get(name, ICONS["chart"])}'
        '</svg>'
    )


def _date(value):
    """Convert a date or timestamp into a date object."""

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).date()

    except (TypeError, ValueError):
        return None


def _staff_role(member):
    """Get a staff member's role name."""

    role = member.get("roles") or {}

    if isinstance(role, list):
        role = role[0] if role else {}

    if isinstance(role, dict):
        return str(
            role.get("role_name") or "Other"
        )

    return "Other"


def _go(page):
    """Navigate using the existing sidebar page state."""

    st.session_state.current_page = page
    st.rerun()


# ============================================================
# DATA FETCHING
# ============================================================

def _hospital_examinations(hospital_id):
    """
    Fetch examinations linked to patients
    belonging to the current hospital.
    """

    response = (
        admin_supabase
        .table("examinations")
        .select(
            "examination_id,"
            "examination_date,"
            "created_at,"
            "status,"
            "patients!inner(hospital_id)"
        )
        .eq("patients.hospital_id", hospital_id)
        .execute()
    )

    return response.data or []


# ============================================================
# DASHBOARD COMPONENTS
# ============================================================

def _heading(icon, title, subtitle):
    """Render a panel heading."""

    html = (
        '<div class="had-panel-heading">'
        f'{_icon(icon, "had-heading-icon")}'
        '<div class="had-panel-heading-text">'
        f'<strong>{_safe(title)}</strong>'
        f'<span>{_safe(subtitle)}</span>'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def _metric(label, value, icon, tone, note):
    """Render one KPI card."""

    html = (
        f'<div class="had-metric had-{tone}">'
        '<div class="had-metric-icon">'
        f'{_icon(icon)}'
        '</div>'
        '<div class="had-metric-body">'
        f'<div class="had-metric-label">{_safe(label)}</div>'
        f'<div class="had-metric-value">{int(value):,}</div>'
        f'<div class="had-metric-note">{_safe(note)}</div>'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


# ============================================================
# EXAMINATIONS OVERVIEW
# ============================================================

def _exam_chart(examinations):
    """Show examination activity over the last seven days."""

    today = datetime.now(timezone.utc).date()

    days = [
        today - timedelta(days=6 - offset)
        for offset in range(7)
    ]

    counts = Counter(
        _date(
            item.get("examination_date")
            or item.get("created_at")
        )
        for item in examinations
    )

    data = pd.DataFrame(
        {
            "Day": [
                day.strftime("%b %d")
                for day in days
            ],
            "Examinations": [
                counts.get(day, 0)
                for day in days
            ],
        }
    ).set_index("Day")

    st.area_chart(
        data,
        color="#00a5a9",
        height=222,
    )


# ============================================================
# STAFF DISTRIBUTION
# ============================================================

def _staff_donut(staff):
    """Show active hospital staff grouped by role."""

    counts = Counter(
        _staff_role(person)
        for person in staff
    )

    if not counts:
        st.info("No active staff accounts found.")
        return

    try:
        import plotly.graph_objects as go

    except ImportError:
        data = pd.DataFrame(
            {
                "Role": list(counts),
                "Staff": list(counts.values()),
            }
        ).set_index("Role")

        st.bar_chart(
            data,
            height=220,
        )
        return

    colors = [
        "#00a7ad",
        "#258ef6",
        "#9054ed",
        "#d5d8dd",
        "#f3a32e",
    ]

    fig = go.Figure(
        go.Pie(
            labels=list(counts),
            values=list(counts.values()),
            hole=0.69,
            sort=False,
            marker={"colors": colors},
            textinfo="none",
            hovertemplate=(
                "%{label}: %{value} (%{percent})"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=205,
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=[
            dict(
                text=f"<b>{len(staff)}</b><br>Staff",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(
                    size=19,
                    color="#101a3c",
                ),
            )
        ],
    )

    chart_col, legend_col = st.columns(
        [1.1, 1],
        vertical_alignment="center",
    )

    with chart_col:
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": False,
            },
        )

    with legend_col:
        for index, (role, count) in enumerate(
            counts.most_common()
        ):
            color = colors[index % len(colors)]
            percentage = 100 * count / len(staff)

            html = (
                '<div class="had-legend-row">'
                f'<span class="had-legend-dot" '
                f'style="background:{color}"></span>'
                f'<span>{_safe(role)}</span>'
                f'<b>{count} ({percentage:.1f}%)</b>'
                '</div>'
            )

            st.markdown(
                html,
                unsafe_allow_html=True,
            )


# ============================================================
# SUBSCRIPTION USAGE
# ============================================================

def _subscription(subscription, usage):
    """Show the current subscription and resource usage."""

    plan = (
        (subscription or {}).get("plan")
        or {}
    )

    name = (
        plan.get("plan_name")
        or "No active plan"
    )

    html = (
        '<div class="had-plan">'
        f'{_icon("crown")}'
        '<div>'
        f'<strong>{_safe(name)}</strong>'
        '<span>Current hospital subscription</span>'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )

    usage_items = (
        ("xrays", "X-ray usage this month"),
        ("users", "Active users"),
        ("patients", "Patients"),
    )

    for key, label in usage_items:
        item = usage.get(key) or {}

        used = int(
            item.get("used") or 0
        )

        limit = item.get("limit")

        unlimited = (
            bool(item.get("unlimited", False))
            or limit is None
        )

        if unlimited:
            display = f"{used:,} / Unlimited"
            fraction = 0.0

        else:
            limit = max(
                int(limit),
                0,
            )

            display = f"{used:,} / {limit:,}"

            fraction = (
                min(used / limit, 1.0)
                if limit
                else 0.0
            )

        html = (
            '<div class="had-usage-label">'
            f'<span>{_safe(label)}</span>'
            f'<b>{_safe(display)}</b>'
            '</div>'
        )

        st.markdown(
            html,
            unsafe_allow_html=True,
        )

        st.progress(fraction)

    st.caption(
        "X-ray usage is not necessarily the number "
        "of AI screening results."
    )


# ============================================================
# RECENT HOSPITAL ACTIVITY
# ============================================================

def _activity(examinations):
    """
    Show current examination status totals.

    This is not an audit timeline because the available
    examination query does not provide audit events.
    """

    counts = Counter(
        str(
            row.get("status") or "Unspecified"
        )
        for row in examinations
    )

    if not counts:
        st.info(
            "No examination activity available yet."
        )
        return

    for status, count in counts.most_common(4):
        html = (
            '<div class="had-activity-row">'
            '<span class="had-activity-mark"></span>'
            f'<strong>{_safe(status.title())}</strong>'
            f'<span>{count:,} examination(s)</span>'
            '</div>'
        )

        st.markdown(
            html,
            unsafe_allow_html=True,
        )

    st.caption(
        "Current examination status totals, "
        "not an audit timeline."
    )


# ============================================================
# MAIN DASHBOARD
# ============================================================

def show():

    # --------------------------------------------------------
    # LOAD CSS
    # --------------------------------------------------------

    if not CSS_PATH.is_file():
        st.error(
            f"Dashboard CSS file missing: {CSS_PATH}"
        )
        return

    st.markdown(
        "<style>"
        + CSS_PATH.read_text(encoding="utf-8")
        + "</style>",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # GET CURRENT HOSPITAL
    # --------------------------------------------------------

    user = (
        st.session_state.get("user")
        or {}
    )

    hospital_id = user.get("hospital_id")

    if not hospital_id:
        st.error(
            "Your account is not assigned to a hospital."
        )
        return

    # --------------------------------------------------------
    # FETCH DATA
    # --------------------------------------------------------

    try:
        usage = (
            get_remaining_usage(hospital_id)
            or {}
        )

        subscription = get_hospital_subscription(
            hospital_id
        )

        staff = (
            get_hospital_staff(
                hospital_id,
                active_only=True,
            )
            or []
        )

        examinations = _hospital_examinations(
            hospital_id
        )

    except Exception:
        st.error(
            "Unable to load hospital dashboard data. "
            "Try refreshing or contact support."
        )
        return

    # --------------------------------------------------------
    # CALCULATE METRICS
    # --------------------------------------------------------

    patient_count = int(
        (usage.get("patients") or {}).get("used")
        or 0
    )

    pending_count = sum(
        str(
            row.get("status") or ""
        ).strip().lower() == "pending"
        for row in examinations
    )

    completed_count = sum(
        str(
            row.get("status") or ""
        ).strip().lower() in {
            "completed",
            "complete",
        }
        for row in examinations
    )

    xray_count = int(
        (usage.get("xrays") or {}).get("used")
        or 0
    )

    # --------------------------------------------------------
    # DASHBOARD LAYOUT
    # --------------------------------------------------------

    with st.container(key="had_dashboard"):

        # ----------------------------------------------------
        # HERO BANNER
        # ----------------------------------------------------

        st.markdown(
            '<div class="had-hero">'
            '<div class="had-hero-kicker">'
            'HOSPITAL ADMINISTRATOR DASHBOARD'
            '</div>'
            '<h1>Hospital Operations Center</h1>'
            '<p>'
            'Monitor hospital activities, manage personnel, '
            'and oversee LungSightAI usage.'
            '</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # KPI CARDS
        # ----------------------------------------------------

        metrics = st.columns(
            4,
            gap="small",
        )

        cards = (
            (
                "Total Patients",
                patient_count,
                "users",
                "teal",
                "Registered patients",
            ),
            (
                "Active Staff",
                len(staff),
                "staff",
                "blue",
                "Active hospital accounts",
            ),
            (
                "Total Examinations",
                len(examinations),
                "exam",
                "orange",
                "Recorded examinations",
            ),
            (
                "X-ray Usage",
                xray_count,
                "brain",
                "purple",
                "Images this month",
            ),
        )

        for col, card in zip(metrics, cards):
            with col:
                _metric(*card)

        # ----------------------------------------------------
        # EXAMINATIONS AND STAFF DISTRIBUTION
        # ----------------------------------------------------

        first_left, first_right = st.columns(
            [1.65, 1.2],
            gap="small",
        )

        with first_left:
            with st.container(
                key="had_exam_panel",
                border=True,
            ):
                _heading(
                    "chart",
                    "Examinations Overview",
                    "Number of examinations over the last 7 days",
                )

                graph, summary = st.columns(
                    [3.1, 1.15],
                    gap="small",
                    vertical_alignment="center",
                )

                with graph:
                    _exam_chart(examinations)

                with summary:
                    pending_html = (
                        '<div class="had-status had-status-pending">'
                        f'{_icon("clock")}'
                        '<span>'
                        'Pending'
                        f'<strong>{pending_count:,}</strong>'
                        '</span>'
                        '</div>'
                    )

                    st.markdown(
                        pending_html,
                        unsafe_allow_html=True,
                    )

                    completed_html = (
                        '<div class="had-status had-status-done">'
                        f'{_icon("check")}'
                        '<span>'
                        'Completed'
                        f'<strong>{completed_count:,}</strong>'
                        '</span>'
                        '</div>'
                    )

                    st.markdown(
                        completed_html,
                        unsafe_allow_html=True,
                    )

        with first_right:
            with st.container(
                key="had_staff_panel",
                border=True,
            ):
                _heading(
                    "users",
                    "Staff Distribution",
                    "Hospital staff by role",
                )

                _staff_donut(staff)

        # ----------------------------------------------------
        # BOTTOM PANELS
        # ----------------------------------------------------

        bottom_left, bottom_mid, bottom_right = st.columns(
            [1, 1.15, 1.15],
            gap="small",
        )

        # SUBSCRIPTION USAGE

        with bottom_left:
            with st.container(
                key="had_subscription_panel",
                border=True,
            ):
                _heading(
                    "layers",
                    "Subscription Usage",
                    "Current plan and resource usage",
                )

                _subscription(
                    subscription,
                    usage,
                )

        # RECENT HOSPITAL ACTIVITY

        with bottom_mid:
            with st.container(
                key="had_activity_panel",
                border=True,
            ):
                _heading(
                    "clock",
                    "Recent Hospital Activity",
                    "Current examination workflow snapshot",
                )

                _activity(examinations)

        # QUICK ACTIONS

        with bottom_right:
            with st.container(
                key="had_actions_panel",
                border=True,
            ):
                _heading(
                    "bolt",
                    "Quick Actions",
                    "Common administrative tasks",
                )

                with st.container(
                    key="had_quick_actions"
                ):
                    row1 = st.columns(
                        2,
                        gap="small",
                    )

                    row2 = st.columns(
                        2,
                        gap="small",
                    )

                    action_columns = [
                        *row1,
                        *row2,
                    ]

                    for col, (
                        label,
                        page,
                        icon,
                        tone,
                    ) in zip(action_columns, ACTIONS):

                        with col:
                            if st.button(
                                label,
                                icon=f":material/{icon}:",
                                key=f"had_action_{page}",
                                width="stretch",
                            ):
                                _go(page)

        # ----------------------------------------------------
        # REFRESH BUTTON
        # ----------------------------------------------------

        with st.container(
            key="had_footer_refresh"
        ):
            refresh_button(
                "hospital_admin_dashboard_refresh"
            )
