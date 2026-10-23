"""
LungSightAI theme for the Streamlit web app.

All colors, fonts, radii and spacing come from shared/theme/tokens.json,
which is also mirrored by the mobile app (mobile_app/src/constants/theme.ts).

The tokens are exposed as CSS custom properties named --ls-*. Page CSS files
under shared/theme/css_content/ alias their own local variables to these
tokens, so a change in tokens.json restyles every page.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

import streamlit as st


TOKENS_PATH = Path(__file__).resolve().parent / "tokens.json"

# Icons in HTML snippets (e.g. .ls-nav-icon) use the "Material Symbols
# Rounded" font that Streamlit already bundles for st.button icons — do not
# @import another copy under the same family name.

DEFAULT_THEME = "light"
VALID_THEMES = {"light", "dark"}


# ============================================================
# TOKENS
# ============================================================

@lru_cache(maxsize=1)
def load_tokens() -> dict:
    """
    Return the parsed design tokens.
    """
    return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))


def _kebab(name: str) -> str:
    """primaryDark -> primary-dark"""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def get_colors(theme: str = None) -> dict:
    """
    Return the color tokens for a theme ('light' or 'dark').
    """
    theme = theme if theme in VALID_THEMES else get_theme()
    return load_tokens()["color"][theme]


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

# Older variable names that existing CSS still references.
LEGACY_ALIASES = {
    "--ls-text": "--ls-ink",
    "--ls-card": "--ls-surface",
    "--ls-accent": "--ls-primary",
    "--ls-bg": "--ls-background",
    "--ls-text-secondary": "--ls-text-soft",
    "--ls-text-muted": "--ls-muted",
    "--ls-primary-hover": "--ls-primary-dark",
}


def build_token_css(theme: str = DEFAULT_THEME) -> str:
    """
    Return the :root block of --ls-* custom properties for a theme.
    """
    tokens = load_tokens()
    colors = tokens["color"][theme if theme in VALID_THEMES else DEFAULT_THEME]
    font = tokens["font"]

    lines = [f"--ls-{_kebab(name)}: {value};" for name, value in colors.items()]

    lines += [
        f"{legacy}: var({target});"
        for legacy, target in LEGACY_ALIASES.items()
    ]

    family = f"'{font['family']}', system-ui, -apple-system, 'Segoe UI', sans-serif"
    lines += [
        f"--ls-font: {family};",
        f"--ls-font-display: {family};",
        "--ls-font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;",
    ]

    lines += [f"--ls-fs-{name}: {size}px;" for name, size in font["size"].items()]
    lines += [f"--ls-space-{step}: {size}px;" for step, size in tokens["space"].items()]
    lines += [f"--ls-radius-{name}: {size}px;" for name, size in tokens["radius"].items()]

    shadow_rgb = "0, 0, 0" if theme == "dark" else "18, 40, 58"
    lines += [
        f"--ls-shadow-sm: 0 1px 2px rgba({shadow_rgb}, 0.06);",
        f"--ls-shadow-md: 0 4px 12px rgba({shadow_rgb}, 0.08);",
        f"--ls-shadow-lg: 0 12px 32px rgba({shadow_rgb}, 0.12);",
    ]

    body = "\n    ".join(lines)
    return f":root {{\n    {body}\n}}"


BASE_CSS = """
.stApp,
.stApp p,
.stApp li,
.stApp label,
.stApp input,
.stApp textarea,
.stApp button {
    font-family: var(--ls-font);
}

.stApp {
    background: var(--ls-background);
    color: var(--ls-ink);
}

.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4 {
    font-family: var(--ls-font-display);
    color: var(--ls-ink);
    letter-spacing: -0.01em;
}

.stApp :focus-visible {
    outline: 2px solid var(--ls-primary);
    outline-offset: 2px;
}
"""


def get_theme_css(theme: str = None):
    """
    Return the global <style> block for the current theme.
    """
    theme = theme if theme in VALID_THEMES else get_theme()
    font_url = load_tokens()["font"]["googleFontsUrl"]

    return (
        "<style>\n"
        f"@import url('{font_url}');\n"
        f"{build_token_css(theme)}\n"
        f"{BASE_CSS}"
        "</style>"
    )


def apply_theme():
    """
    Inject the current LungSight theme CSS into Streamlit.
    """
    st.markdown(
        get_theme_css(),
        unsafe_allow_html=True,
    )
