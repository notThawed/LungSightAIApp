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
from streamlit_app.components.ui import empty_state, format_date, page_header
from shared.assets import load_css


logger = logging.getLogger("lungsight.notifications")

PAGE_SIZE = 25
PAGE_KEY = "notification_page"
SIG_KEY = "notification_filter_sig"
ANY = "Any"

STATUS_HELP = {
    "sent": "Accepted by the email provider (not proof of delivery).",
    "delivered": "Delivery confirmed by a verified provider event.",
    "skipped": "Not sent: the saved state or recipient no longer qualified.",
    "suppressed": "Not sent: the address bounced or complained before.",
}


def _filters(scope):
    today = datetime.now(REPORT_TZ).date()

    c1, c2, c3, c4 = st.columns(4)
    status = c1.selectbox("Status", [ANY] + list(notifications.STATUSES), key="notif_status")
    labels = {v: k for k, v in notifications.EVENT_LABELS.items()}
    event = c2.selectbox("Email", [ANY] + list(labels), key="notif_event")
    date_from = c3.date_input("From", value=today - timedelta(days=30), key="notif_from")
    date_to = c4.date_input("To", value=today, key="notif_to")

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
        choice = st.selectbox("Hospital", [ANY] + sorted(hospitals), key="notif_hospital")
        filters["hospital_id"] = hospitals.get(choice)

    return filters


def _retry_panel(row):
    st.markdown(f"**Selected:** {row['event_label']} to {row['recipient']} — status `{row['status']}`")

    if row.get("last_error"):
        st.caption(f"Last error: {row['last_error']}")
    if row.get("skip_reason"):
        st.caption(f"Reason: {row['skip_reason']}")

    if row["status"] != "failed":
        st.caption("Only failed emails can be retried.")
        return

    if st.button("Retry this email", icon=":material/refresh:", key=f"notif_retry_{row['email_id']}"):
        try:
            notifications.request_retry(row["email_id"])
            st.success("Queued for another attempt.")
            st.rerun()
        except audit.AuditAccessDenied as exc:
            st.error(str(exc))
        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            logger.error("notification retry failed: %s", type(exc).__name__)
            st.error("The retry could not be queued. Please try again.")


def show():
    load_css("system_admin_css/base.css")

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
        "Account and subscription emails sent by LungSight. Recipients are partly hidden.",
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

    if not rows:
        empty_state("No emails match these filters.")
        return

    table = [
        {
            "Created": format_date(r["created_at"], with_time=True),
            "Email": r["event_label"],
            "Recipient": r["recipient"],
            "Status": r["status"] + (" (simulated)" if r["simulated"] else ""),
            "Attempts": f"{r['attempts']}/{r['max_attempts']}",
            "Sent": format_date(r["sent_at"], with_time=True) if r["sent_at"] else "—",
            "Delivered": format_date(r["delivered_at"], with_time=True) if r["delivered_at"] else "—",
        }
        for r in rows
    ]

    selection = st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        on_select="rerun" if scope["platform"] else "ignore",
        selection_mode="single-row",
        key=f"notif_table_{page}",
    )

    st.caption(" · ".join(f"**{k}**: {v}" for k, v in STATUS_HELP.items()))

    total = result["total"]
    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    p1, p2, p3 = st.columns([1, 2, 1], vertical_alignment="center")
    if p1.button("Previous", disabled=page <= 1, key="notif_prev", width="stretch"):
        st.session_state[PAGE_KEY] = page - 1
        st.rerun()
    p2.markdown(f"<div style='text-align:center'>Page {page} of {pages} · {total:,} emails</div>",
                unsafe_allow_html=True)
    if p3.button("Next", disabled=page >= pages, key="notif_next", width="stretch"):
        st.session_state[PAGE_KEY] = page + 1
        st.rerun()

    if scope["platform"]:
        selected = getattr(getattr(selection, "selection", None), "rows", None) or []
        if selected:
            _retry_panel(rows[selected[0]])
        else:
            st.caption("Select a row to see details or retry a failed email.")
