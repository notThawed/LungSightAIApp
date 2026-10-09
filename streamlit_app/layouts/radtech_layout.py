import streamlit as st
from components.sidebar import show_radtech_sidebar
from components.navbar import show_top_navbar

from pages.radtech import dashboard, analyze, geospatial, profile, xray_queue
from pages.system_administrator import manage_examinations, manage_patients

from pages.hospital_administrator import subscription_gate


# ============================================================
# ANALYZE STATE KEYS
# ============================================================

ANALYZE_STATE_KEYS = [
    "radtech_active_examination",
    "radtech_active_patient",
    "radtech_analysis_result",
    "rx_upload",
    "rx_save",
]


def clear_analyze_state():
    """
    Wipe the Analyze X-Ray working state.

    Called whenever the user navigates away from
    the Analyze X-Ray page so that returning to it
    always starts fresh with 'No Patient Selected'.
    """

    for key in ANALYZE_STATE_KEYS:
        st.session_state.pop(key, None)


def show_radtech_layout():

    page = show_radtech_sidebar()

    page_info = {
        "Dashboard": "Quick overview of workload, recent uploads, and key imaging status metrics.",
        "Analyze X-Ray": "Upload and run AI-assisted chest X-ray analysis to support screening and triage.",
        "Patient Records": "Browse patient imaging history and view archived case details.",
        "Examinations": "Generate and review summary reports for findings, trends, and outcomes.",
        "Geospatial Map": "Inspecting location-based imaging trends and regional case distributions.",
        "Profile": "Manage your account information and role-specific preferences.",
        "X-ray Queus": "Pending X-ray requests awaiting imaging.",
    }

    show_top_navbar(
        page_name=page,
        page_info=page_info.get(
            page,
            "Page information is not available.",
        ),
    )

    subscription_gate.render_subscription_warnings(can_renew=False)

    # ========================================================
    # CLEANUP — leaving the Analyze page resets the state
    # ========================================================

    if page != "Analyze X-Ray":
        clear_analyze_state()

    # ========================================================
    # DISPATCH
    # ========================================================

    if page == "Dashboard":
        dashboard.show()

    elif page == "Analyze X-Ray":
        analyze.show()

    elif page == "Patient Records":
        manage_patients.show()

    elif page == "Manage Examinations":
        manage_examinations.show()

    elif page == "Geospatial Map":
        geospatial.show()

    elif page == "X-ray Queus":
        xray_queue.show()

    elif page == "Profile":
        profile.show()