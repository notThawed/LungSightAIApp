import streamlit as st


DEFAULT_THEME = "light"
VALID_THEMES = {"light", "dark"}


# ============================================================
# THEME STATE
# ============================================================

def initialize_theme():
    """
    Initialize the current theme in Streamlit session state.
    """
    if "theme" not in st.session_state:
        st.session_state.theme = DEFAULT_THEME


def get_theme():
    """
    Return the currently active theme.
    """
    initialize_theme()
    return st.session_state.theme


def set_theme(theme: str):
    """
    Set the current theme in Streamlit session state.
    """
    if theme not in VALID_THEMES:
        theme = DEFAULT_THEME

    st.session_state.theme = theme


def is_dark_mode():
    """
    Return True when the current theme is dark mode.
    """
    return get_theme() == "dark"


def is_light_mode():
    """
    Return True when the current theme is light mode.
    """
    return get_theme() == "light"


# ============================================================
# THEME CSS
# ============================================================

def get_theme_css():
    """
    Return the global CSS variables for the current theme.
    """

    theme = get_theme()

    if theme == "dark":

        return """
        <style>

        :root {
            /* ------------------------------------------------
               Application
            ------------------------------------------------ */

            --ls-bg: #0f1720;
            --ls-surface: #17212b;
            --ls-surface-soft: #1d2a35;

            /* ------------------------------------------------
               Text
            ------------------------------------------------ */

            --ls-text: #f1f5f9;
            --ls-text-secondary: #b6c2ce;
            --ls-text-muted: #7f8d9a;

            /* ------------------------------------------------
               Borders
            ------------------------------------------------ */

            --ls-border: #2d3b47;

            /* ------------------------------------------------
               Brand
            ------------------------------------------------ */

            --ls-primary: #4da3ff;
            --ls-primary-hover: #72b7ff;

            /* ------------------------------------------------
               Status
            ------------------------------------------------ */

            --ls-success: #4ade80;
            --ls-warning: #facc15;
            --ls-danger: #f87171;
            --ls-info: #60a5fa;
        }

        </style>
        """

    return """
    <style>

    :root {
        /* ------------------------------------------------
           Application
        ------------------------------------------------ */

        --ls-bg: #f4faff;
        --ls-surface: #ffffff;
        --ls-surface-soft: #eef6fc;

        /* ------------------------------------------------
           Text
        ------------------------------------------------ */

        --ls-text: #17212b;
        --ls-text-secondary: #64748b;
        --ls-text-muted: #94a3b8;

        /* ------------------------------------------------
           Borders
        ------------------------------------------------ */

        --ls-border: #dce7f0;

        /* ------------------------------------------------
           Brand
        ------------------------------------------------ */

        --ls-primary: #2f80ed;
        --ls-primary-hover: #1769c2;

        /* ------------------------------------------------
           Status
        ------------------------------------------------ */

        --ls-success: #16a34a;
        --ls-warning: #ca8a04;
        --ls-danger: #dc2626;
        --ls-info: #2563eb;
    }

    </style>
    """

def apply_theme():
    """
    Inject the current LungSight theme CSS into Streamlit.
    """
    st.markdown(
        get_theme_css(),
        unsafe_allow_html=True,
    )