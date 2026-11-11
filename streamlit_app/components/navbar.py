
from pathlib import Path
import html

import streamlit as st

from backend import audit


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

NAVBAR_CSS_PATH = (
    PROJECT_ROOT
    / "shared"
    / "theme"
    / "css_content"
    / "navbar.css"
)


# ============================================================
# LOAD NAVBAR CSS
# ============================================================

def _load_navbar_css() -> None:
    if NAVBAR_CSS_PATH.exists():
        css = NAVBAR_CSS_PATH.read_text(
            encoding="utf-8"
        )

        st.markdown(
            f"<style>{css}</style>",
            unsafe_allow_html=True,
        )


# ============================================================
# ROLE LABELS
# ============================================================

def _role_label(role_value: str | None) -> str:
    """
    Return a readable role name for the navbar.

    Handles differences in capitalization and common
    role naming variations.
    """

    role_labels = {
        "radtech": "Radiology Technologist",
        "radiology technologist": "Radiology Technologist",
        "radiologic technologist": "Radiology Technologist",
        "radiologist": "Radiologist",
        "physician": "Physician",
        "hospital admin": "Hospital Admin",
        "hospital administrator": "Hospital Admin",
        "administrator": "Hospital Admin",
        "superadmin": "System Administrator",
        "super admin": "System Administrator",
        "system administrator": "System Administrator",
        "system admin": "System Administrator",
        "staff": "Staff",
    }

    if not role_value:
        return "User"

    normalized_role = str(role_value).strip().lower()

    return role_labels.get(
        normalized_role,
        str(role_value).strip(),
    )


# ============================================================
# PORTAL TITLE
# ============================================================

def _portal_title(role_value: str | None) -> str:
    """
    Generate the portal title based on the user's role.

    Examples:
        Staff -> Staff Portal
        Physician -> Physician Portal
        Superadmin -> System Administrator Portal
    """

    role_name = _role_label(role_value)

    return f"{role_name} Portal"


# ============================================================
# USER INITIALS
# ============================================================

def _initials(name: str) -> str:
    if not name:
        return "U"

    parts = [
        part
        for part in name.strip().split()
        if part
    ]

    if not parts:
        return "U"

    if len(parts) == 1:
        return parts[0][0].upper()

    return (
        f"{parts[0][0]}{parts[-1][0]}"
    ).upper()


# ============================================================
# ESCAPE HTML TEXT
# ============================================================

def _safe_text(value, fallback=""):
    if value is None or str(value).strip() == "":
        value = fallback

    return html.escape(
        str(value),
        quote=True,
    )


# ============================================================
# AVATAR HTML
# ============================================================

def _avatar_html(user: dict) -> str:
    avatar_url = (
        user.get("profile_picture_url")
        or user.get("profile_picture")
        or user.get("avatar_url")
    )

    if avatar_url:
        return (
            '<img class="ls-nav-avatar-image" '
            f'src="{html.escape(str(avatar_url), quote=True)}" '
            'alt="User profile">'
        )

    initials = _initials(
        user.get("name") or "User"
    )

    return (
        '<div class="ls-nav-avatar-fallback">'
        f'{html.escape(initials)}'
        '</div>'
    )


# ============================================================
# TOP NAVBAR
# ============================================================

def show_top_navbar(
    page_name: str = "",
    page_info: str = "",
) -> None:

    _load_navbar_css()

    audit.flush_audit_warnings()

    user = st.session_state.get("user") or {}

    # --------------------------------------------------------
    # USER INFORMATION
    # --------------------------------------------------------

    user_name = _safe_text(
        user.get("name"),
        "User",
    )

    role_name = _role_label(
        user.get("role")
    )

    role_text = _safe_text(
        role_name,
        "User",
    )

    avatar_html = _avatar_html(user)

    # --------------------------------------------------------
    # PORTAL INFORMATION
    # --------------------------------------------------------

    portal_title = _safe_text(
        _portal_title(user.get("role")),
        "User Portal",
    )

    # --------------------------------------------------------
    # HOSPITAL INFORMATION
    # --------------------------------------------------------

    hospital_name = _safe_text(
        user.get("hospital_name"),
        "LungSightAI",
    )

    hospital_logo_url = (
        user.get("hospital_logo_url")
        or ""
    )

    hospital_logo_html = ""

    if hospital_logo_url:
        hospital_logo_html = (
            '<img class="ls-nav-hospital-logo" '
            f'src="{html.escape(str(hospital_logo_url), quote=True)}" '
            'alt="Hospital logo">'
        )

    # --------------------------------------------------------
    # HOSPITAL HTML
    # --------------------------------------------------------

    hospital_html = (
        '<div class="ls-nav-hospital-wrap">'
        f'{hospital_logo_html}'
        '<div class="ls-nav-hospital-name">'
        f'{hospital_name}'
        '</div>'
        '</div>'
    )

    # --------------------------------------------------------
    # CENTER PORTAL TITLE HTML
    # --------------------------------------------------------

    portal_html = (
        '<div class="ls-nav-portal-wrap">'
        '<div class="ls-nav-portal-title">'
        f'{portal_title}'
        '</div>'
        '<div class="ls-nav-portal-subtitle">'
        'LungSightAI'
        '</div>'
        '</div>'
    )

    # --------------------------------------------------------
    # PROFILE HTML
    # --------------------------------------------------------

    profile_html = (
        '<div class="ls-nav-profile-wrap">'
        '<div class="ls-nav-user-text">'
        '<div class="ls-nav-user-name">'
        f'{user_name}'
        '</div>'
        '<div class="ls-nav-user-role">'
        f'{role_text}'
        '</div>'
        '</div>'
        f'{avatar_html}'
        '</div>'
    )

    # --------------------------------------------------------
    # RENDER NAVBAR
    # --------------------------------------------------------

    with st.container(
        key="top_navbar"
    ):

        left_col, center_col, right_col = (
            st.columns(
                [1, 1, 1],
                gap="small",
                vertical_alignment="center",
            )
        )

        # LEFT: HOSPITAL INFORMATION

        with left_col:
            st.markdown(
                hospital_html,
                unsafe_allow_html=True,
            )

        # CENTER: ROLE PORTAL TITLE

        with center_col:
            st.markdown(
                portal_html,
                unsafe_allow_html=True,
            )

        # RIGHT: USER PROFILE

        with right_col:
            st.markdown(
                profile_html,
                unsafe_allow_html=True,
            )
