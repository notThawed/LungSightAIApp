
"""
LungSightAI — System Administrator Dashboard

System-wide hospital monitoring, examination activity,
user overview, and administrative quick actions.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
import importlib
from pathlib import Path

import pandas as pd
import streamlit as st

from backend.fetches import (
    get_all_hospitals,
    get_all_users,
)
from backend.supabase_client import admin_supabase
from streamlit_app.components.ui import refresh_button


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

CSS_PATH = (
    PROJECT_ROOT
    / "shared"
    / "theme"
    / "css_content"
    / "system_admin_css"
    / "dashboard.css"
)

PH_TIMEZONE = timezone(timedelta(hours=8))

# These are actual page keys from ADMIN_NAV in sidebar.py.
QUICK_ACTIONS = [
    {
        "label": "Manage Hospitals",
        "page": "Manage Hospitals",
        "icon": "local_hospital",
        "tone": "green",
    },
    {
        "label": "Manage Users",
        "page": "User Management",
        "icon": "groups",
        "tone": "blue",
    },
    {
        "label": "Subscriptions",
        "page": "Manage Subscriptions",
        "icon": "credit_card",
        "tone": "orange",
    },
    {
        "label": "Platform Reports",
        "page": "Reports",
        "icon": "bar_chart",
        "tone": "purple",
    },
]


# ============================================================
# SVG ICONS
# ============================================================

SVG_PATHS = {
    "hospital": (
        '<rect x="4" y="3" width="16" height="18" rx="2"/>'
        '<path d="M9 21v-5h6v5"/>'
        '<path d="M9 7h6M12 4v6M7 13h2m6 0h2"/>'
    ),
    "users": (
        '<circle cx="9" cy="8" r="3"/>'
        '<path d="M3 20v-2a6 6 0 0 1 12 0v2"/>'
        '<circle cx="18" cy="9" r="2"/>'
        '<path d="M17 15a4 4 0 0 1 4 4"/>'
    ),
    "exam": (
        '<rect x="5" y="4" width="14" height="17" rx="2"/>'
        '<path d="M9 4V2h6v2M9 10h6m-6 4h6m-6 4h4"/>'
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
    "pulse": (
        '<path d="M2 12h4l3-7 5 14 3-7h5"/>'
    ),
    "bolt": (
        '<path d="M13 2 5 13h6l-1 9 9-12h-6z"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M3 5v14c0 4 18 4 18 0V5"/>'
        '<path d="M3 12c0 4 18 4 18 0"/>'
    ),
    "layers": (
        '<path d="m12 3 9 5-9 5-9-5 9-5Z"/>'
        '<path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>'
    ),
    "check": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="m7 12 3 3 7-7"/>'
    ),
}


def svg_icon(name, class_name="sad-svg"):
    """Render an SVG without relying on icon fonts."""

    paths = SVG_PATHS.get(
        name,
        SVG_PATHS["chart"],
    )

    return (
        f'<svg class="{class_name}" '
        'viewBox="0 0 24 24" '
        'fill="none" '
        'stroke="currentColor" '
        'stroke-width="1.8" '
        'stroke-linecap="round" '
        'stroke-linejoin="round" '
        'aria-hidden="true">'
        f'{paths}'
        '</svg>'
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def safe(value):
    """Escape text before inserting it into HTML."""

    if value is None:
        return "—"

    return escape(str(value), quote=True)


def parse_datetime(value):
    """Convert a database timestamp to a timezone-aware datetime."""

    if not value:
        return None

    try:
        moment = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)

        return moment.astimezone(PH_TIMEZONE)

    except (TypeError, ValueError):
        return None


def format_datetime(value):
    """Format a timestamp for the activity panel."""

    moment = parse_datetime(value)

    if moment is None:
        return "Date unavailable"

    return moment.strftime("%b %d, %Y · %I:%M %p")


def navigate(page):
    """Navigate through the existing sidebar page state."""

    st.session_state.current_page = page
    st.rerun()


def load_dashboard_css():
    """Load the dedicated system dashboard stylesheet."""

    if not CSS_PATH.is_file():
        st.error(
            "System dashboard stylesheet was not found."
        )
        return False

    css = CSS_PATH.read_text(encoding="utf-8")

    st.markdown(
        "<style>" + css + "</style>",
        unsafe_allow_html=True,
    )

    return True


# ============================================================
# READ-ONLY DASHBOARD DATA
# ============================================================

def fetch_dashboard_data():
    """
    Reuse existing fetch utilities.

    Examination data uses read-only queries with pagination.
    Each result is system-wide and is intended only for the
    authenticated System Administrator page.
    """

    hospitals = get_all_hospitals() or []
    users = get_all_users() or []

    examinations = []

    # Supabase/PostgREST commonly limits rows per request.
    # Pagination prevents silently displaying only 1,000 rows.
    page_size = 500
    start = 0

    while True:
        response = (
            admin_supabase
            .table("examinations")
            .select(
                "examination_id,"
                "patient_id,"
                "examination_date,"
                "created_at,"
                "status,"
                "patients(hospital_id)"
            )
            .order(
                "created_at",
                desc=True,
            )
            .range(
                start,
                start + page_size - 1,
            )
            .execute()
        )

        batch = response.data or []

        examinations.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

    return {
        "hospitals": hospitals,
        "users": users,
        "examinations": examinations,
    }


# ============================================================
# DATA CALCULATIONS
# ============================================================

def calculate_metrics(data):
    """Calculate verified values from retrieved records."""

    hospitals = data["hospitals"]
    users = data["users"]
    examinations = data["examinations"]

    active_users = sum(
        user.get("is_active") is True
        for user in users
    )

    active_hospitals = sum(
        hospital.get("is_active") is True
        for hospital in hospitals
    )

    return {
        "total_hospitals": len(hospitals),
        "active_hospitals": active_hospitals,
        "active_users": active_users,
        "total_examinations": len(examinations),
    }


def examination_trends(examinations):
    """Calculate examination totals over the last seven days."""

    today = datetime.now(PH_TIMEZONE).date()

    days = [
        today - timedelta(days=6 - offset)
        for offset in range(7)
    ]

    counts = Counter()

    for examination in examinations:
        moment = parse_datetime(
            examination.get("created_at")
            or examination.get("examination_date")
        )

        if moment:
            counts[moment.date()] += 1

    return pd.DataFrame(
        {
            "Date": [
                day.strftime("%b %d")
                for day in days
            ],
            "Examinations": [
                counts.get(day, 0)
                for day in days
            ],
        }
    ).set_index("Date")


def examinations_by_hospital(hospitals, examinations):
    """Group examinations using their associated patient hospital."""

    hospital_names = {
        str(hospital.get("hospital_id")): (
            hospital.get("hospital_name")
            or "Unnamed Hospital"
        )
        for hospital in hospitals
    }

    counts = Counter()

    for examination in examinations:
        patient = examination.get("patients") or {}

        if isinstance(patient, list):
            patient = patient[0] if patient else {}

        hospital_id = patient.get("hospital_id")

        if hospital_id:
            name = hospital_names.get(
                str(hospital_id),
                "Unknown Hospital",
            )
        else:
            name = "Unassigned"

        counts[name] += 1

    return counts


# ============================================================
# HERO BANNER
# ============================================================

def render_hero():

    html = (
        '<div class="sad-hero">'
        '<div class="sad-hero-content">'
        '<div class="sad-hero-kicker">'
        'SYSTEM ADMINISTRATOR DASHBOARD'
        '</div>'
        '<h1>System Control Center</h1>'
        '<p>'
        'System-wide overview, platform health, and '
        'administrative controls for LungSightAI.'
        '</p>'
        '</div>'
        '<div class="sad-hero-art" aria-hidden="true">'
        '<div class="sad-hero-orbit"></div>'
        f'{svg_icon("brain", "sad-hero-brain")}'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


# ============================================================
# KPI CARDS
# ============================================================

def render_metric(label, value, icon, tone, caption):

    display_value = (
        f"{value:,}"
        if isinstance(value, int)
        else str(value)
    )

    html = (
        f'<div class="sad-metric sad-metric-{tone}">'
        '<div class="sad-metric-icon">'
        f'{svg_icon(icon)}'
        '</div>'
        '<div class="sad-metric-content">'
        f'<div class="sad-metric-label">{safe(label)}</div>'
        f'<div class="sad-metric-value">{safe(display_value)}</div>'
        f'<div class="sad-metric-caption">{safe(caption)}</div>'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


# ============================================================
# PANEL HEADINGS
# ============================================================

def render_panel_heading(icon, title, subtitle):

    html = (
        '<div class="sad-panel-heading">'
        f'{svg_icon(icon, "sad-panel-icon")}'
        '<div class="sad-panel-text">'
        f'<strong>{safe(title)}</strong>'
        f'<span>{safe(subtitle)}</span>'
        '</div>'
        '</div>'
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


# ============================================================
# HOSPITAL ACTIVITY CHART
# ============================================================

def render_activity_chart(examinations):

    data = examination_trends(examinations)

    st.area_chart(
        data,
        color="#00a6aa",
        height=240,
    )

    today = datetime.now(PH_TIMEZONE).date()

    registrations_today = sum(
        (
            parse_datetime(user.get("created_at")) or
            datetime.min.replace(tzinfo=PH_TIMEZONE)
        ).date() == today
        for user in []
    )

    # The UI only displays values supported by the data.
    # Patient registration counts are not inferred from users.

    st.caption(
        "Daily examination records across all hospitals."
    )


# ============================================================
# EXAMINATIONS BY HOSPITAL
# ============================================================

def render_hospital_distribution(hospitals, examinations):

    counts = examinations_by_hospital(
        hospitals,
        examinations,
    )

    if not counts:
        st.info(
            "No examination records available."
        )
        return

    top = counts.most_common(3)

    remaining = sum(
        count
        for _, count in counts.most_common()[3:]
    )

    if remaining:
        top.append(
            ("Other Hospitals", remaining)
        )

    labels = [name for name, _ in top]
    values = [count for _, count in top]

    colors = [
        "#00a8ad",
        "#258efa",
        "#9255ed",
        "#d7d9de",
    ]

    try:
        go = importlib.import_module("plotly.graph_objects")

    except ImportError:
        frame = pd.DataFrame(
            {
                "Hospital": labels,
                "Examinations": values,
            }
        ).set_index("Hospital")

        st.bar_chart(frame)
        return

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.68,
            sort=False,
            textinfo="none",
            marker={
                "colors": colors[:len(labels)]
            },
            hovertemplate=(
                "%{label}<br>"
                "%{value} examinations<br>"
                "%{percent}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=235,
        margin=dict(
            l=0,
            r=0,
            t=0,
            b=0,
        ),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=[
            {
                "text": (
                    f"<b>{len(examinations):,}</b>"
                    "<br>Total"
                ),
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {
                    "size": 19,
                    "color": "#101a3b",
                },
            }
        ],
    )

    chart_col, legend_col = st.columns(
        [1.1, 1],
        gap="small",
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
        total = sum(values)

        for index, (name, count) in enumerate(top):
            percentage = (
                count / total * 100
                if total
                else 0
            )

            color = colors[index]

            html = (
                '<div class="sad-legend-row">'
                f'<span class="sad-legend-dot" '
                f'style="background:{color}"></span>'
                f'<span class="sad-legend-name">{safe(name)}</span>'
                f'<strong>{percentage:.1f}%</strong>'
                '</div>'
            )

            st.markdown(
                html,
                unsafe_allow_html=True,
            )


# ============================================================
# SYSTEM MONITORING
# ============================================================

def render_system_monitoring(data_loaded):

    services = [
        {
            "label": "Database Connectivity",
            "icon": "database",
            "status": (
                "Connected"
                if data_loaded
                else "Unavailable"
            ),
            "tone": (
                "green"
                if data_loaded
                else "red"
            ),
        },
        {
            "label": "AI Model Availability",
            "icon": "brain",
            "status": "Not verified",
            "tone": "neutral",
        },
        {
            "label": "Subscription Services",
            "icon": "layers",
            "status": "Not verified",
            "tone": "neutral",
        },
    ]

    for service in services:
        html = (
            '<div class="sad-monitor-row">'
            '<div class="sad-monitor-icon">'
            f'{svg_icon(service["icon"])}'
            '</div>'
            f'<span>{safe(service["label"])}</span>'
            f'<strong class="sad-monitor-badge '
            f'sad-monitor-{service["tone"]}">'
            f'{safe(service["status"])}'
            '</strong>'
            '</div>'
        )

        st.markdown(
            html,
            unsafe_allow_html=True,
        )

    st.caption(
        "Model and subscription service health require "
        "dedicated checks before they can be marked operational."
    )


# ============================================================
# RECENT SYSTEM ACTIVITY
# ============================================================

def render_recent_activity(examinations):
    """
    Display actual recent examination records.

    This is not a full audit-log timeline.
    """

    recent = sorted(
        examinations,
        key=lambda item: (
            parse_datetime(item.get("created_at"))
            or datetime.min.replace(tzinfo=PH_TIMEZONE)
        ),
        reverse=True,
    )[:4]

    if not recent:
        st.info(
            "No recent examination records."
        )
        return

    for examination in recent:
        status = (
            examination.get("status")
            or "Unspecified"
        )

        code = (
            examination.get("examination_id")
            or "—"
        )

        created_at = format_datetime(
            examination.get("created_at")
        )

        html = (
            '<div class="sad-activity-row">'
            '<div class="sad-activity-icon">'
            f'{svg_icon("exam")}'
            '</div>'
            '<div class="sad-activity-details">'
            '<strong>Examination record</strong>'
            f'<span>Status: {safe(status)}</span>'
            '</div>'
            '<div class="sad-activity-meta">'
            f'<span>{safe(str(code)[:12])}</span>'
            f'<small>{safe(created_at)}</small>'
            '</div>'
            '</div>'
        )

        st.markdown(
            html,
            unsafe_allow_html=True,
        )

    st.caption(
        "Recent examination records. "
        "For complete administrative events, use Audit Logs."
    )


# ============================================================
# QUICK ACTIONS
# ============================================================

def render_quick_actions():

    with st.container(
        key="sad_quick_actions"
    ):
        row_one = st.columns(
            2,
            gap="small",
        )

        row_two = st.columns(
            2,
            gap="small",
        )

        columns = [
            *row_one,
            *row_two,
        ]

        for column, action in zip(
            columns,
            QUICK_ACTIONS,
        ):
            with column:
                with st.container(
                    key=f'sad_action_{action["tone"]}'
                ):
                    clicked = st.button(
                        action["label"],
                        icon=(
                            f':material/{action["icon"]}:'
                        ),
                        key=(
                            f'sad_go_{action["tone"]}'
                        ),
                        width="stretch",
                    )

                    if clicked:
                        navigate(
                            action["page"]
                        )


# ============================================================
# MAIN DASHBOARD
# ============================================================

def show():

    if not load_dashboard_css():
        return

    # --------------------------------------------------------
    # LOAD REAL DATA
    # --------------------------------------------------------

    try:
        data = fetch_dashboard_data()
        metrics = calculate_metrics(data)

    except Exception:
        st.error(
            "Unable to retrieve system dashboard data. "
            "Please refresh or contact your administrator."
        )
        return

    hospitals = data["hospitals"]
    examinations = data["examinations"]

    # --------------------------------------------------------
    # DASHBOARD WRAPPER
    # --------------------------------------------------------

    with st.container(
        key="sad_dashboard"
    ):

        # ----------------------------------------------------
        # HERO
        # ----------------------------------------------------

        render_hero()

        # ----------------------------------------------------
        # KPI METRICS
        # ----------------------------------------------------

        metric_columns = st.columns(
            4,
            gap="small",
        )

        cards = [
            (
                "Total Hospitals",
                metrics["total_hospitals"],
                "hospital",
                "teal",
                (
                    f'{metrics["active_hospitals"]} '
                    "active hospitals"
                ),
            ),
            (
                "Active Users",
                metrics["active_users"],
                "users",
                "blue",
                "Enabled user profiles",
            ),
            (
                "Total Examinations",
                metrics["total_examinations"],
                "exam",
                "orange",
                "System-wide records",
            ),
            (
                "AI System Status",
                "Unverified",
                "brain",
                "purple",
                "Health check unavailable",
            ),
        ]

        for column, card in zip(
            metric_columns,
            cards,
        ):
            with column:
                render_metric(*card)

        # ----------------------------------------------------
        # MAIN CHART PANELS
        # ----------------------------------------------------

        left, right = st.columns(
            [1.55, 1],
            gap="small",
        )

        with left:
            with st.container(
                key="sad_activity_chart_panel",
                border=True,
            ):
                render_panel_heading(
                    "chart",
                    "Hospital Activity",
                    "Examination activity across all hospitals",
                )

                render_activity_chart(
                    examinations
                )

        with right:
            with st.container(
                key="sad_hospital_distribution_panel",
                border=True,
            ):
                render_panel_heading(
                    "users",
                    "Examinations by Hospital",
                    "Distribution of recorded examinations",
                )

                render_hospital_distribution(
                    hospitals,
                    examinations,
                )

        # ----------------------------------------------------
        # LOWER PANELS
        # ----------------------------------------------------

        monitoring_col, activity_col, actions_col = (
            st.columns(
                [1, 1.15, 1.15],
                gap="small",
            )
        )

        with monitoring_col:
            with st.container(
                key="sad_monitoring_panel",
                border=True,
            ):
                render_panel_heading(
                    "pulse",
                    "System Monitoring",
                    "Core platform service availability",
                )

                render_system_monitoring(
                    data_loaded=True
                )

        with activity_col:
            with st.container(
                key="sad_recent_activity_panel",
                border=True,
            ):
                render_panel_heading(
                    "clock",
                    "Recent System Activity",
                    "Latest examination records",
                )

                render_recent_activity(
                    examinations
                )

        with actions_col:
            with st.container(
                key="sad_actions_panel",
                border=True,
            ):
                render_panel_heading(
                    "bolt",
                    "Quick Actions",
                    "Common administrative tasks",
                )

                render_quick_actions()

        # ----------------------------------------------------
        # REFRESH
        # ----------------------------------------------------

        with st.container(
            key="sad_refresh_footer"
        ):
            refresh_button(
                "system_admin_dashboard_refresh"
            )
