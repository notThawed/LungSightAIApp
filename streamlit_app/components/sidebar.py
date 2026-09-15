from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIDEBAR_CSS_PATH = PROJECT_ROOT / "shared" / "theme" / "css_content" / "sidebar.css"


def _load_sidebar_css() -> None:
    if SIDEBAR_CSS_PATH.exists():
        st.markdown(f"<style>{SIDEBAR_CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _ensure_valid_current_page(valid_pages: list[str]) -> None:
    if st.session_state.current_page not in valid_pages:
        st.session_state.current_page = valid_pages[0]


def _show_sidebar_header(role_label: str) -> None:
    name = st.session_state.user.get("name", "User")
    st.sidebar.markdown(
        f"""
        <div class="ls-sidebar-header">
            <div class="ls-sidebar-brand">LungSight</div>
            <div class="ls-sidebar-welcome">Welcome, <strong>{name}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _render_nav_buttons(role_key: str, nav_items: list[tuple[str, str]]) -> str:
    # Start the main content container
    st.sidebar.markdown('<div class="ls-sidebar-main">', unsafe_allow_html=True)
    
    for page, label in nav_items:
        is_active = st.session_state.current_page == page
        if st.sidebar.button(
            label,
            key=f"{role_key}_{page}",
            width="stretch",
            disabled=is_active,
        ):
            st.session_state.current_page = page
            st.rerun()
    
    # Close the main content container
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    return st.session_state.current_page


def _render_account(role_key: str) -> None:

    st.sidebar.markdown(
        """
        <div class="ls-sidebar-account">
            <div class="ls-sidebar-account-label">Account</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    is_profile_active = st.session_state.current_page == "Profile"

    if st.sidebar.button(
        "Manage Profile",
        key=f"{role_key}_Profile",
        width="stretch",
        disabled=is_profile_active,
    ):
        st.session_state.current_page = "Profile"
        st.rerun()

    if st.sidebar.button(
        "Logout",
        key=f"{role_key}_Logout",
        width="stretch",
    ):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.current_page = "Dashboard"
        st.rerun()

def show_radtech_sidebar():
    _load_sidebar_css()

    radtech_nav_items = [
        ("Dashboard", "Home dashboard"),
        ("Analyze X-Ray", "Analyze X-ray"),
        ("Patient Records", "Patient records"),
        ("Manage Examinations", "Examinations"),
        ("Geospatial Map", "Geospatial map"),
    ]
    valid_pages = [page for page, _ in radtech_nav_items] + ["Profile"]
    _ensure_valid_current_page(valid_pages)
    _show_sidebar_header("Radiology technologist")

    selected_page = _render_nav_buttons("radtech_nav", radtech_nav_items)
    _render_account("radtech")
    return selected_page


def show_physician_sidebar():
    _load_sidebar_css()

    physician_nav_items = [
        ("Dashboard", "Home dashboard"),
        ("Patient Queue", "Patient queue"),
        ("Review Patient", "Review patient"),
        ("Patient Records", "Patient records"),
    ]
    valid_pages = [page for page, _ in physician_nav_items] + ["Profile"]
    _ensure_valid_current_page(valid_pages)
    _show_sidebar_header("Physician")

    selected_page = _render_nav_buttons("physician_nav", physician_nav_items)
    _render_account("physician")
    return selected_page

def show_admin_sidebar():
    _load_sidebar_css()

    admin_nav_items = [
        ("Dashboard", "Home dashboard"),
        ("User Management", "Manage System Users"),
        ("Manage Patients", "Manage Patients"),
        ("Manage Examinations", "Manage Examinations"),
        ("Medical Records", "Medical Records"),
        ("Reports", "View reports"),
        ("System Settings", "Configure system settings"),
    ]
    valid_pages = [page for page, _ in admin_nav_items] + ["Profile"]
    _ensure_valid_current_page(valid_pages)
    _show_sidebar_header("Administrator")

    selected_page = _render_nav_buttons("admin_nav", admin_nav_items)
    _render_account("admin")
    return selected_page