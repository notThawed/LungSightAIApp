"""
Email Notifications — delivery history of LungSight emails.

Hospital Admin: emails to their own hospital's admin accounts. Superadmin:
all emails, with manual retry of failed ones. Scoping and masking happen in
backend.notifications.
"""

import logging
from datetime import datetime, time, timedelta

import streamlit as st

from backend import audit, notifications
from backend.reports.periods import REPORT_TZ
from streamlit_app.components.ui import (
    empty_state,
    format_date,
    page_header,
    metric_card,
    section_title,
    pill,
    show_rows,
    safe,
)
from shared.assets import load_css


logger = logging.getLogger("lungsight.notifications")

PAGE_SIZE = 25
PAGE_KEY = "notification_page"
SIG_KEY = "notification_filter_sig"
ANY = "Any"

STATUS_HELP = {
    "sent": "Accepted by the email provider (awaiting webhook confirmation).",
    "delivered": "Delivery confirmed by provider webhook event.",
    "failed": "Delivery attempt failed (can be queued for retry).",
    "skipped": "Not sent: saved state or recipient account no longer eligible.",
    "suppressed": "Not sent: email address previously bounced or unsubscribed.",
}


def _filters(scope):
    with st.container(key="sa_notif_filters"):
        f_head_l, f_head_r = st.columns([3, 1], vertical_alignment="center")
        with f_head_l:
            section_title("Notification Filters", "Filter email deliveries, provider statuses, and system recipients.")
        with f_head_r:
            if st.button("Reset Filters", icon=":material/restart_alt:", key="notif_reset_btn", width="stretch"):
                st.session_state.pop("notif_status", None)
                st.session_state.pop("notif_event", None)
                st.session_state.pop("notif_from", None)
                st.session_state.pop("notif_to", None)
                st.session_state.pop("notif_hospital", None)
                st.rerun()

        today = datetime.now(REPORT_TZ).date()

        c1, c2, c3, c4 = st.columns(4)
        status = c1.selectbox("Delivery Status", [ANY] + list(notifications.STATUSES), key="notif_status")
        labels = {v: k for k, v in notifications.EVENT_LABELS.items()}
        event = c2.selectbox("Email Event", [ANY] + list(labels), key="notif_event")
        date_from = c3.date_input("From Date", value=today - timedelta(days=30), key="notif_from")
        date_to = c4.date_input("To Date", value=today, key="notif_to")

        filters = {
            "status": None if status == ANY else status,
            "event_type": None if event == ANY else labels[event],
            "created_from": datetime.combine(date_from, time.min, tzinfo=REPORT_TZ),
            "created_before": datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=REPORT_TZ),
        }

        if scope["platform"]:
            from backend.fetches import get_all_hospitals

            try:
                hospitals = {h["hospital_name"]: h["hospital_id"] for h in (get_all_hospitals() or [])}
            except Exception:
                hospitals = {}
            choice = st.selectbox("Healthcare Facility", [ANY] + sorted(hospitals), key="notif_hospital")
            filters["hospital_id"] = hospitals.get(choice)

        return filters


def _retry_panel(row):
    status_raw = str(row.get("status") or "").lower()
    if status_raw == "delivered":
        status_pill = pill("DELIVERED", "green")
    elif status_raw == "sent":
        status_pill = pill("SENT", "teal")
    elif status_raw == "failed":
        status_pill = pill("FAILED", "red")
    elif status_raw == "skipped":
        status_pill = pill("SKIPPED", "amber")
    else:
        status_pill = pill(status_raw.upper(), "grey")

    st.markdown(
        f"<div class='sa-notif-inspector'>"
        f"<div class='sa-notif-inspector-header'>"
        f"<div class='sa-notif-inspector-title'>"
        f"<span class='material-symbols-rounded' style='color:#0F7C88;'>mark_email_read</span>"
        f"<span>Email Inspector: {safe(row['event_label'])}</span>"
        f"</div>"
        f"{status_pill}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    show_rows([
        ("Email Event", row["event_label"]),
        ("Recipient Address", row["recipient"]),
        ("Delivery Status", row["status"] + (" (simulated test)" if row.get("simulated") else "")),
        ("Delivery Attempts", f"{row['attempts']} of {row['max_attempts']} attempts"),
        ("Created Timestamp", format_date(row.get("created_at"), with_time=True)),
        ("Sent Timestamp", format_date(row.get("sent_at"), with_time=True) if row.get("sent_at") else "Not sent"),
        ("Delivered Timestamp", format_date(row.get("delivered_at"), with_time=True) if row.get("delivered_at") else "Not confirmed"),
    ])

    if row.get("last_error"):
        st.markdown(
            f"<div class='sa-notif-error-box'>"
            f"<b>⚠️ Delivery Failure Error:</b><br>{safe(row['last_error'])}"
            f"</div>",
            unsafe_allow_html=True,
        )

    if row.get("skip_reason"):
        st.caption(f"ℹ️ Skip reason: {safe(row['skip_reason'])}")

    if row["status"] == "failed":
        if st.button("Retry Email Delivery Now", icon=":material/refresh:", key=f"notif_retry_{row['email_id']}", type="primary"):
            try:
                notifications.request_retry(row["email_id"])
                st.success("Queued for another delivery attempt.")
                st.rerun()
            except audit.AuditAccessDenied as exc:
                st.error(str(exc))
            except ValueError as exc:
                st.warning(str(exc))
            except Exception as exc:
                logger.error("notification retry failed: %s", type(exc).__name__)
                st.error("The retry could not be queued. Please try again.")


def show():
    load_css("notification_history.css")

    try:
        scope = audit.get_viewer_scope(notifications.RESOURCE)
    except audit.AuditAccessDenied as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        logger.error("notification scope check failed: %s", type(exc).__name__)
        st.error("Unable to verify your access right now. Please try again.")
        return

    page_header(
        "Email Notifications",
        "Delivery history and retry queue of LungSight transactional emails. Recipient emails are masked for privacy.",
    )

    filters = _filters(scope)
    signature = tuple(sorted((k, str(v)) for k, v in filters.items()))
    if st.session_state.get(SIG_KEY) != signature:
        st.session_state[SIG_KEY] = signature
        st.session_state[PAGE_KEY] = 1
    page = st.session_state.get(PAGE_KEY, 1)

    try:
        result = notifications.list_notifications(filters, page=page, page_size=PAGE_SIZE)
    except audit.AuditAccessDenied as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        logger.error("notification query failed: %s", type(exc).__name__)
        st.error("Email history could not be loaded. Please try again.")
        return

    rows = result["rows"]
    total = result["total"]

    # ---------------- Top KPI Metrics ----------------
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Total Emails Logged", total, "mail", "teal")
    with k2:
        scope_str = "Platform-wide" if scope["platform"] else "Hospital Facility"
        metric_card("Recipient Scope", scope_str, "domain", "blue")
    with k3:
        period_str = f"{filters['created_from'].strftime('%b %d')} - {filters['created_before'].strftime('%b %d')}"
        metric_card("Filter Period", period_str, "calendar_month", "green")
    with k4:
        metric_card("Records on Page", len(rows), "mark_email_read", "amber")

    st.markdown("<div style='margin-bottom: 0.5rem;'></div>", unsafe_allow_html=True)

    if not rows:
        empty_state("No transactional emails match these filters.")
        return

    table = [
        {
            "Created": format_date(r["created_at"], with_time=True),
            "Email Event": r["event_label"],
            "Recipient": r["recipient"],
            "Status": r["status"] + (" (simulated)" if r["simulated"] else ""),
            "Attempts": f"{r['attempts']}/{r['max_attempts']}",
            "Sent": format_date(r["sent_at"], with_time=True) if r["sent_at"] else "—",
            "Delivered": format_date(r["delivered_at"], with_time=True) if r["delivered_at"] else "—",
        }
        for r in rows
    ]

    st.markdown(
        f"<div class='sa-notif-toolbar'>"
        f"<span class='sa-notif-count-badge'>Showing <b>{len(rows)}</b> of <b>{total:,}</b> notifications</span>"
        f"<span style='font-size:0.8rem; color:#64748B;'>Select any record below to inspect delivery parameters</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    selection = st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        on_select="rerun" if scope["platform"] else "ignore",
        selection_mode="single-row",
        key=f"notif_table_{page}",
    )

    # Status Legend Strip
    st.markdown(
        f"<div class='sa-notif-legend'>"
        f"<span style='font-weight:700; color:#0F172A;'>Status Guide:</span>"
        f"<span class='sa-notif-legend-item'>{pill('Delivered', 'green')} Provider confirmed</span>"
        f"<span class='sa-notif-legend-item'>{pill('Sent', 'teal')} Dispatched</span>"
        f"<span class='sa-notif-legend-item'>{pill('Failed', 'red')} Error (Retryable)</span>"
        f"<span class='sa-notif-legend-item'>{pill('Skipped', 'amber')} Ineligible</span>"
        f"<span class='sa-notif-legend-item'>{pill('Suppressed', 'grey')} Bounced/Blocked</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    p1, p2, p3 = st.columns([1, 2, 1], vertical_alignment="center")
    if p1.button("Previous", disabled=page <= 1, key="notif_prev", width="stretch"):
        st.session_state[PAGE_KEY] = page - 1
        st.rerun()

    p2.markdown(
        f"<div style='text-align:center; font-size:0.88rem; font-weight:600; color:#475569;'>"
        f"Page {page} of {pages} · {total:,} total emails"
        f"</div>",
        unsafe_allow_html=True,
    )

    if p3.button("Next", disabled=page >= pages, key="notif_next", width="stretch"):
        st.session_state[PAGE_KEY] = page + 1
        st.rerun()

    if scope["platform"]:
        selected = getattr(getattr(selection, "selection", None), "rows", None) or []
        if selected:
            _retry_panel(rows[selected[0]])
        else:
            st.caption("ℹ️ Click any email row above to inspect delivery attempts or retry failed deliveries.")
