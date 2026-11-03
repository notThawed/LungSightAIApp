
from pathlib import Path
import base64
import html

import streamlit as st

from backend import audit


# ============================================================
# FILE PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SIDEBAR_CSS_PATH = (
    PROJECT_ROOT / "shared" / "theme"
    / "css_content" / "sidebar.css"
)

SIDEBAR_LOGO_PATH = (
    PROJECT_ROOT / "shared" / "images"
    / "Modern LungSight Orbit Logo.png"
)


# ============================================================
# ROLE NAVIGATION
# ============================================================

RADTECH_NAV = [
    {
        "section": "Overview",
        "items": [
            ("Dashboard", "Home dashboard", "dashboard"),
        ],
    },
    {
        "section": "Clinical",
        "items": [
            ("Analyze X-Ray", "Analyze X-ray", "radiology"),
            ("Patient Records", "Patient records", "folder_shared"),
            ("Manage Examinations", "Examinations", "assignment"),
            ("X-ray Queus", "X-ray Queus", "assignment"),
        ],
    },
    {
        "section": "Monitoring",
        "items": [
            ("Geospatial Map", "Geospatial map", "map"),
        ],
    },
]


PHYSICIAN_NAV = [
    {
        "section": "Overview",
        "items": [
            ("Dashboard", "Home dashboard", "dashboard"),
            ("Patient Queue", "Patient queue", "groups"),
        ],
    },
    {
        "section": "Clinical",
        "items": [
            ("Review Patient", "Review patient", "person_search"),
            ("Patient Records", "Patient records", "folder_shared"),
            ("Inpatient Dashboard", "Inpatient dashboard", "bedroom_parent"),
            ("Follow-Ups", "Follow-ups", "assignment"),
        ],
    },
]


ADMIN_NAV = [
    {
        "section": "Overview",
        "items": [
            ("Dashboard", "Home dashboard", "dashboard"),
        ],
    },
    {
        "section": "Clinical Management",
        "items": [
            ("Manage Patients", "Manage Patients", "group"),
            ("Manage Examinations", "Manage Examinations", "assignment"),
            ("Medical Records", "Manage Medical Records", "description"),
        ],
    },
    {
        "section": "System Management",
        "items": [
            ("User Management", "Manage System Users", "manage_accounts"),
            ("Manage Hospitals", "Manage Hospitals", "local_hospital"),
            ("Manage Client Applications", "Manage Client Applications", "inbox"),
            ("Manage Subscriptions", "Manage Subscriptions", "credit_card"),
        ],
    },
    {
        "section": "Monitoring & Reports",
        "items": [
            ("Reports", "View reports", "bar_chart"),
            ("Audit Logs", "Audit Logs", "history"),
            ("Email Notifications", "Email Notifications", "mail"),
        ],
    },
    {
        "section": "AI TRAINING",
        "items": [
            ("Training", "Data Training", "settings"),
        ],
    },
    {
        "section": "Configuration",
        "items": [
            ("System Settings", "Configure system settings", "settings"),
        ],
    },
]


STAFF_NAV = [
    {
        "section": "Overview",
        "items": [
            ("Dashboard", "Home dashboard", "dashboard"),
        ],
    },
    {
        "section": "Patient Management",
        "items": [
            ("Register Patient", "Register Patient", "person_add"),
            ("Patient Records", "Patient Records", "folder_shared"),
        ],
    },
    {
        "section": "Clinical Workflow",
        "items": [
            ("Examinations", "Examinations", "assignment"),
            ("Follow-Ups", "Follow-up appointments", "event_available"),
        ],
    },
]


HOSPITAL_ADMIN_NAV = [
    {
        "section": "Overview",
        "items": [
            ("Dashboard", "Home dashboard", "dashboard"),
            ("My Hospital", "My Hospital info", "dashboard"),
        ],
    },
    {
        "section": "Hospital Management",
        "items": [
            ("Manage Users", "Manage Users", "manage_accounts"),
            ("Manage Patients", "Manage Patients", "group"),
            ("Manage Examinations", "Manage Examinations", "assignment"),
        ],
    },
    {
        "section": "Subscription Management",
        "items": [
            ("Subscription Usage", "Subscription Usage", "data_usage"),
            ("Subscription Settings", "Subscription Settings", "payments"),
        ],
    },
    {
        "section": "Reports",
        "items": [
            ("Hospital Reports", "Hospital Reports", "summarize"),
        ],
    },
    {
        "section": "Security",
        "items": [
            ("Audit Logs", "Audit Logs", "history"),
            ("Email Notifications", "Email Notifications", "mail"),
        ],
    },
]


# ============================================================
# LOAD SIDEBAR CSS
# ============================================================

def load_sidebar_css():
    if SIDEBAR_CSS_PATH.exists():
        css = SIDEBAR_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(
            f"<style>{css}</style>",
            unsafe_allow_html=True,
        )


# ============================================================
# HTML ESCAPING
# ============================================================

def safe_text(value, fallback=""):
    if value is None or str(value).strip() == "":
        value = fallback
    return html.escape(str(value))


# ============================================================
# SIDEBAR BRANDING
# ============================================================

def show_sidebar_branding():
    """Show the Modern LungSight Orbit logo and LungSight title."""

    logo_html = ""

    if SIDEBAR_LOGO_PATH.is_file():
        encoded = base64.b64encode(
            SIDEBAR_LOGO_PATH.read_bytes()
        ).decode("utf-8")

        logo_html = (
            '<img class="ls-sidebar-brand-logo" '
            f'src="data:image/png;base64,{encoded}" '
            'alt="LungSight logo">'
        )

    # Use one continuous HTML string to prevent raw HTML output.
    branding_html = (
        '<div class="ls-sidebar-brand-row">'
        f'{logo_html}'
        '<span class="ls-sidebar-brand-title">LungSight</span>'
        '</div>'
    )

    with st.container(key="sidebar_branding"):
        st.markdown(
            branding_html,
            unsafe_allow_html=True,
        )


# ============================================================
# CURRENT PAGE VALIDATION
# ============================================================

def ensure_valid_current_page(valid_pages):
    if not valid_pages:
        return

    if st.session_state.get("current_page") not in valid_pages:
        st.session_state.current_page = valid_pages[0]


# ============================================================
# NAVIGATION BUTTON
# ============================================================

def nav_button(label, page, icon, key):
    is_active = st.session_state.current_page == page

    if st.button(
        label,
        key=key,
        icon=f":material/{icon}:",
        type="primary" if is_active else "secondary",
        width="stretch",
    ):
        st.session_state.current_page = page
        st.rerun()


# ============================================================
# NAVIGATION MENU
# ============================================================

def show_menu(role_key, nav_sections):
    with st.container(key="sidebar_nav"):

        for section in nav_sections:
            section_name = safe_text(section.get("section", ""))

            # Single-line HTML prevents Markdown code rendering.
            st.markdown(
                f'<div class="ls-sidebar-section-label">'
                f'{section_name}</div>',
                unsafe_allow_html=True,
            )

            for page, label, icon in section.get("items", []):
                nav_button(
                    label=label,
                    page=page,
                    icon=icon,
                    key=f"nav_{role_key}_{page}",
                )


# ============================================================
# ACCOUNT CONTROLS
# ============================================================

def show_account(role_key):
    """Keep Manage Profile and Logout functional."""

    with st.container(key="sidebar_account"):

        nav_button(
            "Manage Profile",
            "Profile",
            "account_circle",
            key=f"profile_{role_key}",
        )

        if st.button(
            "Logout",
            key=f"logout_{role_key}",
            icon=":material/logout:",
            width="stretch",
        ):
            audit.record_logout()

            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.current_page = "Dashboard"

            st.rerun()


# ============================================================
# MAIN SIDEBAR
# ============================================================

def show_sidebar(role_key, role_label, nav_sections):
    load_sidebar_css()

    valid_pages = [
        item[0]
        for section in nav_sections
        for item in section.get("items", [])
    ]

    valid_pages.append("Profile")

    ensure_valid_current_page(valid_pages)

    with st.sidebar:
        show_sidebar_branding()
        show_menu(role_key, nav_sections)
        show_account(role_key)

    return st.session_state.current_page


# ============================================================
# ROLE-SPECIFIC SIDEBARS
# ============================================================

def show_radtech_sidebar():
    return show_sidebar(
        "radtech", "Radiology Technologist", RADTECH_NAV
    )


def show_physician_sidebar():
    return show_sidebar(
        "physician", "Physician", PHYSICIAN_NAV
    )


def show_admin_sidebar():
    return show_sidebar(
        "admin", "Administrator", ADMIN_NAV
    )


def show_staff_sidebar():
    return show_sidebar(
        "staff", "Staff", STAFF_NAV
    )


def show_hospital_admin_sidebar():
    return show_sidebar(
        "hospital_admin", "Hospital Admin", HOSPITAL_ADMIN_NAV
    )
