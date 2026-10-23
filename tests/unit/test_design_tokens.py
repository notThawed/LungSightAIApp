"""
The design tokens in shared/theme/tokens.json must be the single source of
truth for the Streamlit theme, .streamlit/config.toml and the mobile app.
"""

import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOKENS = json.loads((ROOT / "shared/theme/tokens.json").read_text(encoding="utf-8"))
THEME_TS = (ROOT / "mobile_app/src/constants/theme.ts").read_text(encoding="utf-8")
CONFIG = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))
CSS_DIR = ROOT / "shared/theme/css_content"


def ts_color_block(theme):
    """Parse `light: { key: '#hex', ... }` out of theme.ts."""
    match = re.search(rf"\b{theme}: \{{(.*?)\}}", THEME_TS, re.S)
    assert match, f"{theme} block missing from theme.ts"
    return dict(re.findall(r"(\w+): '(#[0-9A-Fa-f]{6})'", match.group(1)))


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_mobile_colors_match_tokens(theme):
    assert ts_color_block(theme) == TOKENS["color"][theme]


def test_mobile_scales_match_tokens():
    for name, size in TOKENS["font"]["size"].items():
        assert re.search(rf"\b{name}: {size},", THEME_TS), f"FontSize.{name}"

    for step, size in TOKENS["space"].items():
        assert re.search(rf"\b{step}: {size},", THEME_TS), f"Spacing[{step}]"

    for name, size in TOKENS["radius"].items():
        assert re.search(rf"\b{name}: {size},", THEME_TS), f"Radius.{name}"


def test_streamlit_config_matches_tokens():
    light = TOKENS["color"]["light"]
    theme = CONFIG["theme"]

    assert theme["primaryColor"] == light["primary"]
    assert theme["backgroundColor"] == light["background"]
    assert theme["secondaryBackgroundColor"] == light["surfaceSoft"]
    assert theme["textColor"] == light["ink"]
    assert theme["borderColor"] == light["border"]
    assert theme["font"].startswith(TOKENS["font"]["family"] + ":")


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(
    "foreground",
    ["ink", "textSoft", "muted", "primary", "success", "warning", "danger", "info"],
)
def test_text_colors_meet_wcag_aa(theme, foreground):
    colors = TOKENS["color"][theme]
    assert contrast(colors[foreground], colors["surface"]) >= 4.5


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_button_text_meets_wcag_aa(theme):
    colors = TOKENS["color"][theme]
    assert contrast(colors["onPrimary"], colors["primary"]) >= 4.5


def test_streamlit_theme_emits_every_color_token():
    from shared.theme.streamlit_theme import build_token_css

    for theme in ("light", "dark"):
        css = build_token_css(theme)

        for value in TOKENS["color"][theme].values():
            assert value in css


CANONICAL_DEFINITION = re.compile(r"^\s*--ls-(primary|text|muted|border|background|card|success|warning|danger|radius|shadow)[a-z-]*\s*:", re.M)


@pytest.mark.parametrize("css_file", sorted(CSS_DIR.rglob("*.css")), ids=lambda p: p.name)
def test_page_css_does_not_redefine_canonical_tokens(css_file):
    """Page CSS may alias tokens but must not override them with stale values."""
    assert not CANONICAL_DEFINITION.search(css_file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("css_file", sorted(CSS_DIR.rglob("*.css")), ids=lambda p: p.name)
def test_page_css_uses_single_font_family(css_file):
    text = css_file.read_text(encoding="utf-8")
    assert "Fraunces" not in text
    assert "Barlow" not in text
