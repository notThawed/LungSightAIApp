# streamlit_app/pages/system_administrator/manage_applications.py

"""
System Administrator — Manage Hospital Applications

Review, verify, and manage hospital subscription onboarding applications.
Features:
- Overview KPI metrics (Total, Pending, Approved, Paid)
- Search & multi-parameter filter toolbar
- Dual View modes: Standard Clinical Table (compact) and Expanded Card Grid
- All Applications, Pending Review, Approved, and Rejected tabs
- Clinical application dossier with 4 audit tabs
- Itemized SaaS invoice modal with PayMongo verification
- Safe confirmation dialogs for approval, rejection, and deletion
- Seamless 1-click navigation to approved facility in Manage Hospitals
"""

from datetime import datetime, timedelta, timezone
from html import escape

import streamlit as st

from backend.backend_utils.application_utils import (
    get_all_hospital_applications,
    get_hospital_application,
    approve_hospital_application,
    reject_hospital_application,
    delete_hospital_application,
)
from backend.backend_utils.subscription_utils import get_active_subscription_plans
from backend.supabase_client import admin_supabase

from streamlit_app.components.ui import (
    page_header,
    table_header,
    table_row,
    safe,
    peso,
    format_date,
    show_flash_message,
)
from shared.assets import load_css


# Philippines fixed UTC+8 offset (no DST)
PH_TIME = timezone(timedelta(hours=8))

TABLE_HEADERS = [
    "Ref Code",
    "Hospital Facility",
    "Representative",
    "Subscription",
    "Payment",
    "Status",
    "Submitted",
    "Actions",
]
TABLE_WIDTHS = [1.1, 2.7, 2.2, 1.6, 1.4, 1.3, 1.3, 1.4]


# ============================================================
# INLINE SVG ICONS (Cross-platform, 100% reliable)
# ============================================================

SVG_ICONS = {
    "clipboard": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>""",
    "hourglass": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/></svg>""",
    "check_circle": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>""",
    "x_circle": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>""",
    "hospital": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/><path d="M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4"/><path d="M10 9h4"/><path d="M12 7v4"/></svg>""",
    "user": """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>""",
    "pin": """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>""",
    "calendar": """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M8 2v4"/><path d="M16 2v4"/><path d="M3 10h18"/></svg>""",
    "box": """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>""",
    "card": """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>""",
    "dollar": """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>""",
    "info": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>""",
}


# ============================================================
# STATUS LABELS AND TONES
# ============================================================

PAYMENT_LABELS = {
    "paid": "Paid",
    "pending": "Pending",
    "refunded": "Refunded",
    "unpaid": "Unpaid",
    "failed": "Failed",
    "expired": "Expired",
    "cancelled": "Cancelled",
}

PAYMENT_TONES = {
    "paid": "paid",
    "pending": "pending",
    "refunded": "refunded",
    "unpaid": "unpaid",
    "failed": "unpaid",
    "expired": "neutral",
    "cancelled": "neutral",
}

APPLICATION_TONES = {
    "Pending": "pending",
    "Approved": "approved",
    "Rejected": "rejected",
}

METHOD_LABELS = {
    "card": "Credit / Debit Card",
    "gcash": "GCash",
    "paymaya": "Maya",
    "grab_pay": "GrabPay",
    "dob": "Online Banking",
    "qrph": "QR Ph",
    "billease": "BillEase",
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def person_name(application, prefix):
    """prefix is 'applicant' or 'admin'."""
    parts = [
        application.get(f"{prefix}_first_name"),
        application.get(f"{prefix}_middle_name"),
        application.get(f"{prefix}_last_name"),
    ]
    return " ".join(part for part in parts if part) or "—"


def payment_label(status):
    return PAYMENT_LABELS.get(status, str(status or "Unknown").title())


def status_badge_html(text, tone):
    return (
        f'<span class="ma-badge ma-badge-{tone}">'
        f'<span class="ma-dot"></span>{safe(text)}'
        f'</span>'
    )


def dual_status_pills(application_status, payment_status):
    app_tone = APPLICATION_TONES.get(application_status, "neutral")
    pay_tone = PAYMENT_TONES.get(payment_status, "neutral")
    pay_text = f"Payment: {payment_label(payment_status)}"

    return (
        f'<div class="ma-pills">'
        f'{status_badge_html(application_status, app_tone)}'
        f'{status_badge_html(pay_text, pay_tone)}'
        f'</div>'
    )


def rows_html(rows):
    items = "".join(
        f'<div class="ma-row"><span>{label}</span><b>{safe(value)}</b></div>'
        for label, value in rows
    )
    return f'<div class="ma-rows">{items}</div>'


def note(text, tone=""):
    cls = f"ma-note-{tone}" if tone else ""
    st.markdown(
        f'<div class="ma-note {cls}">{SVG_ICONS["info"]} <span>{text}</span></div>',
        unsafe_allow_html=True,
    )


def remember(message):
    st.session_state["sa_flash"] = message


# ============================================================
# DATA FETCHERS & CACHES
# ============================================================

def get_latest_payment(application_id):
    """The most recent payment record for an application, or None."""
    try:
        response = (
            admin_supabase
            .table("payments")
            .select(
                "payment_id, status, amount, currency, "
                "billing_cycle, payment_method, "
                "provider_reference, paid_at, created_at"
            )
            .eq("application_id", application_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    except Exception:
        return None


def get_plan_name(application, plan_map):
    if application.get("plan_name"):
        return application["plan_name"]
    plan_id = application.get("selected_plan_id")
    if plan_id and plan_id in plan_map:
        return plan_map[plan_id]
    return f"Plan #{plan_id}" if plan_id else "No Plan Selected"


def invoice_number(payment):
    code = str(payment.get("payment_id", "")).replace("-", "")[:8].upper()
    return f"INV-{code}" if code else "INV-000000"


# ============================================================
# KPI METRIC CARDS
# ============================================================

def render_overview_kpis(applications):
    pending = [a for a in applications if a.get("application_status") == "Pending"]
    approved = [a for a in applications if a.get("application_status") == "Approved"]
    paid = [a for a in applications if a.get("payment_status") == "paid"]

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f'<div class="ma-metric ma-metric-teal">'
            f'<div class="ma-metric-icon">{SVG_ICONS["clipboard"]}</div>'
            f'<div class="ma-metric-body">'
            f'<div class="ma-metric-title">Total Applications</div>'
            f'<div class="ma-metric-value">{len(applications)}</div>'
            f'<div class="ma-metric-sub">Submitted onboarding forms</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f'<div class="ma-metric ma-metric-amber">'
            f'<div class="ma-metric-icon">{SVG_ICONS["hourglass"]}</div>'
            f'<div class="ma-metric-body">'
            f'<div class="ma-metric-title">Pending Review</div>'
            f'<div class="ma-metric-value">{len(pending)}</div>'
            f'<div class="ma-metric-sub">Awaiting admin review</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f'<div class="ma-metric ma-metric-green">'
            f'<div class="ma-metric-icon">{SVG_ICONS["check_circle"]}</div>'
            f'<div class="ma-metric-body">'
            f'<div class="ma-metric-title">Approved Facilities</div>'
            f'<div class="ma-metric-value">{len(approved)}</div>'
            f'<div class="ma-metric-sub">Activated hospital accounts</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f'<div class="ma-metric ma-metric-blue">'
            f'<div class="ma-metric-icon">{SVG_ICONS["dollar"]}</div>'
            f'<div class="ma-metric-body">'
            f'<div class="ma-metric-title">Paid Subscriptions</div>'
            f'<div class="ma-metric-value">{len(paid)} <small style="font-size:0.9rem; font-weight:600; color:var(--sa-slate);">/ {len(applications)}</small></div>'
            f'<div class="ma-metric-sub">Verified payment transfers</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# FILTER TOOLBAR
# ============================================================

def render_filters(plan_names):
    with st.container(key="ma_filters"):
        col_search, col_plan, col_payment, col_view, col_reset = st.columns([3.0, 1.8, 1.8, 1.5, 0.9])

        with col_search:
            search_query = st.text_input(
                "Search",
                placeholder="Search by hospital, representative, email, city...",
                key="ma_search_input",
                label_visibility="collapsed",
            )

        with col_plan:
            plan_filter = st.selectbox(
                "Plan Filter",
                options=["All Plans"] + sorted(list(plan_names)),
                key="ma_plan_select",
                label_visibility="collapsed",
            )

        with col_payment:
            payment_filter = st.selectbox(
                "Payment Filter",
                options=["All Payments", "Paid", "Pending", "Unpaid", "Refunded", "Failed"],
                key="ma_payment_select",
                label_visibility="collapsed",
            )

        with col_view:
            view_mode = st.selectbox(
                "View Mode",
                options=["Table View", "Card View"],
                key="ma_view_mode",
                label_visibility="collapsed",
            )

        with col_reset:
            if st.button("Reset", key="ma_reset_btn", icon=":material/refresh:", width="stretch"):
                st.session_state["ma_search_input"] = ""
                st.session_state["ma_plan_select"] = "All Plans"
                st.session_state["ma_payment_select"] = "All Payments"
                st.session_state["ma_page"] = 1
                st.rerun()

    return search_query.strip().lower(), plan_filter, payment_filter, view_mode


def filter_applications(applications, plan_map, query, plan_filter, payment_filter):
    filtered = []
    for app in applications:
        if query:
            h_name = (app.get("hospital_name") or "").lower()
            h_address = (app.get("hospital_address") or "").lower()
            h_email = (app.get("hospital_email") or "").lower()
            rep_name = person_name(app, "applicant").lower()
            rep_email = (app.get("applicant_email") or "").lower()
            app_id = (app.get("application_id") or "").lower()

            matches = any(query in target for target in [h_name, h_address, h_email, rep_name, rep_email, app_id])
            if not matches:
                continue

        if plan_filter != "All Plans":
            app_plan = get_plan_name(app, plan_map)
            if app_plan.lower() != plan_filter.lower():
                continue

        if payment_filter != "All Payments":
            app_payment = (app.get("payment_status") or "unpaid").lower()
            if app_payment != payment_filter.lower():
                continue

        filtered.append(app)

    return filtered


# ============================================================
# STANDARDIZED CLINICAL TABLE VIEW
# ============================================================

def render_applications_table(applications, plan_map, tab_key):
    if not applications:
        return

    PAGE_SIZE = 10
    total_items = len(applications)
    total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
    page_key = f"ma_page_{tab_key}"
    current_page = st.session_state.get(page_key, 1)

    if current_page > total_pages:
        current_page = total_pages
        st.session_state[page_key] = current_page
    elif current_page < 1:
        current_page = 1
        st.session_state[page_key] = current_page

    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_items)
    page_apps = applications[start_idx:end_idx]

    # Toolbar
    st.markdown(
        f'<div class="sa-table-toolbar">'
        f'<div class="sa-table-count-badge">'
        f'Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_items}</b> applications'
        f'</div>'
        f'<span style="font-size:0.78rem; color:var(--sa-slate);">Page {current_page} of {total_pages}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.container(key=f"sa_table_applications_{tab_key}"):
        table_header(TABLE_HEADERS, TABLE_WIDTHS, f"applications_{tab_key}")

        for app in page_apps:
            app_id = app.get("application_id")
            app_code = (app_id or "").replace("-", "")[:8].upper()
            h_name = app.get("hospital_name") or "Unnamed Hospital"
            h_type = app.get("hospital_type") or "General Hospital"
            address = app.get("hospital_address") or "—"
            applicant = person_name(app, "applicant")
            position = app.get("applicant_position") or "Representative"
            email = app.get("applicant_email") or app.get("hospital_email") or "—"
            plan = get_plan_name(app, plan_map)
            billing = (app.get("billing_cycle") or "Monthly").title()
            app_status = app.get("application_status") or "Pending"
            pay_status = app.get("payment_status") or "unpaid"
            created_at = format_date(app.get("created_at"))
            hospital_id = app.get("hospital_id")

            with table_row(f"app_{app_id}_{tab_key}", TABLE_WIDTHS) as cols:
                # 0. Ref Code
                cols[0].markdown(f'<span class="ma-app-code">#{app_code}</span>', unsafe_allow_html=True)

                # 1. Hospital Facility
                cols[1].markdown(
                    f'<div class="ma-table-hospital">'
                    f'<span class="ma-table-hosp-name">{safe(h_name)}</span>'
                    f'<span class="ma-table-hosp-sub">{safe(h_type)} &bull; {safe(address[:32])}{"…" if len(address) > 32 else ""}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # 2. Representative
                cols[2].markdown(
                    f'<div class="ma-table-rep">'
                    f'<span class="ma-table-rep-name">{safe(applicant)}</span>'
                    f'<span class="ma-table-rep-sub">{safe(position)} &bull; {safe(email)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # 3. Subscription
                cols[3].markdown(
                    f'<div class="ma-table-sub">'
                    f'<span class="ma-table-plan">{safe(plan)}</span>'
                    f'<span class="ma-table-cycle">{safe(billing)} billing</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # 4. Payment
                cols[4].markdown(
                    status_badge_html(payment_label(pay_status), PAYMENT_TONES.get(pay_status, "neutral")),
                    unsafe_allow_html=True,
                )

                # 5. Application Status
                cols[5].markdown(
                    status_badge_html(app_status, APPLICATION_TONES.get(app_status, "neutral")),
                    unsafe_allow_html=True,
                )

                # 6. Submitted
                cols[6].markdown(f'<span class="sa-cell sa-cell-muted">{created_at}</span>', unsafe_allow_html=True)

                # 7. Actions
                with cols[7]:
                    act_cols = st.columns(3, gap="small", vertical_alignment="center")

                    with act_cols[0]:
                        if st.button("", key=f"tbl_view_{app_id}_{tab_key}", icon=":material/visibility:", help="View application dossier", width="stretch"):
                            show_application_details(app_id, plan_map)

                    with act_cols[1]:
                        if st.button("", key=f"tbl_inv_{app_id}_{tab_key}", icon=":material/receipt_long:", help="View subscription invoice", width="stretch"):
                            show_invoice_dialog(app_id, plan_map)

                    with act_cols[2]:
                        if app_status == "Pending":
                            can_approve = (pay_status == "paid")
                            if can_approve:
                                if st.button("", key=f"tbl_appr_{app_id}_{tab_key}", icon=":material/check_circle:", help="Approve application", width="stretch", type="primary"):
                                    show_approve_dialog(app_id)
                            else:
                                if st.button("", key=f"tbl_rej_{app_id}_{tab_key}", icon=":material/close:", help="Reject application", width="stretch"):
                                    show_reject_dialog(app_id)
                        elif app_status == "Approved":
                            if hospital_id:
                                if st.button("", key=f"tbl_hosp_{app_id}_{tab_key}", icon=":material/domain:", help="View facility in Manage Hospitals", width="stretch"):
                                    st.session_state["selected_hospital"] = hospital_id
                                    st.session_state.current_page = "Manage Hospitals"
                                    st.rerun()
                            else:
                                st.button("", key=f"tbl_ok_{app_id}_{tab_key}", icon=":material/check:", help="Application approved and active", disabled=True, width="stretch")
                        elif app_status == "Rejected":
                            if st.button("", key=f"tbl_del_{app_id}_{tab_key}", icon=":material/delete_forever:", help="Delete rejected record permanently", width="stretch"):
                                show_delete_dialog(app_id)

    # Pagination controls
    if total_pages > 1:
        st.markdown('<div class="sa-pagination-bar">', unsafe_allow_html=True)
        col_prev, col_info, col_next = st.columns([1, 2.5, 1], vertical_alignment="center")

        with col_prev:
            if st.button("Previous", key=f"prev_{tab_key}", disabled=(current_page <= 1), width="stretch"):
                st.session_state[page_key] = current_page - 1
                st.rerun()

        with col_info:
            st.markdown(
                f'<div class="sa-pagination-info">Page <b>{current_page}</b> of <b>{total_pages}</b> ({total_items} items)</div>',
                unsafe_allow_html=True,
            )

        with col_next:
            if st.button("Next", key=f"next_{tab_key}", disabled=(current_page >= total_pages), width="stretch"):
                st.session_state[page_key] = current_page + 1
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# EXPANDED CARD VIEW
# ============================================================

def render_application_card(application, mode, plan_map, tab_key):
    application_id = application.get("application_id")
    application_status = application.get("application_status", "Pending")
    payment_status = application.get("payment_status", "unpaid")

    hospital_name = application.get("hospital_name") or "Unnamed Hospital"
    hospital_type = application.get("hospital_type") or "General Hospital"
    address = application.get("hospital_address") or "No address provided"
    created_at = format_date(application.get("created_at"))

    applicant = person_name(application, "applicant")
    position = application.get("applicant_position") or "Representative"

    plan = get_plan_name(application, plan_map)
    billing = (application.get("billing_cycle") or "Monthly").title()
    app_code = (application_id or "").replace("-", "")[:8].upper()
    card_status_cls = f"ma-card-{application_status.lower()}"

    with st.container(key=f"app_card_{card_status_cls}_{application_id}_{tab_key}"):
        header_html = (
            f'<div class="ma-card-header {card_status_cls}">'
            f'<div class="ma-card-hospital">'
            f'<div class="ma-card-avatar">{SVG_ICONS["hospital"]}</div>'
            f'<div class="ma-card-meta">'
            f'<div class="ma-card-title">{safe(hospital_name)}</div>'
            f'<div class="ma-card-subline">'
            f'<span class="ma-badge ma-badge-neutral">#{app_code}</span>'
            f'<span>&bull;</span>'
            f'<span>{safe(hospital_type)}</span>'
            f'<span>&bull;</span>'
            f'{SVG_ICONS["calendar"]} <span>Submitted {created_at}</span>'
            f'</div>'
            f'</div>'
            f'</div>'
            f'{dual_status_pills(application_status, payment_status)}'
            f'</div>'
        )
        st.markdown(header_html, unsafe_allow_html=True)

        chips_html = (
            f'<div class="ma-card-chips">'
            f'<div class="ma-chip">'
            f'<span class="ma-chip-label">{SVG_ICONS["pin"]} Location</span>'
            f'<span class="ma-chip-value" title="{safe(address)}">{safe(address[:38])}{"…" if len(address) > 38 else ""}</span>'
            f'</div>'
            f'<div class="ma-chip">'
            f'<span class="ma-chip-label">{SVG_ICONS["box"]} Subscription</span>'
            f'<span class="ma-chip-value">{safe(plan)} ({safe(billing)})</span>'
            f'</div>'
            f'<div class="ma-chip">'
            f'<span class="ma-chip-label">{SVG_ICONS["user"]} Authorized Contact</span>'
            f'<span class="ma-chip-value" title="{safe(applicant)} ({safe(position)})">{safe(applicant)}</span>'
            f'</div>'
            f'<div class="ma-chip">'
            f'<span class="ma-chip-label">{SVG_ICONS["card"]} Payment Status</span>'
            f'<span class="ma-chip-value">{payment_label(payment_status)}</span>'
            f'</div>'
            f'</div>'
        )
        st.markdown(chips_html, unsafe_allow_html=True)

        # Card action buttons
        show_card_buttons(application, application_id, payment_status, mode, plan_map, tab_key)


def show_card_buttons(application, application_id, payment_status, mode, plan_map, tab_key):
    hospital_id = application.get("hospital_id")
    app_status = application.get("application_status", "Pending")

    if app_status == "Pending":
        c_detail, c_invoice, c_approve, c_reject = st.columns([1.2, 1.2, 1.3, 1.1], gap="small")

        with c_detail:
            if st.button("Details", key=f"c_view_{application_id}_{tab_key}", icon=":material/visibility:", width="stretch", type="secondary"):
                show_application_details(application_id, plan_map)

        with c_invoice:
            if st.button("Invoice", key=f"c_inv_{application_id}_{tab_key}", icon=":material/receipt_long:", width="stretch", type="secondary"):
                show_invoice_dialog(application_id, plan_map)

        can_approve = (payment_status == "paid")

        with c_approve:
            if st.button(
                "Approve",
                key=f"c_approve_{application_id}_{tab_key}",
                icon=":material/check_circle:",
                type="primary",
                width="stretch",
                disabled=not can_approve,
                help=None if can_approve else "Payment must be completed before an application can be approved.",
            ):
                show_approve_dialog(application_id)

        with c_reject:
            if st.button("Reject", key=f"c_reject_{application_id}_{tab_key}", icon=":material/close:", width="stretch", type="secondary"):
                show_reject_dialog(application_id)

    elif app_status == "Approved":
        c_detail, c_invoice, c_hosp, c_empty = st.columns([1.2, 1.2, 1.5, 2.5], gap="small")

        with c_detail:
            if st.button("Details", key=f"c_view_{application_id}_{tab_key}", icon=":material/visibility:", width="stretch", type="secondary"):
                show_application_details(application_id, plan_map)

        with c_invoice:
            if st.button("Invoice", key=f"c_inv_{application_id}_{tab_key}", icon=":material/receipt_long:", width="stretch", type="secondary"):
                show_invoice_dialog(application_id, plan_map)

        with c_hosp:
            if hospital_id:
                if st.button("Go to Facility", key=f"c_hosp_{application_id}_{tab_key}", icon=":material/domain:", width="stretch", type="secondary"):
                    st.session_state["selected_hospital"] = hospital_id
                    st.session_state.current_page = "Manage Hospitals"
                    st.rerun()

    elif app_status == "Rejected":
        c_detail, c_invoice, c_delete, c_empty = st.columns([1.2, 1.2, 1.5, 2.5], gap="small")

        with c_detail:
            if st.button("Details", key=f"c_view_{application_id}_{tab_key}", icon=":material/visibility:", width="stretch", type="secondary"):
                show_application_details(application_id, plan_map)

        with c_invoice:
            if st.button("Invoice", key=f"c_inv_{application_id}_{tab_key}", icon=":material/receipt_long:", width="stretch", type="secondary"):
                show_invoice_dialog(application_id, plan_map)

        with c_delete:
            if st.button("Delete Record", key=f"c_delete_{application_id}_{tab_key}", icon=":material/delete_forever:", width="stretch", type="secondary"):
                show_delete_dialog(application_id)


# ============================================================
# DETAILS DOSSIER DIALOG
# ============================================================

@st.dialog("Application Dossier", width="medium")
def show_application_details(application_id, plan_map):
    application = get_hospital_application(application_id)

    if not application:
        st.error("Unable to load application details.")
        return

    payment = get_latest_payment(application_id)

    hospital_name = application.get("hospital_name") or "Unnamed Hospital"
    application_status = application.get("application_status", "Pending")
    payment_status = application.get("payment_status", "unpaid")
    submitted_date = format_date(application.get("created_at"), with_time=True)

    header_html = (
        f'<div class="ma-dialog-head">'
        f'<div class="ma-dialog-brand">'
        f'<div class="ma-dialog-avatar">{SVG_ICONS["hospital"]}</div>'
        f'<div>'
        f'<div class="ma-dialog-title">{safe(hospital_name)}</div>'
        f'<div class="ma-dialog-sub">Application ID: {safe(application_id)} &bull; Submitted {submitted_date}</div>'
        f'</div>'
        f'</div>'
        f'{dual_status_pills(application_status, payment_status)}'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    t_hospital, t_people, t_plan, t_audit = st.tabs(
        ["Hospital Profile", "Authorized Personnel", "Subscription & Payment", "Legal & Audit"]
    )

    # 1. Hospital Profile
    with t_hospital:
        st.markdown(
            f'<div class="ma-dialog-subheading">{SVG_ICONS["hospital"]} Clinical Facility Information</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            rows_html([
                ("Hospital Name", application.get("hospital_name")),
                ("Facility Type", application.get("hospital_type")),
                ("Physical Address", application.get("hospital_address")),
                ("Official Email", application.get("hospital_email")),
                ("Contact Number", application.get("hospital_contact_number")),
                ("Official Website", application.get("hospital_website")),
            ]),
            unsafe_allow_html=True,
        )

    # 2. People
    with t_people:
        st.markdown(
            f'<div class="ma-dialog-subheading">{SVG_ICONS["user"]} Authorized Applicant Representative</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            rows_html([
                ("Representative Name", person_name(application, "applicant")),
                ("Official Position", application.get("applicant_position")),
                ("Email Address", application.get("applicant_email")),
                ("Mobile / Landline", application.get("applicant_contact_number")),
            ]),
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="ma-dialog-subheading">{SVG_ICONS["user"]} Designee Hospital Administrator</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            rows_html([
                ("Administrator Name", person_name(application, "admin")),
                ("Admin Email", application.get("admin_email")),
                ("Contact Number", application.get("admin_contact_number")),
            ]),
            unsafe_allow_html=True,
        )

    # 3. Plan & Payment
    with t_plan:
        plan_name = get_plan_name(application, plan_map)
        billing = (application.get("billing_cycle") or "Monthly").title()

        st.markdown(
            f'<div class="ma-dialog-subheading">{SVG_ICONS["box"]} Subscription Package</div>',
            unsafe_allow_html=True,
        )

        rows = [
            ("Selected Plan", plan_name),
            ("Billing Cadence", billing),
        ]

        if payment:
            amount = peso(payment.get("amount"))
            method = payment.get("payment_method")
            method_name = METHOD_LABELS.get(method, str(method or "").replace("_", " ").title())
            paid_date = format_date(payment.get("paid_at"), with_time=True)

            rows.extend([
                ("Payment Status", payment_label(payment.get("status"))),
                ("Amount Paid", amount),
                ("Payment Method", method_name),
                ("Paid Timestamp", paid_date),
                ("PayMongo Reference", payment.get("provider_reference")),
            ])
        else:
            rows.append(("Payment Status", payment_label(payment_status)))

        st.markdown(rows_html(rows), unsafe_allow_html=True)

        if not payment:
            note("No transaction record has been completed via PayMongo for this application yet.", "amber")

    # 4. Legal & Audit
    with t_audit:
        accepted = application.get("agreement_accepted", False)
        accepted_text = "Agreed & Signed &bull; " + format_date(application.get("agreement_accepted_at"), with_time=True) if accepted else "Pending Acceptance"

        st.markdown(
            f'<div class="ma-dialog-subheading">{SVG_ICONS["clipboard"]} Compliance & System Audit</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            rows_html([
                ("Terms & Service Agreement", accepted_text),
                ("Application UUID", application.get("application_id")),
                ("Submission Timestamp", format_date(application.get("created_at"), with_time=True)),
                ("Last Record Update", format_date(application.get("updated_at"), with_time=True)),
            ]),
            unsafe_allow_html=True,
        )


# ============================================================
# INVOICE DIALOG
# ============================================================

@st.dialog("Subscription Invoice", width="medium")
def show_invoice_dialog(application_id, plan_map):
    application = get_hospital_application(application_id)

    if not application:
        st.error("Unable to load invoice record.")
        return

    payment = get_latest_payment(application_id)

    if not payment:
        note(
            "No completed payment transaction has been logged for this application yet. "
            "An invoice will be generated automatically once checkout is fulfilled.",
            "amber",
        )
        return

    status = (payment.get("status") or application.get("payment_status") or "unpaid").lower()
    is_paid = (status == "paid")

    plan_name = get_plan_name(application, plan_map)
    billing = (payment.get("billing_cycle") or application.get("billing_cycle") or "Monthly").title()
    amount_str = peso(payment.get("amount"))

    inv_num = invoice_number(payment)
    method = payment.get("payment_method")
    method_name = METHOD_LABELS.get(method, str(method or "").replace("_", " ").title())
    paid_date = format_date(payment.get("paid_at"), with_time=True) if is_paid else "Awaiting Payment"
    inv_date = format_date(payment.get("created_at"))

    h_name = application.get("hospital_name") or "Hospital Facility"
    h_addr = application.get("hospital_address") or "—"
    h_email = application.get("hospital_email") or "—"
    h_phone = application.get("hospital_contact_number") or "—"

    stamp_cls = "ma-inv-stamp-paid" if is_paid else "ma-inv-stamp-unpaid"
    stamp_text = "PAID" if is_paid else "PAYMENT DUE"

    invoice_html = (
        f'<div class="ma-inv">'
        f'<div class="ma-inv-top">'
        f'<div class="ma-inv-brand">'
        f'<div class="ma-inv-logo">LUNGSIGHT DIAGNOSTICS &bull; OFFICIAL INVOICE</div>'
        f'<div class="ma-inv-number">{inv_num}</div>'
        f'</div>'
        f'<div class="ma-inv-stamp {stamp_cls}">{stamp_text}</div>'
        f'</div>'
        f'<div class="ma-inv-grid">'
        f'<div class="ma-inv-block">'
        f'<span class="ma-inv-block-head">Billed To Facility</span>'
        f'<b>{safe(h_name)}</b>'
        f'<small>{safe(h_addr)}<br>{safe(h_email)} &bull; {safe(h_phone)}</small>'
        f'</div>'
        f'<div class="ma-inv-block">'
        f'<span class="ma-inv-block-head">Payment Details</span>'
        f'<span>Invoice Date: <b>{inv_date}</b></span>'
        f'<span>Paid Timestamp: <b>{paid_date}</b></span>'
        f'<span>Payment Method: <b>{safe(method_name)}</b></span>'
        f'<span>Provider Ref: <b>{safe(payment.get("provider_reference"))}</b></span>'
        f'</div>'
        f'</div>'
        f'<div class="ma-inv-lines">'
        f'<div class="ma-inv-line ma-inv-line-head">'
        f'<span>Item Description</span><span>Term / Period</span><span>Total Amount</span>'
        f'</div>'
        f'<div class="ma-inv-line">'
        f'<span><b>LungSight {safe(plan_name)} Tier</b><br><small style="color:var(--sa-slate);">Clinical AI analysis & facility management license</small></span>'
        f'<span>{safe(billing)} Cycle</span>'
        f'<b>{amount_str}</b>'
        f'</div>'
        f'</div>'
        f'<div class="ma-inv-total">'
        f'<span>{"Total Amount Paid" if is_paid else "Total Balance Due"}</span>'
        f'<b>{amount_str}</b>'
        f'</div>'
        f'</div>'
    )
    st.markdown(invoice_html, unsafe_allow_html=True)


# ============================================================
# APPROVAL / REJECTION / DELETION DIALOGS
# ============================================================

@st.dialog("Approve Application", width="small")
def show_approve_dialog(application_id):
    application = get_hospital_application(application_id)

    if not application:
        st.error("Application record not found.")
        return

    hospital_name = safe(application.get("hospital_name") or "this facility")
    payment_status = (application.get("payment_status") or "unpaid").lower()

    st.markdown(
        f'<p style="font-size:0.95rem; color:var(--sa-ink); margin-bottom:0.75rem;">'
        f'Are you sure you want to approve the application for <b>{hospital_name}</b>?'
        f'</p>',
        unsafe_allow_html=True,
    )

    if payment_status != "paid":
        note("Cannot approve: Subscription payment has not been received or confirmed.", "red")
        return

    note("Payment is verified. Approving will automatically provision a new hospital account and assign the selected subscription.", "green")

    c_cancel, c_confirm = st.columns(2, gap="small")

    with c_cancel:
        if st.button("Cancel", key=f"cancel_approve_{application_id}", width="stretch"):
            st.rerun()

    with c_confirm:
        if st.button("Confirm Approval", type="primary", key=f"confirm_approve_{application_id}", icon=":material/check_circle:", width="stretch"):
            result = approve_hospital_application(application_id)
            if result.get("success"):
                remember(f"Hospital application for {hospital_name} approved successfully.")
                st.rerun()
            else:
                st.error(f"Approval failed: {result.get('message', 'Unknown error')}")


@st.dialog("Reject Application", width="small")
def show_reject_dialog(application_id):
    application = get_hospital_application(application_id)

    if not application:
        st.error("Application record not found.")
        return

    hospital_name = safe(application.get("hospital_name") or "this facility")
    payment_status = (application.get("payment_status") or "unpaid").lower()

    st.markdown(
        f'<p style="font-size:0.95rem; color:var(--sa-ink); margin-bottom:0.75rem;">'
        f'Reject the onboarding application for <b>{hospital_name}</b>?'
        f'</p>',
        unsafe_allow_html=True,
    )

    if payment_status == "paid":
        note("Caution: Payment was already collected for this application. Rejecting it requires initiating a refund manually through PayMongo.", "amber")
    else:
        note("The application will be moved to the Rejected queue.", "amber")

    c_cancel, c_confirm = st.columns(2, gap="small")

    with c_cancel:
        if st.button("Cancel", key=f"cancel_reject_{application_id}", width="stretch"):
            st.rerun()

    with c_confirm:
        if st.button("Confirm Rejection", type="primary", key=f"confirm_reject_{application_id}", icon=":material/close:", width="stretch"):
            result = reject_hospital_application(application_id)
            if result.get("success"):
                remember(f"Application for {hospital_name} was marked as rejected.")
                st.rerun()
            else:
                st.error(f"Rejection failed: {result.get('message', 'Unknown error')}")


@st.dialog("Delete Application", width="small")
def show_delete_dialog(application_id):
    application = get_hospital_application(application_id)

    if not application:
        st.error("Application record not found.")
        return

    if application.get("application_status") != "Rejected":
        st.error("Only rejected applications can be permanently deleted.")
        return

    hospital_name = safe(application.get("hospital_name") or "this facility")

    st.markdown(
        f'<p style="font-size:0.95rem; color:var(--sa-ink); margin-bottom:0.75rem;">'
        f'Permanently delete the application record for <b>{hospital_name}</b>?'
        f'</p>',
        unsafe_allow_html=True,
    )

    note("Warning: This action is permanent and cannot be undone. All submitted hospital metadata and contact details will be deleted from the database.", "red")

    c_cancel, c_confirm = st.columns(2, gap="small")

    with c_cancel:
        if st.button("Cancel", key=f"cancel_delete_{application_id}", width="stretch"):
            st.rerun()

    with c_confirm:
        if st.button("Delete Permanently", type="primary", key=f"confirm_delete_{application_id}", icon=":material/delete_forever:", width="stretch"):
            result = delete_hospital_application(application_id)
            if result.get("success"):
                remember(f"Application for {hospital_name} was permanently purged.")
                st.rerun()
            else:
                st.error(f"Deletion failed: {result.get('message', 'Unknown error')}")


# ============================================================
# MAIN ENTRYPOINT
# ============================================================

def show():
    load_css("manage_application.css")
    show_flash_message()

    with st.container(key="sa_page"):
        page_header(
            "Manage Hospital Applications",
            "Review, verify subscriptions, and approve onboarding applications for healthcare facilities.",
        )

        # 1. Fetch data
        all_apps = get_all_hospital_applications()
        # Drafts are not yet submitted to admin review
        active_applications = [a for a in all_apps if a.get("application_status") != "Draft"]

        # Cache plans mapping to prevent N+1 queries
        active_plans = get_active_subscription_plans()
        plan_map = {p.get("plan_id"): p.get("plan_name") for p in active_plans}
        plan_names = set(plan_map.values())

        # 2. Overview KPI cards
        render_overview_kpis(active_applications)

        # 3. Search and filters
        query, plan_filter, payment_filter, view_mode = render_filters(plan_names)

        # Apply filtering
        filtered_all = filter_applications(active_applications, plan_map, query, plan_filter, payment_filter)
        filtered_pending = [a for a in filtered_all if a.get("application_status") == "Pending"]
        filtered_approved = [a for a in filtered_all if a.get("application_status") == "Approved"]
        filtered_rejected = [a for a in filtered_all if a.get("application_status") == "Rejected"]

        # 4. Tab navigation (All Applications first so admin never sees an empty screen)
        tab_all, tab_pending, tab_approved, tab_rejected = st.tabs([
            f"All Applications ({len(filtered_all)})",
            f"Pending Review ({len(filtered_pending)})",
            f"Approved Facilities ({len(filtered_approved)})",
            f"Rejected ({len(filtered_rejected)})",
        ])

        # TAB 1: ALL APPLICATIONS
        with tab_all:
            if not filtered_all:
                st.markdown(
                    f'<div class="ma-empty">{SVG_ICONS["clipboard"]}<br><b>No applications found.</b><br>'
                    f'<span style="font-size:0.8rem;">No hospital applications match your current search or filter criteria.</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                if view_mode == "Table View":
                    render_applications_table(filtered_all, plan_map, "all")
                else:
                    for app in filtered_all:
                        render_application_card(app, app.get("application_status", "Pending").lower(), plan_map, "all")

        # TAB 2: PENDING REVIEW
        with tab_pending:
            if not filtered_pending:
                st.markdown(
                    f'<div class="ma-empty">{SVG_ICONS["check_circle"]}<br><b>All Caught Up! No Pending Applications</b><br>'
                    f'<span style="font-size:0.8rem;">Every submitted hospital onboarding application has been reviewed and processed.</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                if view_mode == "Table View":
                    render_applications_table(filtered_pending, plan_map, "pending")
                else:
                    for app in filtered_pending:
                        render_application_card(app, "pending", plan_map, "pending")

        # TAB 3: APPROVED FACILITIES
        with tab_approved:
            if not filtered_approved:
                st.markdown(
                    f'<div class="ma-empty">{SVG_ICONS["hospital"]}<br><b>No approved applications found.</b><br>'
                    f'<span style="font-size:0.8rem;">Approved healthcare facilities will be listed here.</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                if view_mode == "Table View":
                    render_applications_table(filtered_approved, plan_map, "approved")
                else:
                    for app in filtered_approved:
                        render_application_card(app, "approved", plan_map, "approved")

        # TAB 4: REJECTED
        with tab_rejected:
            if not filtered_rejected:
                st.markdown(
                    f'<div class="ma-empty">{SVG_ICONS["x_circle"]}<br><b>No rejected applications found.</b><br>'
                    f'<span style="font-size:0.8rem;">Declined applications will appear here where they can be permanently purged if needed.</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                if view_mode == "Table View":
                    render_applications_table(filtered_rejected, plan_map, "rejected")
                else:
                    for app in filtered_rejected:
                        render_application_card(app, "rejected", plan_map, "rejected")
