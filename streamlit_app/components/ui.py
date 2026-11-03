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

# The Philippines has no daylight saving, so a fixed UTC+8 offset is enough
PH_TIME = timezone(timedelta(hours=8))


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
    """Page title with optional action and a standard refresh button."""
    if action_label:
        left, action_col, refresh_col = st.columns(
            [4, 1.2, 0.65], vertical_alignment="center"
        )
    else:
        left, refresh_col = st.columns(
            [4, 0.65], vertical_alignment="center"
        )

    left.markdown(
        f"<p class='sa-page-title'>{title}</p>"
        f"<p class='sa-page-caption'>{caption}</p>",
        unsafe_allow_html=True,
    )

    action_clicked = False
    if action_label:
        action_clicked = action_col.button(
            action_label,
            key=action_key,
            icon=f":material/{action_icon}:" if action_icon else None,
            type="primary",
            width="stretch",
        )

    title_key = "_".join(
        part.lower() for part in str(title).split() if part
    )
    with refresh_col:
        refresh_button(
            key=f"page_refresh_{title_key}",
            label_visibility="collapsed",
        )

    return action_clicked


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
# MODERN COMPONENTS (Ant Design & Shadcn UI)
# ============================================================

def modern_tabs(
    items,
    index=0,
    variant="default",
    size="sm",
    color=None,
    use_container_width=False,
    key=None,
):
    """
    Renders modern, clean tabs using streamlit-antd-components.

    items can be:
      - List of strings: ["Plans", "Add plan", "Inactive plans"]
      - List of dicts: [
            {"label": "Pending", "icon": "hourglass-split", "tag": 3, "tag_color": "orange"},
            {"label": "Approved", "icon": "check-circle", "tag": 12, "tag_color": "green"}
        ]
      - List of sac.TabsItem objects

    Returns the label of the currently selected tab.
    """
    try:
        import streamlit_antd_components as sac

        processed_items = []
        for item in items:
            if isinstance(item, str):
                processed_items.append(sac.TabsItem(label=item))
            elif isinstance(item, dict):
                tag_obj = None
                if "tag" in item and item["tag"] is not None:
                    tag_obj = sac.Tag(
                        label=str(item["tag"]),
                        color=item.get("tag_color", "blue"),
                        bordered=True,
                    )
                processed_items.append(
                    sac.TabsItem(
                        label=item.get("label", ""),
                        icon=item.get("icon"),
                        tag=tag_obj,
                        disabled=item.get("disabled", False),
                    )
                )
            elif isinstance(item, sac.TabsItem):
                processed_items.append(item)

        selected = sac.tabs(
            items=processed_items,
            index=index,
            variant=variant,
            size=size,
            color=color,
            use_container_width=use_container_width,
            key=key,
        )
        return selected
    except Exception:
        import streamlit_shadcn_ui as ui
        options = [
            item if isinstance(item, str) else item.get("label", "")
            for item in items
        ]
        return ui.tabs(options=options, default=options[index] if options else None, key=key)


def modern_badge(text, tone="grey", icon=None, bordered=True, key=None):
    """
    Renders a modern, clean tag / badge using streamlit-antd-components.
    tones: green, red, amber, orange, blue, teal, cyan, purple, grey, gray.
    """
    try:
        import streamlit_antd_components as sac

        tone_map = {
            "green": "green",
            "red": "red",
            "amber": "orange",
            "orange": "orange",
            "blue": "blue",
            "teal": "cyan",
            "cyan": "cyan",
            "purple": "purple",
            "grey": "gray",
            "gray": "gray",
        }
        color = tone_map.get(str(tone).lower(), "gray")
        return sac.tags(
            [
                sac.Tag(
                    label=str(text),
                    color=color,
                    icon=icon,
                    bordered=bordered,
                    radius="sm",
                )
            ],
            key=key,
        )
    except Exception:
        st.markdown(pill(text, tone), unsafe_allow_html=True)


def modern_button(
    label,
    key=None,
    variant="default",
    size="default",
    disabled=False,
    width="stretch",
    icon=None,
):
    """
    Renders a modern Shadcn UI button with fallbacks.
    variant: 'default', 'secondary', 'destructive', 'outline', 'ghost', 'link'.
    """
    try:
        import streamlit_shadcn_ui as ui
        return ui.button(
            label,
            key=key,
            variant=variant,
            size=size,
            disabled=disabled,
            width=width,
        )
    except Exception:
        type_val = "primary" if variant in ("default", "destructive") else "secondary"
        return st.button(
            label,
            key=key,
            type=type_val,
            disabled=disabled,
            icon=f":material/{icon}:" if icon else None,
            width=width,
        )


# ============================================================
# DIALOG BUTTONS AND MESSAGES
# ============================================================

def close_button(key):
    if modern_button("Close", key=key, variant="outline", width="stretch"):
        st.rerun()


def confirm_buttons(key, confirm_label, confirm_variant="default"):
    """Cancel + confirm. Returns True when confirm is clicked.
    A key that starts with 'delete' or 'remove' makes the confirm button destructive red."""
    cancel_col, confirm_col = st.columns(2)
    is_delete = "delete" in key.lower() or "remove" in key.lower()

    with cancel_col:
        if modern_button("Cancel", key=f"cancel_{key}", variant="outline", width="stretch"):
            st.rerun()

    with confirm_col:
        variant = "destructive" if is_delete else confirm_variant
        return modern_button(
            confirm_label, key=f"confirm_{key}", variant=variant, width="stretch"
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


def refresh_button(
    key,
    label="Refresh",
    width="content",
    label_visibility="collapsed",
):
    """Render the shared circular refresh control and reload fresh data."""
    st.markdown(
        """<style>
        /* The circular button container */
        [class*="st-key-ui_refresh_"] button {
            width: 2.75rem !important;
            min-width: 2.75rem !important;
            height: 2.75rem !important;
            min-height: 2.75rem !important;
            padding: 0 !important;
            border: 1px solid rgba(15, 124, 136, 0.24);
            border-radius: 50% !important;
            background: #e8f4f6;
            color: #0f7c88;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
            transition: background 140ms ease, box-shadow 140ms ease,
                transform 140ms ease;
        }
        
        /* Hover effect */
        [class*="st-key-ui_refresh_"] button:hover {
            border-color: #0f7c88;
            background: #d8eef0;
            color: #075e68;
            box-shadow: 0 4px 12px rgba(15, 124, 136, 0.18);
            transform: rotate(-12deg);
        }

        /* Force the inner wrapper to center the icon perfectly */
        [class*="st-key-ui_refresh_"] button > div {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            height: 100% !important;
        }

        /* Hide the text visually but keep it in the DOM for Streamlit */
        [class*="st-key-ui_refresh_"] button p {
            display: none !important;
        }
        
        /* Remove any margins from the icon that might offset it */
        [class*="st-key-ui_refresh_"] button [data-testid="stIconMaterial"] {
            margin: 0 !important;
            padding: 0 !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    with st.container(key=f"ui_refresh_{key}"):
        clicked = st.button(
            label,
            key=key,
            icon=":material/refresh:",
            type="secondary",
            width=width,
            help="Reload this page with the latest data",
        )
    if clicked:
        refresh_data()
    return clicked




def show_flash_message():
    message = st.session_state.pop("sa_flash", None)

    if message:
        st.toast(message)

# ============================================================
# RICHER CELLS (used by physician follow-up pages)
# ============================================================

def status_badge_cell(column, label, tone="grey", sub=""):
    """
    A pill with an optional caption underneath, used inside table rows.
    """
    sub_html = f"<small class='sa-cell-sub'>{safe(sub)}</small>" if sub else ""

    column.markdown(
        "<div class='sa-badgecell'>"
        f"{pill(label, tone)}"
        f"{sub_html}"
        "</div>",
        unsafe_allow_html=True,
    )


def meta_cell(column, primary, secondary=""):
    """
    A two-line cell — small bold primary on top, muted caption below.
    """
    secondary_html = (
        f"<small class='sa-cell-sub'>{safe(secondary)}</small>"
        if secondary
        else ""
    )

    column.markdown(
        "<div class='sa-metacell'>"
        f"<b>{safe(primary)}</b>"
        f"{secondary_html}"
        "</div>",
        unsafe_allow_html=True,
    )


def kpi_strip(items):
    """
    A horizontal strip of KPI blocks.

    items = [
        ("Patients With Follow-Ups", 12, "blue"),
        ("Upcoming", 5, "amber"),
        ...
    ]
    """
    blocks = "".join(
        f"<div class='sa-kpi sa-kpi-{tone}'>"
        f"<div class='sa-kpi-value'>{value}</div>"
        f"<div class='sa-kpi-label'>{safe(label)}</div>"
        "</div>"
        for label, value, tone in items
    )

    st.markdown(
        f"<div class='sa-kpi-strip'>{blocks}</div>",
        unsafe_allow_html=True,
    )


def followup_card_open(key):
    """
    Opens a styled card wrapper. Pair with followup_card_close().
    Because Streamlit doesn't render HTML containers around real widgets,
    we simulate the card by opening a st.container with a key the CSS targets.
    """
    return st.container(key=key)


def patient_summary_card(patient, meta_rows=None):
    """
    Renders a polished patient summary card.
    """
    name = full_name(
        patient.get("first_name"),
        patient.get("middle_name"),
        patient.get("last_name"),
        patient.get("suffix"),
    )

    code = (
        patient.get("patient_code")
        or patient.get("patient_id")
        or "—"
    )

    rows_html_str = ""

    if meta_rows:
        rows_html_str = "".join(
            f"<div class='sa-summary-row'>"
            f"<span>{safe(label)}</span>"
            f"<b>{safe(value)}</b>"
            "</div>"
            for label, value in meta_rows
        )

    st.markdown(
        "<div class='sa-summary-card'>"
        f"<div class='sa-summary-avatar'>{initials(name)}</div>"
        "<div class='sa-summary-body'>"
        f"<div class='sa-summary-name'>{safe(name)}</div>"
        f"<div class='sa-summary-code'>{safe(code)}</div>"
        f"<div class='sa-summary-rows'>{rows_html_str}</div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def follow_up_entry_header(scheduled_at, status, tone="grey"):
    """
    Renders a compact header for a follow-up entry inside the case file.
    """
    st.markdown(
        "<div class='sa-fu-header'>"
        f"<div class='sa-fu-when'>{safe(scheduled_at)}</div>"
        f"<div class='sa-fu-status'>{pill(status, tone)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
