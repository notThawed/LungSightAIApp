from pathlib import Path
import html

import streamlit as st


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SIDEBAR_CSS_PATH = (
    PROJECT_ROOT
    / "shared"
    / "theme"
    / "css_content"
    / "sidebar.css"
)


# ============================================================
# NAVIGATION
# ============================================================

RADTECH_NAV = [
    {
        "section": "Overview",
        "items": [
            (
                "Dashboard",
                "Home dashboard",
                "dashboard",
            ),
        ],
    },

    {
        "section": "Clinical",
        "items": [
            (
                "Analyze X-Ray",
                "Analyze X-ray",
                "radiology",
            ),
            (
                "Patient Records",
                "Patient records",
                "folder_shared",
            ),
            (
                "Manage Examinations",
                "Examinations",
                "assignment",
            ),
            (
                "X-ray Queus",
                "X-ray Queus",
                "assignment",
            ),

        ],
    },

    {
        "section": "Monitoring",
        "items": [
            (
                "Geospatial Map",
                "Geospatial map",
                "map",
            ),
        ],
    },
]


PHYSICIAN_NAV = [
    {
        "section": "Overview",
        "items": [
            (
                "Dashboard",
                "Home dashboard",
                "dashboard",
            ),
            (
                "Patient Queue",
                "Patient queue",
                "groups",
            ),
        ],
    },

    {
        "section": "Clinical",
        "items": [
            (
                "Review Patient",
                "Review patient",
                "person_search",
            ),
            (
                "Patient Records",
                "Patient records",
                "folder_shared",
            ),
        ],
    },
]


ADMIN_NAV = [
    {
        "section": "Overview",
        "items": [
            (
                "Dashboard",
                "Home dashboard",
                "dashboard",
            ),
        ],
    },

    {
        "section": "Clinical Management",
        "items": [
            (
                "Manage Patients",
                "Manage Patients",
                "group",
            ),
            (
                "Manage Examinations",
                "Manage Examinations",
                "assignment",
            ),
            (
                "Medical Records",
                "Manage Medical Records",
                "description",
            ),
        ],
    },

    {
        "section": "System Management",
        "items": [
            (
                "User Management",
                "Manage System Users",
                "manage_accounts",
            ),
            (
                "Manage Hospitals",
                "Manage Hospitals",
                "local_hospital",
            ),
            (
                "Manage Client Applications",
                "Manage Client Applications",
                "inbox",
            ),
            (
                "Manage Subscriptions",
                "Manage Subscriptions",
                "credit_card",
            ),
        ],
    },

    {
        "section": "Monitoring & Reports",
        "items": [
            (
                "Reports",
                "View reports",
                "bar_chart",
            ),
        ],
    },

    {
        "section": "Configuration",
        "items": [
            (
                "System Settings",
                "Configure system settings",
                "settings",
            ),
        ],
    },
]


STAFF_NAV = [
    {
        "section": "Overview",
        "items": [
            (
                "Dashboard",
                "Home dashboard",
                "dashboard",
            ),
        ],
    },

    {
        "section": "Patient Management",
        "items": [
            (
                "Register Patient",
                "Register new patient",
                "person_add",
            ),
            (
                "Patient Records",
                "Patient Records",
                "folder_shared",
            ),
        ],
    },

    {
        "section": "Clinical Workflow",
        "items": [
            (
                "Examinations",
                "Examinations",
                "assignment",
            ),
        ],
    },

    {
        "section": "Appointments",
        "items": [
            (
                "Follow-Ups",
                "Follow-up appointments",
                "event_available",
            ),
        ],
    },
]


HOSPITAL_ADMIN_NAV = [
    {
        "section": "Overview",
        "items": [
            (
                "Dashboard",
                "Home dashboard",
                "dashboard",
            ),
        ],
    },

    {
        "section": "Hospital Management",
        "items": [
            (
                "Manage Users",
                "Manage Users",
                "manage_accounts",
            ),
            (
                "Manage Patients",
                "Manage Patients",
                "group",
            ),
            (
                "Manage Examinations",
                "Manage Examinations",
                "assignment",
            ),
        ],
    },
]


# ============================================================
# LOAD CSS
# ============================================================

def load_sidebar_css():
    """Load the sidebar stylesheet."""

    if not SIDEBAR_CSS_PATH.exists():
        return

    css = SIDEBAR_CSS_PATH.read_text(
        encoding="utf-8"
    )

    st.markdown(
        f"""<style>
{css}
</style>""",
        unsafe_allow_html=True,
    )


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user():
    """Return the currently logged-in user."""

    return (
        st.session_state.get("user")
        or {}
    )


# ============================================================
# SAFE TEXT
# ============================================================

def safe_text(
    value,
    fallback="",
):
    """Escape user-provided values before inserting into HTML."""

    if value is None or str(value).strip() == "":
        value = fallback

    return html.escape(
        str(value)
    )


# ============================================================
# INITIALS
# ============================================================

# Titles that should not count as initials ("Dr. Maria Santos" -> MS, not DM)
NAME_TITLES = {"dr", "dra", "mr", "mrs", "ms", "engr", "atty", "prof"}


def get_initials(name):
    """Turn 'Maria Santos' into 'MS' (used for the avatar circle)."""

    words = [
        word
        for word in str(name).split()
        if word.strip(".").lower() not in NAME_TITLES
    ]

    if not words:
        return "U"

    if len(words) == 1:
        return words[0][0].upper()

    return (words[0][0] + words[-1][0]).upper()


# ============================================================
# NAVIGATION VALIDATION
# ============================================================

def ensure_valid_current_page(
    valid_pages,
):
    """Reset the current page if it is not available."""

    current_page = st.session_state.get(
        "current_page"
    )

    if current_page not in valid_pages:
        st.session_state.current_page = (
            valid_pages[0]
        )


# ============================================================
# NAVIGATION BUTTON
# ============================================================

def nav_button(
    label,
    page,
    icon,
    key,
):
    """Render one sidebar navigation button."""

    is_active = (
        st.session_state.current_page
        == page
    )

    button_type = (
        "primary"
        if is_active
        else "secondary"
    )

    if st.button(
        label,
        key=key,
        icon=f":material/{icon}:",
        type=button_type,
        width="stretch",
    ):
        st.session_state.current_page = page
        st.rerun()


# ============================================================
# SIDEBAR HEADER
# Logo and brand on top, then a small card with the signed-in user.
# ============================================================

def show_header(role_label):

    user = get_current_user()

    user_name = user.get("name") or "User"

    hospital_logo_url = (
        user.get("hospital_logo_url")
        or ""
    )

    # ---- logo: the hospital's logo, or a hospital icon as a fallback ----

    if hospital_logo_url:

        logo_html = (
            '<img class="ls-sidebar-logo" '
            f'src="{html.escape(hospital_logo_url)}" '
            'alt="Hospital logo">'
        )

    else:

        logo_html = (
            '<div class="ls-sidebar-logo ls-sidebar-logo-fallback">'
            '<span class="ls-sidebar-icon">settings</span>'
            "</div>"
        )

    # ---- everything is written as one HTML string (no blank lines) ----

    with st.container(
        key="sidebar_header"
    ):

        st.markdown(
            '<div class="ls-sidebar-brandbar">'
            f"{logo_html}"
            '<div class="ls-sidebar-brand">LungSight</div>'
            "</div>"
            '<div class="ls-sidebar-usercard">'
            f'<div class="ls-sidebar-avatar">{safe_text(get_initials(user_name))}</div>'
            '<div class="ls-sidebar-usertext">'
            f'<div class="ls-sidebar-username" title="{safe_text(user_name)}">'
            f"{safe_text(user_name)}</div>"
            f'<div class="ls-sidebar-role">{safe_text(role_label)}</div>'
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )


# ============================================================
# SIDEBAR MENU
# ============================================================

def show_menu(
    role_key,
    nav_sections,
):
    """Render the sidebar navigation grouped into sections."""

    with st.container(
        key="sidebar_nav"
    ):

        for section in nav_sections:

            section_name = section.get("section")
            items = section.get("items", [])

            # ------------------------------------------------
            # Section label
            # ------------------------------------------------

            st.markdown(
                f"""
                <div class="ls-sidebar-section-label">
                    {safe_text(section_name)}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ------------------------------------------------
            # Section navigation buttons
            # ------------------------------------------------

            for (
                page,
                label,
                icon,
            ) in items:

                nav_button(
                    label=label,
                    page=page,
                    icon=icon,
                    key=f"nav_{role_key}_{page}",
                )


# ============================================================
# SIDEBAR ACCOUNT
# ============================================================

def show_account(role_key):
    """Render profile and logout controls."""

    with st.container(
        key="sidebar_account"
    ):

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

            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.current_page = "Dashboard"

            st.rerun()


# ============================================================
# MAIN SIDEBAR
# ============================================================

def show_sidebar(
    role_key,
    role_label,
    nav_sections,
):
    """Build the complete sidebar."""

    load_sidebar_css()

    valid_pages = []

    for section in nav_sections:
        for item in section.get("items", []):
            valid_pages.append(item[0])

    valid_pages.append("Profile")

    ensure_valid_current_page(
        valid_pages
    )

    with st.sidebar:

        show_header(
            role_label
        )

        show_menu(
            role_key,
            nav_sections,
        )

        show_account(
            role_key
        )

    return st.session_state.current_page


# ============================================================
# ROLE-SPECIFIC SIDEBARS
# ============================================================

def show_radtech_sidebar():

    return show_sidebar(
        "radtech",
        "Radiology Technologist",
        RADTECH_NAV,
    )


def show_physician_sidebar():

    return show_sidebar(
        "physician",
        "Physician",
        PHYSICIAN_NAV,
    )


def show_admin_sidebar():

    return show_sidebar(
        "admin",
        "Administrator",
        ADMIN_NAV,
    )


def show_staff_sidebar():

    return show_sidebar(
        "staff",
        "Staff",
        STAFF_NAV,
    )


def show_hospital_admin_sidebar():

    return show_sidebar(
        "hospital_admin",
        "Hospital Admin",
        HOSPITAL_ADMIN_NAV,
    )