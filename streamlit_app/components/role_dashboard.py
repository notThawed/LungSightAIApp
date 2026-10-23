"""
Shared dashboard for hospital roles (Radiologist, Radiologic Technologist,
Staff, Hospital Admin).

Metrics come from backend.backend_utils.dashboard_utils, which the mobile app
mirrors in mobile_app/src/lib/dashboard.ts.
"""

import streamlit as st

from backend.backend_utils.dashboard_utils import get_dashboard_metrics
from shared.assets import load_css
from streamlit_app.components.ui import (
    metric_card,
    note,
    page_header,
    section_title,
)


METRIC_ICONS = {
    "pending_exams": ("pending_actions", "amber"),
    "xray_ready": ("radiology", "blue"),
    "awaiting_xray": ("schedule", ""),
    "completed_exams": ("task_alt", "green"),
    "followups_today": ("event_available", ""),
    "followups_upcoming": ("event_upcoming", "blue"),
    "followups_missed": ("event_busy", "red"),
    "ai_today": ("radiology", ""),
    "ai_positive_today": ("priority_high", "amber"),
    "active_hospitals": ("local_hospital", "blue"),
    "active_users": ("group", "green"),
}

AI_DISCLAIMER = (
    "LungSightAI results are decision support, not a diagnosis. "
    "Every AI finding must be reviewed and confirmed by a qualified clinician."
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_metrics(role, hospital_id):
    return get_dashboard_metrics(role, hospital_id)


def show_metric_row(metrics):
    columns = st.columns(len(metrics) or 1)

    for column, metric in zip(columns, metrics):
        icon, tone = METRIC_ICONS.get(metric["key"], ("monitoring", ""))
        value = "—" if metric["value"] is None else f"{metric['value']:,}"

        with column:
            metric_card(metric["label"], value, icon, tone, hint=metric["hint"])

    if any(metric["value"] is None for metric in metrics):
        note(
            "Some numbers could not be loaded and are shown as “—”. "
            "Use Refresh to try again.",
            "amber",
        )


def show_role_dashboard(title, caption, shortcuts, show_ai_note=True):
    """
    shortcuts: [(label, page_name, material_icon)] — buttons that open
    another page in the current role's sidebar navigation.
    """

    load_css("dashboard.css")

    user = st.session_state.get("user") or {}
    role = user.get("role")
    hospital_id = user.get("hospital_id")

    with st.container(key="sa_page"):

        if page_header(title, caption, "Refresh", "dashboard_refresh", "refresh"):
            _cached_metrics.clear()
            st.rerun()

        if not hospital_id:
            note("Your account is not linked to a hospital, so there is no workload to show.", "amber")
            return

        show_metric_row(_cached_metrics(role, hospital_id))

        if shortcuts:
            section_title("Quick actions")

            for column, (label, page, icon) in zip(st.columns(len(shortcuts)), shortcuts):
                if column.button(
                    label,
                    key=f"dashboard_go_{page}",
                    icon=f":material/{icon}:",
                    width="stretch",
                ):
                    st.session_state.current_page = page
                    st.rerun()

        if show_ai_note:
            st.write("")
            note(AI_DISCLAIMER)
