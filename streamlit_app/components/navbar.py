from pathlib import Path
import base64
import html

import streamlit as st


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOGO_PATH = (
    PROJECT_ROOT
    / "shared"
    / "images"
    / "LungSight Logo.png"
)

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

        "radtech":
            "RadTech",

        "Radiology Technologist":
            "Radiology Technologist",

        "physician":
            "Physician",

        "Hospital Admin":
            "Hospital Admin",

        "Hospital administrator":
            "Hospital Admin",

        "Administrator":
            "Administrator",

        "Staff":
            "Staff",
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
# LUNGSIGHT LOGO
# ============================================================

def _logo_data_uri() -> str:

    if not LOGO_PATH.exists():
        return ""

    encoded = base64.b64encode(
        LOGO_PATH.read_bytes()
    ).decode("utf-8")

    return (
        f"data:image/png;base64,{encoded}"
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
        user.get("hospital_name"),
        "-",
    )

    # --------------------------------------------------------
    # Avatar
    # --------------------------------------------------------

    avatar_html = _avatar_html(
        user
    )

    # --------------------------------------------------------
    # LungSight logo
    # --------------------------------------------------------

    logo_uri = _logo_data_uri()

    if logo_uri:

        logo_html = (
            '<img '
            f'src="{logo_uri}" '
            'class="ls-nav-brand-logo" '
            'alt="LungSight logo">'
        )

    else:

        logo_html = ""

    # --------------------------------------------------------
    # Navbar
    #
    # Three columns:
    #
    # LEFT   = LungSight
    # CENTER = Hospital name
    # RIGHT  = User profile
    # --------------------------------------------------------

    with st.container(
        key="top_navbar"
    ):

        left_col, center_col, right_col = (
            st.columns(
                [1.5, 3, 1.8],
                vertical_alignment="center",
            )
        )

        # ====================================================
        # LEFT
        # ====================================================

        with left_col:

            st.markdown(
                f"""<div class="ls-nav-left-wrap">
{logo_html}
<div class="ls-nav-appname">LungSight</div>
</div>""",
                unsafe_allow_html=True,
            )

        # ====================================================
        # CENTER
        # ====================================================

        with center_col:

            st.markdown(
                f"""<div class="ls-nav-hospital-wrap">
<div class="ls-nav-hospital-name">
{hospital_name}
</div>
</div>""",
                unsafe_allow_html=True,
            )

        # ====================================================
        # RIGHT
        # ====================================================

        with right_col:

            st.markdown(
                f"""<div class="ls-nav-profile-wrap">
{avatar_html}
<div class="ls-nav-user-text">
<div class="ls-nav-user-name">{user_name}</div>
<div class="ls-nav-user-role">{role_text}</div>
</div>
</div>""",
                unsafe_allow_html=True,
            )