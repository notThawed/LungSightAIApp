"""
Audit Logs — Hospital Admin (own hospital) and Superadmin (platform-wide).

All scoping happens in backend.audit, which re-reads the viewer's role and
hospital from the database on every query and export. Nothing on this page
decides which hospital's rows are visible.
"""

import logging
from datetime import date, timedelta

import streamlit as st

from backend import audit
from backend.fetches import get_all_hospitals, get_hospital_staff
from streamlit_app.components.ui import (
    empty_state,
    format_date,
    full_name,
    page_header,
    metric_card,
    section_title,
    pill,
    show_rows,
    safe,
)
from shared.assets import load_css


logger = logging.getLogger("lungsight.audit")

PAGE_SIZE = 25
PAGE_KEY = "audit_logs_page"
FILTER_SIG_KEY = "audit_logs_filter_sig"
EXPORT_KEY = "audit_logs_export"

ANY = "Any"
PLATFORM = "Platform-wide (no hospital)"


@st.cache_data(ttl=300, show_spinner=False)
def _hospital_options():
    try:
        hospitals = get_all_hospitals() or []
    except Exception:
        hospitals = []

    return {
        h.get("hospital_name") or str(h.get("hospital_id")): str(h.get("hospital_id"))
        for h in hospitals
        if h.get("hospital_id")
    }


@st.cache_data(ttl=300, show_spinner=False)
def _actor_options(hospital_id):
    if not hospital_id:
        return {}

    try:
        staff = get_hospital_staff(hospital_id) or []
    except Exception:
        staff = []

    return {
        (full_name(s.get("user_fname"), s.get("user_lname")) or "User")
        + f" · {str(s.get('user_id'))[:8]}": str(s.get("user_id"))
        for s in staff
        if s.get("user_id")
    }


def _render_filters(scope):
    with st.container(key="sa_audit_filters"):
        f_head_l, f_head_r = st.columns([3, 1], vertical_alignment="center")
        with f_head_l:
            section_title("Audit Event Filters", "Filter security events, authentication attempts, and operational records.")
        with f_head_r:
            if st.button("Reset Filters", icon=":material/restart_alt:", key="audit_reset_btn", width="stretch"):
                st.session_state.pop("audit_from", None)
                st.session_state.pop("audit_to", None)
                st.session_state.pop("audit_category", None)
                st.session_state.pop("audit_outcome", None)
                st.session_state.pop("audit_hospital", None)
                st.session_state.pop("audit_actor", None)
                st.session_state.pop("audit_search", None)
                st.rerun()

        today = date.today()

        c1, c2, c3, c4 = st.columns(4)

        date_from = c1.date_input("From Date", value=today - timedelta(days=30), key="audit_from")
        date_to = c2.date_input("To Date", value=today, key="audit_to")
        category = c3.selectbox("Event Category", [ANY] + audit.CATEGORIES, key="audit_category")
        outcome = c4.selectbox("Outcome", [ANY] + list(audit.OUTCOMES), key="audit_outcome")

        filters = {
            "date_from": date_from,
            "date_to": date_to,
            "category": None if category == ANY else category,
            "outcome": None if outcome == ANY else outcome,
        }

        hospital_names = {}

        if scope["platform"]:
            d1, d2, d3 = st.columns([1.3, 1.3, 1.4])
            hospital_names = _hospital_options()
            hospital_choice = d1.selectbox(
                "Hospital Facility",
                [ANY, PLATFORM] + sorted(hospital_names),
                key="audit_hospital",
            )
            if hospital_choice == PLATFORM:
                filters["hospital_id"] = "platform"
            elif hospital_choice != ANY:
                filters["hospital_id"] = hospital_names[hospital_choice]
            actor_hospital = filters.get("hospital_id") if filters.get("hospital_id") != "platform" else None
            actor_col, search_col = d2, d3
        else:
            d2, d3 = st.columns(2)
            actor_hospital = scope["hospital_id"]
            actor_col, search_col = d2, d3

        actors = _actor_options(actor_hospital)
        actor_choice = actor_col.selectbox("Actor", [ANY] + sorted(actors), key="audit_actor")
        filters["actor_user_id"] = None if actor_choice == ANY else actors[actor_choice]

        filters["search"] = search_col.text_input(
            "Search event type or ID",
            key="audit_search",
            placeholder="e.g. auth.login or record ID",
        )

        return filters, {v: k for k, v in hospital_names.items()}


def _filter_signature(filters):
    return tuple(sorted((k, str(v)) for k, v in filters.items()))


def _render_detail(row, actor_name, hospital_label):
    outcome_raw = str(row.get("outcome") or "").lower()
    if outcome_raw in ("success", "approved", "completed"):
        outcome_pill = pill("SUCCESS", "green")
    elif outcome_raw in ("failure", "failed", "denied", "error"):
        outcome_pill = pill(outcome_raw.upper(), "red")
    else:
        outcome_pill = pill(outcome_raw.upper() if outcome_raw else "UNKNOWN", "amber")

    st.markdown(
        f"<div class='sa-audit-inspector'>"
        f"<div class='sa-audit-inspector-header'>"
        f"<div class='sa-audit-inspector-title'>"
        f"<span class='material-symbols-rounded' style='color:#2563EB;'>manage_search</span>"
        f"<span>Event Inspector: {safe(row.get('event_type'))}</span>"
        f"</div>"
        f"{outcome_pill}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    show_rows([
        ("Timestamp (UTC)", row.get("created_at")),
        ("Event Type", row.get("event_type")),
        ("Outcome", row.get("outcome")),
        ("Actor", actor_name),
        ("Actor ID", row.get("actor_user_id") or "System"),
        ("Facility", hospital_label),
        ("Target", f"{row.get('target_type') or '—'} · {row.get('target_id') or '—'}"),
    ])

    if row.get("metadata"):
        st.caption("Event Payload & Metadata")
        st.json(row["metadata"], expanded=True)


def _render_export(filters, signature):
    cached = st.session_state.get(EXPORT_KEY)

    if cached and cached.get("sig") != signature:
        st.session_state.pop(EXPORT_KEY, None)
        cached = None

    with st.container(key="sa_audit_export_container"):
        st.markdown(
            f"<div class='sa-audit-export-card'>"
            f"<div>"
            f"<div style='font-weight:700; color:#0F172A; font-size:0.95rem;'>Compliance &amp; Security CSV Export</div>"
            f"<div style='font-size:0.8rem; color:#64748B;'>Generate an immutable, timestamped CSV export matching current search filters.</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if not cached:
            if st.button("Generate CSV Export", icon=":material/download:", key="audit_export_prepare", type="primary"):
                try:
                    with st.spinner("Preparing export dataset..."):
                        data, count, truncated = audit.export_audit_logs_csv(filters)
                    st.session_state[EXPORT_KEY] = {
                        "sig": signature,
                        "data": data,
                        "count": count,
                        "truncated": truncated,
                    }
                    st.rerun()
                except audit.AuditAccessDenied as exc:
                    st.error(str(exc))
                except ValueError as exc:
                    st.warning(str(exc))
                except Exception as exc:
                    logger.error("audit export failed: %s", type(exc).__name__)
                    st.error("The export could not be prepared. Please try again.")
            return

        caption = f"{cached['count']:,} events ready for export."
        if cached["truncated"]:
            caption += f" Export is limited to the newest {audit.EXPORT_ROW_LIMIT:,} rows; narrow filters for smaller sets."
        st.caption(caption)

        st.download_button(
            "Download Audit Log CSV",
            data=cached["data"],
            file_name=f"audit_logs_{date.today().isoformat()}.csv",
            mime="text/csv",
            icon=":material/download:",
            key="audit_export_download",
            type="primary",
        )


def show():
    load_css("audit_logs.css")

    try:
        scope = audit.get_viewer_scope()
    except audit.AuditAccessDenied as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        logger.error("audit scope check failed: %s", type(exc).__name__)
        st.error("Unable to verify your access right now. Please try again.")
        return

    page_header(
        "Audit Logs",
        (
            "Platform-wide security events, administrative activities, and audit trails."
            if scope["platform"]
            else "Hospital security events, patient access records, and staff activity trails."
        ),
    )

    filters, hospital_label_by_id = _render_filters(scope)

    signature = _filter_signature(filters)

    if st.session_state.get(FILTER_SIG_KEY) != signature:
        st.session_state[FILTER_SIG_KEY] = signature
        st.session_state[PAGE_KEY] = 1

    page = st.session_state.get(PAGE_KEY, 1)

    try:
        with st.spinner("Loading audit logs..."):
            result = audit.query_audit_logs(filters, page=page, page_size=PAGE_SIZE)
    except audit.AuditAccessDenied as exc:
        st.error(str(exc))
        return
    except ValueError as exc:
        st.warning(str(exc))
        return
    except Exception as exc:
        logger.error("audit query failed: %s", type(exc).__name__)
        st.error("Audit logs could not be loaded. Please try again.")
        return

    rows = result["rows"]
    total = result["total"]

    # ---------------- Top KPI Metrics ----------------
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Total Events Logged", total, "history", "teal")
    with k2:
        scope_str = "Platform-wide" if scope["platform"] else "Hospital Facility"
        metric_card("Audited Scope", scope_str, "domain", "blue")
    with k3:
        period_str = f"{filters['date_from'].strftime('%b %d')} - {filters['date_to'].strftime('%b %d')}"
        metric_card("Timeframe", period_str, "calendar_month", "green")
    with k4:
        metric_card("Events on Page", len(rows), "list_alt", "amber")

    st.markdown("<div style='margin-bottom: 0.5rem;'></div>", unsafe_allow_html=True)

    if not rows:
        empty_state("No audit events match these filters. Try expanding the date range or clearing specific filter criteria.")
        return

    try:
        names = audit.get_actor_names(r.get("actor_user_id") for r in rows)
    except Exception:
        names = {}

    def actor_label(row):
        actor = row.get("actor_user_id")
        if not actor:
            return "System"
        return names.get(str(actor), str(actor)[:8])

    def hospital_label(row):
        hospital = row.get("hospital_id")
        if not hospital:
            return "Platform-wide"
        return hospital_label_by_id.get(str(hospital), str(hospital)[:8])

    table = []
    for row in rows:
        entry = {
            "Time (PH)": format_date(row.get("created_at"), with_time=True),
            "Event": row.get("event_type"),
            "Outcome": row.get("outcome"),
            "Actor": actor_label(row),
            "Target": f"{row.get('target_type') or '—'} · {str(row.get('target_id') or '—')[:12]}",
        }
        if scope["platform"]:
            entry["Hospital"] = hospital_label(row)
        table.append(entry)

    # Toolbar with count badge
    st.markdown(
        f"<div class='sa-audit-toolbar'>"
        f"<span class='sa-audit-count-badge'>Showing <b>{len(rows)}</b> of <b>{total:,}</b> events</span>"
        f"<span style='font-size:0.8rem; color:#64748B;'>Click any row below to inspect full event payload</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    selection = st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=f"audit_table_{page}",
    )

    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)

    p1, p2, p3 = st.columns([1, 2, 1], vertical_alignment="center")

    if p1.button("Previous", disabled=page <= 1, key="audit_prev", width="stretch"):
        st.session_state[PAGE_KEY] = page - 1
        st.rerun()

    p2.markdown(
        f"<div style='text-align:center; font-size:0.88rem; font-weight:600; color:#475569;'>"
        f"Page {page} of {pages} · {total:,} total records"
        f"</div>",
        unsafe_allow_html=True,
    )

    if p3.button("Next", disabled=page >= pages, key="audit_next", width="stretch"):
        st.session_state[PAGE_KEY] = page + 1
        st.rerun()

    selected_rows = getattr(getattr(selection, "selection", None), "rows", None) or []

    if selected_rows:
        row = rows[selected_rows[0]]
        _render_detail(row, actor_label(row), hospital_label(row))
    else:
        st.caption("ℹ️ Click any row in the audit table to inspect full event metadata, actor identity, and system payloads.")

    st.divider()

    _render_export(filters, signature)
