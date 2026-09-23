from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import streamlit as st

from backend.backend_utils.application_utils import (
    get_all_hospital_applications,
    get_hospital_application,
    approve_hospital_application,
    reject_hospital_application,
    delete_hospital_application,
)
from backend.backend_utils.subscription_utils import get_active_subscription_plans


PROJECT_ROOT = Path(__file__).resolve().parents[3]
APPLICATION_CSS_PATH = (
    PROJECT_ROOT / "shared" / "theme" / "css_content" / "application.css"
)

# The Philippines has no daylight saving, so a fixed UTC+8 offset is enough
PH_TIME = timezone(timedelta(hours=8))


# ============================================================
# LABELS AND COLORS
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

# Pill color for each status (the colors are defined in application.css)
PAYMENT_TONES = {
    "paid": "green",
    "pending": "amber",
    "refunded": "blue",
    "unpaid": "red",
    "failed": "red",
    "expired": "grey",
    "cancelled": "grey",
}

APPLICATION_TONES = {
    "Pending": "amber",
    "Approved": "green",
    "Rejected": "red",
}

METHOD_LABELS = {
    "card": "Credit / debit card",
    "gcash": "GCash",
    "paymaya": "Maya",
    "grab_pay": "GrabPay",
    "dob": "Online banking",
    "qrph": "QR Ph",
    "billease": "BillEase",
}


# ============================================================
# SMALL HELPERS
# ============================================================

def load_css():
    if APPLICATION_CSS_PATH.exists():
        css = APPLICATION_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def safe(value):
    """Escape text before putting it inside HTML. Empty values show a dash."""
    text = escape(str(value or "").strip())
    return text or "—"


def peso(amount):
    """1500 -> ₱1,500.00"""
    return f"₱{float(amount or 0):,.2f}"


def format_date(value, with_time=False):
    """'2026-09-20T05:12:33+00:00' -> 'Sep 20, 2026' (or with the time)."""
    if not value:
        return "—"

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


def person_name(application, prefix):
    """prefix is 'applicant' or 'admin'."""
    parts = [
        application.get(f"{prefix}_first_name"),
        application.get(f"{prefix}_middle_name"),
        application.get(f"{prefix}_last_name"),
    ]
    return " ".join(part for part in parts if part)


def payment_label(status):
    return PAYMENT_LABELS.get(status, str(status or "Unknown").title())


def pill(text, tone):
    return f"<span class='ma-pill ma-pill-{tone}'>{safe(text)}</span>"


def status_pills(application_status, payment_status):
    """The two small colored labels shown on cards and in the details header."""
    return (
        "<div class='ma-pills'>"
        + pill(application_status, APPLICATION_TONES.get(application_status, "grey"))
        + pill(f"Payment {payment_label(payment_status).lower()}",
               PAYMENT_TONES.get(payment_status, "grey"))
        + "</div>"
    )


def rows_html(rows):
    """Label / value rows, e.g. [("Plan", "Standard"), ("Billing", "Monthly")]."""
    items = "".join(
        f"<div class='ma-row'><span>{label}</span><b>{safe(value)}</b></div>"
        for label, value in rows
    )
    return f"<div class='ma-rows'>{items}</div>"


def note(text, tone=""):
    """A small colored message box. tone: '', 'green', 'red' or 'amber'."""
    st.markdown(
        f"<div class='ma-note ma-note-{tone}'>{text}</div>",
        unsafe_allow_html=True,
    )


def close_button(key):
    if st.button("Close", key=key, width="stretch"):
        st.rerun()


def remember(message):
    """Show this message (as a small toast) after the page reloads."""
    st.session_state["applications_flash"] = message


def show_flash_message():
    message = st.session_state.pop("applications_flash", None)

    if message:
        st.toast(message)


# ============================================================
# DATA HELPERS
# ============================================================

def get_latest_payment(application_id):
    """The most recent payment record for an application, or None."""
    from backend.supabase_client import admin_supabase

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


def get_plan_name(application):
    if application.get("plan_name"):
        return application["plan_name"]

    plan_id = application.get("selected_plan_id")

    for plan in get_active_subscription_plans():
        if plan.get("plan_id") == plan_id:
            return plan.get("plan_name")

    return f"Plan #{plan_id}"


def invoice_number(payment):
    """There is no invoice table, so the number is made from the payment id."""
    code = str(payment.get("payment_id", "")).replace("-", "")[:8].upper()
    return f"INV-{code}"


# ============================================================
# METRIC CARD
# icon is a Material icon name, e.g. "hourglass_top"
# ============================================================

def metric_card(title, value, icon, tone=""):
    st.markdown(
        f"<div class='ma-metric ma-metric-{tone}'>"
        f"<span class='ma-metric-icon'>{icon}</span>"
        "<div>"
        f"<div class='ma-metric-title'>{title}</div>"
        f"<div class='ma-metric-value'>{value}</div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# DETAILS DIALOG
# ============================================================

@st.dialog("Application details", width="medium")
def show_application_details(application_id):

    application = get_hospital_application(application_id)

    if not application:
        st.error("Unable to load application details.")
        return

    payment = get_latest_payment(application_id)

    application_status = application.get("application_status", "Unknown")
    payment_status = application.get("payment_status", "unpaid")

    with st.container(key="ma_dialog"):

        st.markdown(
            "<div class='ma-dialog-head'>"
            "<div>"
            f"<p class='ma-dialog-title'>{safe(application.get('hospital_name'))}</p>"
            f"<p class='ma-dialog-sub'>Submitted {format_date(application.get('created_at'))}</p>"
            "</div>"
            f"{status_pills(application_status, payment_status)}"
            "</div>",
            unsafe_allow_html=True,
        )

        hospital_tab, people_tab, plan_tab, record_tab = st.tabs(
            ["Hospital", "People", "Plan & payment", "Record"]
        )

        # ---------------- Hospital ----------------
        with hospital_tab:
            st.markdown(
                rows_html([
                    ("Type", application.get("hospital_type")),
                    ("Address", application.get("hospital_address")),
                    ("Email", application.get("hospital_email")),
                    ("Contact number", application.get("hospital_contact_number")),
                    ("Website", application.get("hospital_website")),
                ]),
                unsafe_allow_html=True,
            )

        # ---------------- People ----------------
        with people_tab:
            st.markdown(
                "<p class='ma-subtitle'>Authorized representative</p>"
                + rows_html([
                    ("Name", person_name(application, "applicant")),
                    ("Position", application.get("applicant_position")),
                    ("Email", application.get("applicant_email")),
                    ("Contact number", application.get("applicant_contact_number")),
                ])
                + "<p class='ma-subtitle'>Hospital administrator</p>"
                + rows_html([
                    ("Name", person_name(application, "admin")),
                    ("Email", application.get("admin_email")),
                    ("Contact number", application.get("admin_contact_number")),
                ]),
                unsafe_allow_html=True,
            )

        # ---------------- Plan & payment ----------------
        with plan_tab:
            rows = [
                ("Plan", get_plan_name(application)),
                ("Billing cycle", application.get("billing_cycle")),
            ]

            if payment:
                rows += [
                    ("Payment status", payment_label(payment.get("status"))),
                    ("Amount", peso(payment.get("amount"))),
                    ("Method", METHOD_LABELS.get(
                        payment.get("payment_method"),
                        str(payment.get("payment_method") or "").replace("_", " ").title(),
                    )),
                    ("Paid on", format_date(payment.get("paid_at"), with_time=True)),
                    ("Reference", payment.get("provider_reference")),
                ]
            else:
                rows.append(("Payment status", payment_label(payment_status)))

            st.markdown(rows_html(rows), unsafe_allow_html=True)

            if not payment:
                note("No payment record is associated with this application yet.")

        # ---------------- Record ----------------
        with record_tab:
            accepted = application.get("agreement_accepted", False)

            if accepted:
                accepted_text = "Accepted " + format_date(
                    application.get("agreement_accepted_at"), with_time=True
                )
            else:
                accepted_text = "Not accepted"

            st.markdown(
                rows_html([
                    ("Service agreement", accepted_text),
                    ("Application ID", application.get("application_id")),
                    ("Created", format_date(application.get("created_at"), with_time=True)),
                    ("Last updated", format_date(application.get("updated_at"), with_time=True)),
                ]),
                unsafe_allow_html=True,
            )

        close_button(f"close_details_{application_id}")


# ============================================================
# INVOICE DIALOG
# ============================================================

@st.dialog("Invoice", width="medium")
def show_invoice_dialog(application_id):

    application = get_hospital_application(application_id)

    if not application:
        st.error("Unable to load the application.")
        return

    payment = get_latest_payment(application_id)

    with st.container(key="ma_dialog"):

        if not payment:
            note("No payment has been recorded for this application yet, "
                 "so there is no invoice to show.")
            close_button(f"close_invoice_{application_id}")
            return

        status = payment.get("status") or application.get("payment_status")
        is_paid = status == "paid"

        plan_name = get_plan_name(application)
        billing_cycle = payment.get("billing_cycle") or application.get("billing_cycle")
        amount = peso(payment.get("amount"))

        method = payment.get("payment_method")
        method_text = METHOD_LABELS.get(method, str(method or "").replace("_", " ").title())

        paid_on = format_date(payment.get("paid_at"), with_time=True) if is_paid else "Not paid yet"

        # Everything below is one HTML string, built from small pieces
        header = (
            "<div class='ma-inv-top'>"
            "<div>"
            "<p class='ma-inv-label'>Invoice</p>"
            f"<p class='ma-inv-number'>{invoice_number(payment)}</p>"
            "</div>"
            f"{pill(payment_label(status), PAYMENT_TONES.get(status, 'grey'))}"
            "</div>"
        )

        billed_to = (
            "<div class='ma-inv-block'>"
            "<span>Billed to</span>"
            f"<b>{safe(application.get('hospital_name'))}</b>"
            f"<small>{safe(application.get('hospital_address'))}<br>"
            f"{safe(application.get('hospital_email'))} · "
            f"{safe(application.get('hospital_contact_number'))}</small>"
            "</div>"
        )

        payment_block = (
            "<div class='ma-inv-block'>"
            "<span>Invoice date</span>"
            f"<b>{format_date(payment.get('created_at'))}</b>"
            "<span>Paid on</span>"
            f"<b>{paid_on}</b>"
            "<span>Payment method</span>"
            f"<b>{safe(method_text)}</b>"
            "<span>Reference</span>"
            f"<b>{safe(payment.get('provider_reference'))}</b>"
            "</div>"
        )

        lines = (
            "<div class='ma-inv-lines'>"
            "<div class='ma-inv-line ma-inv-line-head'>"
            "<span>Description</span><span>Amount</span></div>"
            "<div class='ma-inv-line'>"
            f"<span>{safe(plan_name)} plan · {safe(billing_cycle)} subscription</span>"
            f"<b>{amount}</b></div>"
            "</div>"
        )

        total = (
            "<div class='ma-inv-total'>"
            f"<span>{'Amount paid' if is_paid else 'Amount due'}</span>"
            f"<b>{amount}</b>"
            "</div>"
        )

        st.markdown(
            "<div class='ma-inv'>"
            f"{header}"
            f"<div class='ma-inv-grid'>{billed_to}{payment_block}</div>"
            f"{lines}{total}"
            "</div>",
            unsafe_allow_html=True,
        )

        close_button(f"close_invoice_{application_id}")


# ============================================================
# APPROVE / REJECT / DELETE DIALOGS
# ============================================================

@st.dialog("Approve application", width="small")
def show_approve_dialog(application_id):

    application = get_hospital_application(application_id)

    if not application:
        st.error("Application could not be found.")
        return

    hospital_name = safe(application.get("hospital_name") or "this hospital")
    payment_status = application.get("payment_status", "unpaid")

    with st.container(key="ma_dialog"):

        st.markdown(
            f"<p class='ma-dialog-text'>Approve the application for <b>{hospital_name}</b>?</p>",
            unsafe_allow_html=True,
        )

        # An unpaid application can never be approved
        if payment_status != "paid":
            note(
                "Payment has not been received "
                f"(status: {payment_label(payment_status)}). "
                "An unpaid application cannot be approved.",
                "red",
            )
            close_button(f"close_unpaid_{application_id}")
            return

        note("Payment confirmed. The application will be marked as Approved.", "green")

        cancel_col, approve_col = st.columns(2)

        if cancel_col.button("Cancel", key=f"cancel_approve_{application_id}", width="stretch"):
            st.rerun()

        if approve_col.button(
            "Approve", type="primary", key=f"confirm_approve_{application_id}", width="stretch"
        ):
            result = approve_hospital_application(application_id)

            if result["success"]:
                remember("Application approved.")
                st.rerun()
            else:
                st.error(f"Unable to approve application: {result['message']}")


@st.dialog("Reject application", width="small")
def show_reject_dialog(application_id):

    application = get_hospital_application(application_id)

    if not application:
        st.error("Application could not be found.")
        return

    hospital_name = safe(application.get("hospital_name") or "this hospital")
    payment_status = application.get("payment_status", "unpaid")

    with st.container(key="ma_dialog"):

        st.markdown(
            f"<p class='ma-dialog-text'>Reject the application for <b>{hospital_name}</b>?</p>",
            unsafe_allow_html=True,
        )

        if payment_status == "paid":
            note(
                "This application has already been paid. Rejecting it means "
                "the refund must be processed manually through PayMongo.",
                "amber",
            )
        else:
            note("The application will be marked as Rejected.")

        st.caption(
            "Rejected applications can be deleted later from the Rejected tab."
        )

        cancel_col, reject_col = st.columns(2)

        if cancel_col.button("Cancel", key=f"cancel_reject_{application_id}", width="stretch"):
            st.rerun()

        if reject_col.button(
            "Reject", type="primary", key=f"confirm_reject_{application_id}", width="stretch"
        ):
            result = reject_hospital_application(application_id)

            if result["success"]:
                remember("Application rejected.")
                st.rerun()
            else:
                st.error(f"Unable to reject application: {result['message']}")


@st.dialog("Delete application", width="small")
def show_delete_dialog(application_id):

    application = get_hospital_application(application_id)

    if not application:
        st.error("Application could not be found.")
        return

    # Safety check: only rejected applications can be deleted
    if application.get("application_status") != "Rejected":
        st.error("Only rejected applications can be deleted.")
        return

    hospital_name = safe(application.get("hospital_name") or "this hospital")

    with st.container(key="ma_dialog"):

        st.markdown(
            f"<p class='ma-dialog-text'>Permanently delete the application for <b>{hospital_name}</b>?</p>",
            unsafe_allow_html=True,
        )

        note(
            "This cannot be undone. All information stored in this "
            "application record will be removed.",
            "red",
        )

        cancel_col, delete_col = st.columns(2)

        if cancel_col.button("Cancel", key=f"cancel_delete_{application_id}", width="stretch"):
            st.rerun()

        if delete_col.button(
            "Delete permanently", type="primary", key=f"confirm_delete_{application_id}", width="stretch"
        ):
            result = delete_hospital_application(application_id)

            if result["success"]:
                remember("Application deleted.")
                st.rerun()
            else:
                st.error(f"Unable to delete application: {result['message']}")


# ============================================================
# APPLICATION CARD
# mode is "pending", "approved" or "rejected"
# ============================================================

def show_card_buttons(application_id, payment_status, mode):

    columns = st.columns([1, 1, 1, 1, 2])

    if columns[0].button(
        "Details", key=f"view_{application_id}",
        icon=":material/visibility:", width="stretch",
    ):
        show_application_details(application_id)

    if columns[1].button(
        "Invoice", key=f"invoice_{application_id}",
        icon=":material/receipt_long:", width="stretch",
    ):
        show_invoice_dialog(application_id)

    if mode == "pending":
        can_approve = payment_status == "paid"

        if columns[2].button(
            "Approve", key=f"approve_{application_id}",
            icon=":material/check:", type="primary", width="stretch",
            disabled=not can_approve,
            help=None if can_approve else "Cannot approve an unpaid application.",
        ):
            show_approve_dialog(application_id)

        if columns[3].button(
            "Reject", key=f"reject_{application_id}",
            icon=":material/close:", width="stretch",
        ):
            show_reject_dialog(application_id)

    if mode == "rejected":
        if columns[2].button(
            "Delete", key=f"delete_{application_id}",
            icon=":material/delete:", width="stretch",
        ):
            show_delete_dialog(application_id)


def render_application_card(application, mode):

    application_id = application.get("application_id")
    application_status = application.get("application_status", "Unknown")
    payment_status = application.get("payment_status", "unpaid")

    with st.container(key=f"app_card_{application_id}"):

        st.markdown(
            "<div class='ma-card-top'>"
            "<div>"
            f"<p class='ma-card-title'>{safe(application.get('hospital_name') or 'Unnamed hospital')}</p>"
            f"<p class='ma-card-meta'>{safe(person_name(application, 'applicant'))}"
            f" · Submitted {format_date(application.get('created_at'))}</p>"
            "</div>"
            f"{status_pills(application_status, payment_status)}"
            "</div>",
            unsafe_allow_html=True,
        )

        show_card_buttons(application_id, payment_status, mode)


def show_application_list(applications, mode, caption, empty_text):
    st.caption(caption)

    if not applications:
        st.markdown(f"<div class='ma-empty'>{empty_text}</div>", unsafe_allow_html=True)
        return

    for application in applications:
        render_application_card(application, mode)


# ============================================================
# MAIN PAGE
# ============================================================

def show():

    load_css()
    show_flash_message()

    # Drafts are pre-payment and not yet submitted, so they are left out
    applications = [
        application
        for application in get_all_hospital_applications()
        if application.get("application_status") != "Draft"
    ]

    pending = [a for a in applications if a.get("application_status") == "Pending"]
    approved = [a for a in applications if a.get("application_status") == "Approved"]
    rejected = [a for a in applications if a.get("application_status") == "Rejected"]

    with st.container(key="ma_page"):

        st.markdown(
            "<p class='ma-page-title'>Hospital applications</p>"
            "<p class='ma-page-caption'>Review and manage hospital subscription applications.</p>",
            unsafe_allow_html=True,
        )

        pending_col, approved_col, rejected_col = st.columns(3)

        with pending_col:
            metric_card("Pending review", len(pending), "hourglass_top", "amber")

        with approved_col:
            metric_card("Approved", len(approved), "check_circle", "green")

        with rejected_col:
            metric_card("Rejected", len(rejected), "cancel", "red")

        pending_tab, approved_tab, rejected_tab = st.tabs([
            f"Pending ({len(pending)})",
            f"Approved ({len(approved)})",
            f"Rejected ({len(rejected)})",
        ])

        with pending_tab:
            show_application_list(
                pending, "pending",
                "Waiting for review. Only paid applications can be approved.",
                "No pending applications.",
            )

        with approved_tab:
            show_application_list(
                approved, "approved",
                "Applications that have been approved.",
                "No approved applications yet.",
            )

        with rejected_tab:
            show_application_list(
                rejected, "rejected",
                "Rejected applications. Deleting one is permanent.",
                "No rejected applications.",
            )