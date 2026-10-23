from pathlib import Path
import html

import streamlit as st


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
# LOAD CSS
# ============================================================

def _load_navbar_css() -> None:

    if not NAVBAR_CSS_PATH.exists():
        return

    css = NAVBAR_CSS_PATH.read_text(
        encoding="utf-8"
    )

    st.markdown(
        f"<style>{css}</style>",
        unsafe_allow_html=True,
    )


# ============================================================
# ROLE LABEL
# ============================================================

def _role_label(
    role_value: str | None
) -> str:

    role_labels = {
        "Radiologist": "Radiologist",
        "Radiologic Technologist": "Radiologic Technologist",
        "Staff": "Staff",
        "Hospital Admin": "Hospital Admin",
        "Superadmin": "System Administrator",
    }

    return role_labels.get(
        role_value,
        role_value or "User",
    )


# ============================================================
# INITIALS
# ============================================================

def _initials(
    name: str
) -> str:

    if not name:
        return "U"

    parts = [
        segment
        for segment
        in name.strip().split()
        if segment
    ]

    if not parts:
        return "U"

    if len(parts) == 1:
        return parts[0][0].upper()

    return (
        f"{parts[0][0]}"
        f"{parts[-1][0]}"
    ).upper()


# ============================================================
# ESCAPE TEXT
# ============================================================

def _safe_text(
    value,
    fallback="",
):

    if value is None:
        value = fallback

    return html.escape(
        str(value)
    )


# ============================================================
# AVATAR HTML
# ============================================================

def _avatar_html(
    user: dict
) -> str:

    avatar_url = (
        user.get(
            "profile_picture_url"
        )
        or user.get(
            "profile_picture"
        )
        or user.get(
            "avatar_url"
        )
    )

    if avatar_url:

        return (
            '<img '
            f'src="{html.escape(avatar_url)}" '
            'alt="User profile" '
            'class="ls-nav-avatar-image">'
        )

    initials = _initials(
        user.get(
            "name",
            "User",
        )
    )

    return (
        '<div class="ls-nav-avatar-fallback">'
        f'{initials}'
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

    user = (
        st.session_state.get("user")
        or {}
    )

    # --------------------------------------------------------
    # User information
    # --------------------------------------------------------

    user_name = _safe_text(
        user.get("name"),
        "User",
    )

    role_text = _safe_text(
        _role_label(
            user.get("role")
        ),
        "User",
    )

    hospital_name = _safe_text(
        user.get("hospital_name")
        or ("LungSightAI system" if user.get("role") == "Superadmin" else ""),
    )

    # --------------------------------------------------------
    # Avatar
    # --------------------------------------------------------

    avatar_html = _avatar_html(
        user
    )

    hospital_html = (
        f'<span class="ls-nav-hospital" title="{hospital_name}">'
        '<span class="ls-nav-icon">local_hospital</span>'
        f"{hospital_name}</span>"
        if hospital_name
        else ""
    )

    # --------------------------------------------------------
    # Navbar: where you are (left) and who you are (right).
    # The LungSightAI brand lives in the sidebar.
    # --------------------------------------------------------

    with st.container(
        key="top_navbar"
    ):

        left_col, right_col = st.columns(
            [3, 2],
            vertical_alignment="center",
        )

        with left_col:

            st.markdown(
                '<div class="ls-nav-context">'
                f'<div class="ls-nav-page">{_safe_text(page_name)}</div>'
                f'<div class="ls-nav-info">{_safe_text(page_info)}</div>'
                "</div>",
                unsafe_allow_html=True,
            )

        with right_col:

            st.markdown(
                '<div class="ls-nav-profile-wrap">'
                '<div class="ls-nav-user-text">'
                f'<div class="ls-nav-user-name">{user_name}</div>'
                f'<div class="ls-nav-user-role">{role_text}{hospital_html}</div>'
                "</div>"
                f"{avatar_html}"
                "</div>",
                unsafe_allow_html=True,
            )
