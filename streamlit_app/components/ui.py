"""
Reusable helpers for the system administrator pages.

Save as: streamlit_app/components/ui.py

Every page does:
    from streamlit_app.components.ui import load_css, page_header, metric_card, ...
    load_css("manage_users.css")        # base.css is always loaded first
"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CSS_DIR = (
    PROJECT_ROOT / "shared" / "theme" / "css_content" / "system_admin_css"
)

# The Philippines has no daylight saving, so a fixed UTC+8 offset is enough
PH_TIME = timezone(timedelta(hours=8))


# ============================================================
# CSS
# ============================================================

def load_css(*names):
    """Load base.css plus any page-specific css files from system_admin_css/."""
    css = ""

    for name in ("base.css", *names):
        path = CSS_DIR / name

        if path.exists():
            css += path.read_text(encoding="utf-8") + "\n"

    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ============================================================
# TEXT HELPERS
# ============================================================

def safe(value):
    """Escape text before it goes inside HTML. Empty values show a dash."""
    text = escape(str(value if value is not None else "").strip())
    return text or "—"


def peso(amount):
    """1500 -> ₱1,500.00"""
    return f"₱{float(amount or 0):,.2f}"


def limit_text(value):
    """None means 'no limit' in the database."""
    return "Unlimited" if value is None else f"{value:,}"


def full_name(*parts):
    """full_name('Maria', '', 'Santos') -> 'Maria Santos'"""
    return " ".join(str(part).strip() for part in parts if part and str(part).strip())


def initials(name):
    """'Maria Santos' -> 'MS'"""
    words = str(name or "").split()

    if not words:
        return "?"

    if len(words) == 1:
        return words[0][0].upper()

    return (words[0][0] + words[-1][0]).upper()


def format_date(value, with_time=False):
    """Any date, datetime or ISO string -> 'Sep 20, 2026' (optionally with time)."""
    if not value:
        return "—"

    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, date):
        moment = datetime(value.year, value.month, value.day)
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)

    if moment.tzinfo:
        moment = moment.astimezone(PH_TIME)

    text = f"{moment:%b} {moment.day}, {moment.year}"

    if with_time:
        text += " · " + moment.strftime("%I:%M %p").lstrip("0")

    return text


# ============================================================
# SMALL HTML PIECES
# ============================================================

def pill(text, tone="grey"):
    """A small colored label. tone: green, amber, red, blue, teal, grey."""
    return f"<span class='sa-pill sa-pill-{tone}'>{safe(text)}</span>"


def rows_html(rows):
    """Label / value rows, e.g. [("Email", "a@b.com"), ("Role", "Admin")]."""
    items = "".join(
        f"<div class='sa-row'><span>{label}</span><b>{safe(value)}</b></div>"
        for label, value in rows
    )
    return f"<div class='sa-rows'>{items}</div>"


def show_rows(rows):
    st.markdown(rows_html(rows), unsafe_allow_html=True)


def note(text, tone=""):
    """A colored message box. tone: '', green, red, amber."""
    st.markdown(
        f"<div class='sa-note sa-note-{tone}'>{text}</div>",
        unsafe_allow_html=True,
    )


def empty_state(text):
    st.markdown(f"<div class='sa-empty'>{text}</div>", unsafe_allow_html=True)


def section_title(title, caption=""):
    caption_html = f"<p class='sa-section-caption'>{caption}</p>" if caption else ""

    st.markdown(
        f"<p class='sa-section-title'>{title}</p>{caption_html}",
        unsafe_allow_html=True,
    )


def field(label, value):
    """A label with a (possibly long) text value underneath."""
    st.markdown(
        f"<div class='sa-field'><span>{label}</span><p>{safe(value)}</p></div>",
        unsafe_allow_html=True,
    )


# ============================================================
# PAGE HEADER AND METRIC CARD
# ============================================================

def page_header(title, caption, action_label=None, action_key=None, action_icon=None):
    """Title and caption, with an optional main button on the right.
    Returns True when that button was clicked."""
    left, right = st.columns([4, 1.2], vertical_alignment="center")

    left.markdown(
        f"<p class='sa-page-title'>{title}</p>"
        f"<p class='sa-page-caption'>{caption}</p>",
        unsafe_allow_html=True,
    )

    if action_label:
        return right.button(
            action_label,
            key=action_key,
            icon=f":material/{action_icon}:" if action_icon else None,
            type="primary",
            width="stretch",
        )

    return False


def metric_card(title, value, icon, tone=""):
    """icon is a Material icon name, e.g. 'groups'. tone: amber, green, red, blue."""
    st.markdown(
        f"<div class='sa-metric sa-metric-{tone}'>"
        f"<span class='sa-metric-icon'>{icon}</span>"
        "<div>"
        f"<div class='sa-metric-title'>{title}</div>"
        f"<div class='sa-metric-value'>{value}</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )


# ============================================================
# TABLE
#
#   with st.container(key="sa_table_users"):
#       table_header(["Name", "Role", ""], [3, 2, 1], "users")
#       for user in users:
#           with table_row(f"users_{user['id']}", [3, 2, 1]) as cols:
#               name_cell(cols[0], "Maria Santos", "maria@mail.com")
#               text_cell(cols[1], "Admin")
#               cols[2].button("Edit", key=...)
# ============================================================

def table_header(labels, widths, key):
    with st.container(key=f"sa_head_{key}"):
        for column, label in zip(st.columns(widths), labels):
            column.markdown(f"<span class='sa-th'>{label}</span>", unsafe_allow_html=True)


@contextmanager
def table_row(key, widths):
    with st.container(key=f"sa_row_{key}"):
        yield st.columns(widths, vertical_alignment="center")


def text_cell(column, value, strong=False, muted=False):
    css = "sa-cell"
    css += " sa-cell-strong" if strong else ""
    css += " sa-cell-muted" if muted else ""

    column.markdown(f"<div class='{css}'>{safe(value)}</div>", unsafe_allow_html=True)


def name_cell(column, name, sub=""):
    """Show a name and optional email without the initials avatar."""
    sub_html = f"<small>{safe(sub)}</small>" if sub else ""

    column.markdown(
        "<div class='sa-namecell'>"
        f"<div><b>{safe(name)}</b>{sub_html}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def pill_cell(column, text, tone="grey"):
    column.markdown(pill(text, tone), unsafe_allow_html=True)


# ============================================================
# DIALOG BUTTONS AND MESSAGES
# ============================================================

def close_button(key):
    if st.button("Close", key=key, width="stretch"):
        st.rerun()


def confirm_buttons(key, confirm_label):
    """Cancel + confirm. Returns True when confirm is clicked.
    A key that starts with 'delete' makes the confirm button red."""
    cancel_col, confirm_col = st.columns(2)

    if cancel_col.button("Cancel", key=f"cancel_{key}", width="stretch"):
        st.rerun()

    return confirm_col.button(
        confirm_label, key=f"confirm_{key}", type="primary", width="stretch"
    )


def remember(message):
    """Call this after a successful save.
    Shows a small toast after the next reload AND clears the cached database
    reads (see data.py) so the page loads fresh data."""
    st.cache_data.clear()
    st.session_state["sa_flash"] = message


def refresh_data():
    """For 'Refresh' buttons: forget the cached reads and reload the page."""
    st.cache_data.clear()
    st.rerun()


def show_flash_message():
    message = st.session_state.pop("sa_flash", None)

    if message:
        st.toast(message)