"""
LungSight — hospital theme utilities.

Applies the current hospital's theme color to the
whole Streamlit app by overriding the CSS variables
that every LungSight stylesheet already uses
(--ls-*, --ap-*, --sb-*, --geo-*, --ss-*, --rx-*, --sa-*).

Usage (in your app entry point, once per page render):

    from shared.theme.theme_utils import apply_theme
    apply_theme()
"""

import streamlit as st


DEFAULT_THEME_COLOR = "#0f7c88"


def get_active_theme_color():
    """
    Return the theme color for the current session.

    Priority:
    1. st.session_state.user["hospital_theme_color"]
    2. DEFAULT_THEME_COLOR
    """

    user = st.session_state.get("user") or {}

    color = user.get("hospital_theme_color")

    if not color:
        return DEFAULT_THEME_COLOR

    color = str(color).strip()

    if (
        len(color) == 7
        and color.startswith("#")
    ):
        return color

    return DEFAULT_THEME_COLOR


def _hex_to_rgb(hex_color):
    """Return (r, g, b) ints for a #RRGGBB hex."""

    hex_color = hex_color.lstrip("#")

    try:
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
    except (ValueError, IndexError):
        return (15, 124, 136)


def _rgb_to_hex(r, g, b):
    """Return #rrggbb from ints, clamped to 0-255."""

    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))

    return f"#{r:02x}{g:02x}{b:02x}"


def _lighten(hex_color, amount=0.85):
    """Blend toward white. amount=0 → same, amount=1 → white."""

    r, g, b = _hex_to_rgb(hex_color)

    r = r + (255 - r) * amount
    g = g + (255 - g) * amount
    b = b + (255 - b) * amount

    return _rgb_to_hex(r, g, b)


def _darken(hex_color, amount=0.2):
    """Blend toward black. amount=0 → same, amount=1 → black."""

    r, g, b = _hex_to_rgb(hex_color)

    r = r * (1 - amount)
    g = g * (1 - amount)
    b = b * (1 - amount)

    return _rgb_to_hex(r, g, b)


def apply_theme():
    """
    Inject the hospital theme color as CSS variables,
    overriding every per-file variable family that the
    LungSight stylesheets already use.

    Call this ONCE per page render, before any page
    content is drawn.
    """

    color = get_active_theme_color()

    color_dark = _darken(color, 0.20)     # hover
    color_darker = _darken(color, 0.35)   # deep hover
    color_light = _lighten(color, 0.40)   # soft accent
    color_soft = _lighten(color, 0.85)    # very light tint (backgrounds)

    r, g, b = _hex_to_rgb(color)

    css = f"""
    <style>
    :root,
    html:root,
    html:root * {{
        /* ------------------------------------------------- */
        /* --ls-* family (application, navbar, subscription, */
        /*          manage_application)                      */
        /* ------------------------------------------------- */
        --ls-primary:        {color};
        --ls-primary-dark:   {color_dark};
        --ls-primary-soft:   {color_soft};
        --ls-accent:         {color_light};

        --ls-nav-accent:      {color};
        --ls-nav-accent-soft: {color_soft};

        /* ------------------------------------------------- */
        /* --ap-* family (profile, setup_wizard)             */
        /* ------------------------------------------------- */
        --ap-teal:      {color};
        --ap-teal-dark: {color_dark};
        --ap-teal-soft: {color_soft};

        /* ------------------------------------------------- */
        /* --sb-* family (sidebar)                           */
        /* ------------------------------------------------- */
        --sb-accent:      {color};
        --sb-accent-dark: {color_dark};
        --sb-accent-bg:   {color_soft};

        /* ------------------------------------------------- */
        /* --geo-* family (hospital_info)                    */
        /* ------------------------------------------------- */
        --geo-primary:      {color};
        --geo-primary-dark: {color_dark};
        --geo-primary-soft: {color_soft};
        --geo-accent:       {color_light};

        /* ------------------------------------------------- */
        /* --ss-* family (subscription_settings)             */
        /* ------------------------------------------------- */
        --ss-teal:      {color};
        --ss-teal-dark: {color_dark};
        --ss-teal-soft: {color_soft};

        /* ------------------------------------------------- */
        /* --rx-* family (radtech/analyze)                   */
        /* ------------------------------------------------- */
        --rx-primary: {color};
        --rx-accent:  {color_light};

        /* ------------------------------------------------- */
        /* --sa-* family (system_admin/base)                 */
        /* ------------------------------------------------- */
        --sa-teal:      {color};
        --sa-teal-dark: {color_dark};
        --sa-teal-soft: {color_soft};

        /* ------------------------------------------------- */
        /* RGB form, for rgba() usage in future CSS          */
        /* ------------------------------------------------- */
        --ls-primary-rgb: {r}, {g}, {b};
    }}

    /* ---------------------------------------------------- */
    /* Streamlit built-in components                        */
    /* ---------------------------------------------------- */

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {{
        background-color: var(--ls-primary) !important;
        border-color: var(--ls-primary) !important;
        color: #ffffff !important;
    }}

    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover {{
        background-color: var(--ls-primary-dark) !important;
        border-color: var(--ls-primary-dark) !important;
    }}

    a {{
        color: var(--ls-primary) !important;
    }}

    *:focus-visible {{
        outline-color: var(--ls-primary) !important;
    }}

    .stSlider [role="slider"] {{
        background-color: var(--ls-primary) !important;
    }}

    .stProgress > div > div > div > div {{
        background-color: var(--ls-primary) !important;
    }}

    .stTabs [aria-selected="true"] {{
        color: var(--ls-primary) !important;
    }}

    .stCheckbox label span[role="checkbox"][aria-checked="true"],
    .stToggle label span[role="checkbox"][aria-checked="true"] {{
        background-color: var(--ls-primary) !important;
        border-color: var(--ls-primary) !important;
    }}

    div[role="radiogroup"] label > div:first-child {{
        border-color: var(--ls-primary) !important;
    }}
    </style>
    """

    st.markdown(css, unsafe_allow_html=True)