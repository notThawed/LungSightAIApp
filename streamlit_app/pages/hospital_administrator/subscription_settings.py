# streamlit_app/pages/hospital_administrator/subscription_settings.py

"""
Hospital Admin — Subscription Settings.

Shows the current plan, available plans, and payment history.
Supports Cancel, Reactivate, and unified Change Plan
(upgrade via PayMongo, downgrade scheduled for next cycle).
"""

import streamlit as st

from backend.backend_utils.subscription_utils import (
    get_hospital_subscription_row,
    get_all_subscription_plans,
    cancel_subscription,
    reactivate_subscription,
    schedule_downgrade,
    undo_scheduled_downgrade,
)

from backend.backend_utils.subscription_usage import (
    get_remaining_usage,
)

from backend.payments import (
    compute_prorated_amount,
    create_upgrade_checkout_session,
    get_upgrade_status,
)

from backend.supabase_client import admin_supabase

from streamlit_app.components.ui import (
    page_header,
    section_title,
    empty_state,
    safe,
    show_flash_message,
)

from streamlit_app.pages.hospital_administrator.subscription_gate import (
    show_checkout_link_screen,
    show_renewal_success_screen,
    SESSION_RENEWAL_PAYMENT,
    SESSION_RENEWAL_URL,
    SESSION_RENEWAL_SUCCESS,
    _reset_renewal_session,
)

from shared.assets import load_css


# ============================================================
# CONSTANTS
# ============================================================

SESSION_UPGRADE_FLOW = "ss_upgrade_flow"


def _svg(paths):
    return (
        "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' "
        "stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' "
        f"aria-hidden='true'>{paths}</svg>"
    )


ICON_LAYERS = _svg(
    "<path d='m12 2 10 5-10 5L2 7z'/>"
    "<path d='m2 17 10 5 10-5M2 12l10 5 10-5'/>"
)


# ============================================================
# USER HELPERS
# ============================================================

def current_user():
    return st.session_state.get("user") or {}


def current_hospital_id():
    return current_user().get("hospital_id")


# ============================================================
# FORMATTERS
# ============================================================

def peso(amount):
    if amount is None:
        return "—"
    try:
        return f"₱{float(amount):,.2f}"
    except (TypeError, ValueError):
        return "—"


def limit_text(value):
    if value is None:
        return "Unlimited"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def format_date(value):
    if not value:
        return "—"
    return str(value)


def plan_price_for(plan, billing_cycle):
    """Return (amount, period_word) for a plan in the current cycle."""
    if billing_cycle == "Yearly":
        return plan.get("price_yearly"), "year"
    return plan.get("price_monthly"), "month"


# ============================================================
# DATA LOADERS
# ============================================================

def load_current_subscription(hospital_id):
    try:
        return get_hospital_subscription_row(hospital_id)
    except Exception as exc:
        print(f"Failed to load subscription row: {exc}")
        return None


def load_current_plan(plan_id):
    if not plan_id:
        return None

    try:
        response = (
            admin_supabase
            .table("subscription_plans")
            .select("*")
            .eq("plan_id", plan_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception as exc:
        print(f"Failed to load plan {plan_id}: {exc}")
        return None


def load_all_active_plans():
    try:
        plans = get_all_subscription_plans() or []
        return [p for p in plans if p.get("is_active", True)]
    except Exception as exc:
        print(f"Failed to load plans: {exc}")
        return []


def load_payment_history(hospital_id, limit=5):
    try:
        response = (
            admin_supabase
            .table("payments")
            .select(
                "payment_id,"
                "amount,"
                "currency,"
                "billing_cycle,"
                "status,"
                "payment_type,"
                "paid_at,"
                "created_at"
            )
            .eq("hospital_id", hospital_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        print(f"Failed to load payment history: {exc}")
        return []


# ============================================================
# CACHE CONTROL
# ============================================================

def refresh_after_mutation():
    """Clear the cached subscription context and rerun."""
    st.session_state.pop("subscription_context", None)
    st.session_state.pop("grace_info", None)
    st.rerun()


# ============================================================
# PAGE
# ============================================================

def show():
    load_css("subscription_settings.css")
    show_flash_message()

    hospital_id = current_hospital_id()

    # PayMongo sub-flow interceptor
    if st.session_state.get(SESSION_RENEWAL_SUCCESS):
        _, center, _ = st.columns([1, 6, 1])
        with center:
            with st.container(key="ss_page"):
                if st.session_state.get(SESSION_UPGRADE_FLOW):
                    show_upgrade_success_screen()
                else:
                    show_renewal_success_screen()
        return

    if st.session_state.get(SESSION_RENEWAL_PAYMENT):
        _, center, _ = st.columns([1, 6, 1])
        with center:
            with st.container(key="ss_page"):
                show_checkout_link_screen()
        return

    _, center, _ = st.columns([1, 6, 1])

    with center:
        with st.container(key="ss_page"):

            page_header(
                "Subscription Settings",
                "Manage your hospital's LungSight plan and billing.",
            )

            if not hospital_id:
                st.error(
                    "Your account is not assigned to a hospital. "
                    "Please contact your Superadmin."
                )
                return

            subscription = load_current_subscription(hospital_id)

            if not subscription:
                st.warning(
                    "No subscription was found for your hospital. "
                    "Please contact support."
                )
                return

            current_plan_id = subscription.get("plan_id")
            current_plan = load_current_plan(current_plan_id)
            all_plans = load_all_active_plans()
            payments = load_payment_history(hospital_id)

            render_current_plan_card(subscription, current_plan)
            render_scheduled_changes(subscription)
            render_all_plans(
                all_plans,
                current_plan_id,
                current_plan,
                subscription,
            )
            render_payment_history(payments)


# ============================================================
# CURRENT PLAN CARD
# ============================================================

def render_current_plan_card(subscription, plan):

    if not plan:
        empty_state("Current plan could not be loaded.")
        return

    billing_cycle = subscription.get("billing_cycle") or "—"

    if billing_cycle == "Yearly":
        price = plan.get("price_yearly")
        period = "year"
    else:
        price = plan.get("price_monthly")
        period = "month"

    status = subscription.get("status") or "Unknown"
    start_date = format_date(subscription.get("start_date"))
    end_date = format_date(subscription.get("end_date"))

    cancelled = bool(subscription.get("cancel_at_period_end"))

    if cancelled:
        status_label = "Cancels at period end"
        status_tone = "amber"
    elif status == "Active":
        status_label = "Active"
        status_tone = "green"
    elif status == "Pending Setup":
        status_label = "Pending Setup"
        status_tone = "amber"
    elif status == "Cancelled":
        status_label = "Cancelled"
        status_tone = "red"
    elif status == "Expired":
        status_label = "Expired"
        status_tone = "red"
    else:
        status_label = status
        status_tone = "slate"

    # Navy hero card
    # Left : plan name + price
    # Right: status pill (top) and Cancel button (below), right-aligned
    with st.container(key="ss_current_card"):

        left_col, right_col = st.columns(
            [4, 1.6],
            vertical_alignment="top",
        )

        with left_col:

            st.markdown(
                "<p class='ss-current-eyebrow'>Current plan</p>"
                f"<p class='ss-current-name'>{safe(plan.get('plan_name'))}</p>"
                f"<p class='ss-current-price'>{peso(price)}"
                f"<small> / {safe(period)}</small></p>",
                unsafe_allow_html=True,
            )

        with right_col:

            # Status pill on top
            st.markdown(
                "<div class='ss-current-pill-wrap'>"
                f"<span class='ss-pill ss-pill-{status_tone}'>"
                f"{safe(status_label)}"
                "</span>"
                "</div>",
                unsafe_allow_html=True,
            )

            # Cancel / Reactivate below the pill, right-aligned
            render_current_plan_actions(subscription, cancelled)

    # Limits
    st.markdown(
        "<div class='ss-limits'>"
        "<div class='ss-limit'>"
        f"<b>{limit_text(plan.get('max_users'))}</b><span>Users</span>"
        "</div>"
        "<div class='ss-limit'>"
        f"<b>{limit_text(plan.get('max_patients'))}</b><span>Patients</span>"
        "</div>"
        "<div class='ss-limit'>"
        f"<b>{limit_text(plan.get('max_xrays_per_month'))}</b><span>X-rays / month</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Dates
    st.markdown(
        "<div class='ss-dates'>"
        "<div>"
        "<span class='ss-dates-label'>Started</span>"
        f"<span class='ss-dates-value'>{safe(start_date)}</span>"
        "</div>"
        "<div>"
        "<span class='ss-dates-label'>Renews</span>"
        f"<span class='ss-dates-value'>{safe(end_date)}</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_current_plan_actions(subscription, cancelled):
    """Cancel / Reactivate button — right-aligned, below the status pill."""

    subscription_id = subscription.get("hospital_subscription_id")

    if not subscription_id:
        return

    if cancelled:
        if st.button(
            "Reactivate",
            key="ss_reactivate_btn",
            icon=":material/restart_alt:",
            width="stretch",
        ):
            open_reactivate_dialog(subscription)
        return

    if st.button(
        "Cancel Subscription",
        key="ss_cancel_btn",
        icon=":material/cancel:",
        width="stretch",
    ):
        open_cancel_dialog(subscription)


# ============================================================
# CANCEL DIALOG
# ============================================================

@st.dialog("Cancel Subscription", width="small")
def open_cancel_dialog(subscription):

    subscription_id = subscription.get("hospital_subscription_id")
    end_date = format_date(subscription.get("end_date"))

    st.markdown(
        "<p style='font-size:0.9rem; line-height:1.55; "
        "color:var(--ls-text-soft); margin-bottom:1rem;'>"
        "Cancelling your subscription means that LungSight "
        "will stop billing you after your current billing "
        "period ends."
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='ss-dialog-note ss-dialog-note-amber'>"
        "<span class='material-symbols-rounded'>info</span>"
        f"<div>You will keep full access until "
        f"<b>{safe(end_date)}</b>. After that, your account "
        f"will stop working until you renew."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p style='font-size:0.85rem; color:var(--ls-text-soft); "
        "margin-top:0.75rem;'>"
        "You can reactivate at any time before the end date."
        "</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    cancel_col, confirm_col = st.columns(2)

    with cancel_col:
        if st.button(
            "Keep Subscription",
            key="ss_cancel_abort",
            width="stretch",
        ):
            st.rerun()

    with confirm_col:
        if st.button(
            "Yes, cancel",
            key="ss_cancel_confirm",
            type="primary",
            icon=":material/cancel:",
            width="stretch",
        ):
            result = cancel_subscription(subscription_id)

            if result.get("success"):
                st.session_state["ss_flash"] = (
                    "Your subscription will be cancelled at "
                    "the end of the current billing period."
                )
                refresh_after_mutation()
            else:
                st.error(
                    f"Could not cancel subscription: "
                    f"{result.get('message', 'Unknown error')}"
                )


# ============================================================
# REACTIVATE DIALOG
# ============================================================

@st.dialog("Reactivate Subscription", width="small")
def open_reactivate_dialog(subscription):

    subscription_id = subscription.get("hospital_subscription_id")
    end_date = format_date(subscription.get("end_date"))

    st.markdown(
        "<p style='font-size:0.9rem; line-height:1.55; "
        "color:var(--ls-text-soft); margin-bottom:1rem;'>"
        "Reactivating will undo the scheduled cancellation. "
        "Your subscription will continue as normal."
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='ss-dialog-note ss-dialog-note-green'>"
        "<span class='material-symbols-rounded'>check_circle</span>"
        f"<div>Your plan will renew on <b>{safe(end_date)}</b> "
        f"as originally scheduled.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    abort_col, confirm_col = st.columns(2)

    with abort_col:
        if st.button(
            "Go back",
            key="ss_reactivate_abort",
            width="stretch",
        ):
            st.rerun()

    with confirm_col:
        if st.button(
            "Reactivate",
            key="ss_reactivate_confirm",
            type="primary",
            icon=":material/restart_alt:",
            width="stretch",
        ):
            result = reactivate_subscription(subscription_id)

            if result.get("success"):
                st.session_state["ss_flash"] = "Subscription reactivated."
                refresh_after_mutation()
            else:
                st.error(
                    f"Could not reactivate subscription: "
                    f"{result.get('message', 'Unknown error')}"
                )


# ============================================================
# SCHEDULED CHANGES BANNER
# ============================================================

def render_scheduled_changes(subscription):

    pending_plan_id = subscription.get("pending_plan_id")
    cancel_at_end = bool(subscription.get("cancel_at_period_end"))

    if not pending_plan_id and not cancel_at_end:
        return

    end_date = format_date(subscription.get("end_date"))
    subscription_id = subscription.get("hospital_subscription_id")

    with st.container(key="ss_scheduled"):

        if cancel_at_end:
            st.info(
                f"Your subscription is scheduled to be cancelled "
                f"on **{end_date}**. You can continue using LungSight "
                f"until then."
            )
            return

        pending_plan = load_current_plan(pending_plan_id)
        pending_name = (
            pending_plan.get("plan_name")
            if pending_plan
            else f"plan #{pending_plan_id}"
        )

        info_col, action_col = st.columns([4, 1])

        with info_col:
            st.info(
                f"Your subscription is scheduled to switch to "
                f"**{pending_name}** on **{end_date}**."
            )

        with action_col:
            if st.button(
                "Undo",
                key="ss_undo_downgrade",
                icon=":material/undo:",
                width="stretch",
            ):
                result = undo_scheduled_downgrade(subscription_id)

                if result.get("success"):
                    st.session_state["ss_flash"] = (
                        "Scheduled plan change cancelled."
                    )
                    refresh_after_mutation()
                else:
                    st.error(
                        f"Could not undo scheduled change: "
                        f"{result.get('message', 'Unknown error')}"
                    )


# ============================================================
# PLANS GRID
# ============================================================

def render_all_plans(plans, current_plan_id, current_plan, subscription):

    section_title(
        "Available plans",
        "Every plan currently offered on LungSight.",
    )

    if not plans:
        empty_state("No plans available.")
        return

    billing_cycle = subscription.get("billing_cycle") or "Monthly"
    pending_plan_id = subscription.get("pending_plan_id")

    current_price, _ = plan_price_for(current_plan, billing_cycle)
    current_price = float(current_price or 0)

    with st.container(key="ss_plans_grid"):

        cols_per_row = 3

        for row_start in range(0, len(plans), cols_per_row):
            row_plans = plans[row_start: row_start + cols_per_row]
            columns = st.columns(cols_per_row, gap="medium")

            for col, plan in zip(columns, row_plans):
                with col:
                    render_plan_card(
                        plan=plan,
                        is_current=(plan.get("plan_id") == current_plan_id),
                        is_scheduled=(plan.get("plan_id") == pending_plan_id),
                        current_price=current_price,
                        billing_cycle=billing_cycle,
                        subscription=subscription,
                    )


def render_plan_card(
    plan,
    is_current,
    is_scheduled,
    current_price,
    billing_cycle,
    subscription,
):
    """Render a single plan card (login-page style)."""

    plan_name = plan.get("plan_name") or "Unnamed Plan"
    description = plan.get("description") or "LungSight subscription plan."
    plan_id = plan.get("plan_id")

    price_monthly = peso(plan.get("price_monthly"))
    price_yearly = peso(plan.get("price_yearly"))

    max_users = limit_text(plan.get("max_users"))
    max_patients = limit_text(plan.get("max_patients"))
    max_xrays = limit_text(plan.get("max_xrays_per_month"))

    if is_current:
        badge_html = (
            "<span class='ss-plan-badge ss-plan-badge-current'>"
            "Current plan</span>"
        )
    elif is_scheduled:
        badge_html = (
            "<span class='ss-plan-badge ss-plan-badge-scheduled'>"
            "Scheduled</span>"
        )
    else:
        badge_html = ""

    features = "".join([
        f"<div class='ss-plan-feature'><span>Users</span><b>{max_users}</b></div>",
        f"<div class='ss-plan-feature'><span>Patients</span><b>{max_patients}</b></div>",
        f"<div class='ss-plan-feature'><span>X-rays / month</span><b>{max_xrays}</b></div>",
    ])

    card_html = "".join([
        f"<div class='ss-plan-icon'>{ICON_LAYERS}</div>",
        "<div class='ss-plan-head'>",
        f"<p class='ss-plan-name'>{safe(plan_name)}</p>",
        badge_html,
        "</div>",
        f"<p class='ss-plan-desc'>{safe(description)}</p>",
        "<div class='ss-plan-price-row'>",
        f"<p class='ss-plan-price'>{price_monthly}</p>",
        "<span>/ month</span>",
        "</div>",
        f"<p class='ss-plan-yearly'>or {price_yearly} per year</p>",
        "<div class='ss-plan-features'>",
        features,
        "</div>",
    ])

    with st.container(key=f"ss_plan_card_{plan_id}"):

        st.markdown(card_html, unsafe_allow_html=True)

        render_plan_action_button(
            plan=plan,
            is_current=is_current,
            is_scheduled=is_scheduled,
            current_price=current_price,
            billing_cycle=billing_cycle,
            subscription=subscription,
        )


def render_plan_action_button(
    plan,
    is_current,
    is_scheduled,
    current_price,
    billing_cycle,
    subscription,
):
    """Unified Change Plan button — decides upgrade vs downgrade in the dialog."""

    plan_id = plan.get("plan_id")

    if is_current:
        st.button(
            "Current plan",
            key=f"ss_plan_btn_{plan_id}",
            icon=":material/check_circle:",
            width="stretch",
            disabled=True,
        )
        return

    if is_scheduled:
        st.button(
            "Scheduled",
            key=f"ss_plan_btn_{plan_id}",
            icon=":material/schedule:",
            width="stretch",
            disabled=True,
        )
        return

    new_price, _ = plan_price_for(plan, billing_cycle)
    new_price = float(new_price or 0)

    if new_price == current_price:
        st.button(
            "Change Plan",
            key=f"ss_plan_btn_{plan_id}",
            icon=":material/swap_horiz:",
            width="stretch",
            disabled=True,
        )
        return

    if st.button(
        "Change Plan",
        key=f"ss_plan_btn_{plan_id}",
        icon=":material/swap_horiz:",
        width="stretch",
    ):
        open_change_plan_dialog(
            subscription=subscription,
            target_plan=plan,
            current_price=current_price,
        )


# ============================================================
# UNIFIED CHANGE PLAN DIALOG
# ============================================================

@st.dialog("Change Plan", width="small")
def open_change_plan_dialog(subscription, target_plan, current_price):
    """Opens one dialog that adapts based on target plan price."""

    subscription_id = subscription.get("hospital_subscription_id")
    target_plan_id = target_plan.get("plan_id")
    target_name = target_plan.get("plan_name") or "the new plan"

    if not subscription_id or not target_plan_id:
        st.error("Missing plan or subscription information.")
        return

    billing_cycle = subscription.get("billing_cycle") or "Monthly"

    new_price, _ = plan_price_for(target_plan, billing_cycle)
    new_price = float(new_price or 0)

    if new_price < current_price:
        _render_downgrade_content(
            subscription, target_plan, subscription_id, target_name,
        )
        return

    if new_price > current_price:
        _render_upgrade_content(
            subscription, target_plan, subscription_id,
            target_plan_id, target_name,
        )
        return

    st.info("This plan has the same price as your current plan.")

    if st.button("Close", key="ss_change_close", width="stretch"):
        st.rerun()


def _render_downgrade_content(
    subscription, target_plan, subscription_id, target_name,
):
    """Downgrade branch — schedules the switch for end of cycle."""

    end_date = format_date(subscription.get("end_date"))

    st.markdown(
        "<p style='font-size:0.9rem; line-height:1.55; "
        "color:var(--ls-text-soft); margin-bottom:1rem;'>"
        f"You're switching to <b>{safe(target_name)}</b>. "
        "This change takes effect at the end of your "
        "current billing period."
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='ss-dialog-note ss-dialog-note-amber'>"
        "<span class='material-symbols-rounded'>event</span>"
        f"<div>You'll keep your current plan's features until "
        f"<b>{safe(end_date)}</b>. On that date, your plan "
        f"will switch to <b>{safe(target_name)}</b>."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p style='font-size:0.85rem; color:var(--ls-text-soft); "
        "margin-top:0.75rem;'>"
        "You can undo this scheduled change any time before "
        "the switch date."
        "</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    abort_col, confirm_col = st.columns(2)

    with abort_col:
        if st.button(
            "Keep current plan",
            key="ss_change_abort",
            width="stretch",
        ):
            st.rerun()

    with confirm_col:
        if st.button(
            "Confirm change",
            key="ss_change_confirm_downgrade",
            type="primary",
            icon=":material/check:",
            width="stretch",
        ):
            result = schedule_downgrade(
                subscription_id,
                target_plan.get("plan_id"),
            )

            if result.get("success"):
                st.session_state["ss_flash"] = (
                    f"Plan change to {target_name} scheduled."
                )
                refresh_after_mutation()
            else:
                st.error(
                    f"Could not schedule plan change: "
                    f"{result.get('message', 'Unknown error')}"
                )


def _render_upgrade_content(
    subscription, target_plan, subscription_id,
    target_plan_id, target_name,
):
    """Upgrade branch — prorated charge via PayMongo."""

    with st.spinner("Calculating upgrade cost..."):

        proration = compute_prorated_amount(
            subscription_id,
            target_plan_id,
        )

    if not proration.get("success"):
        st.error(
            f"Could not compute upgrade cost: "
            f"{proration.get('message', 'Unknown error')}"
        )
        return

    amount = proration.get("amount", 0)
    days_left = proration.get("days_left", 0)
    cycle_days = proration.get("cycle_days", 0)
    old_name = proration.get("old_plan_name") or "your current plan"

    st.markdown(
        "<p style='font-size:0.9rem; line-height:1.55; "
        "color:var(--ls-text-soft); margin-bottom:1rem;'>"
        f"You're upgrading from <b>{safe(old_name)}</b> to "
        f"<b>{safe(target_name)}</b>. Your new features activate "
        "as soon as payment is confirmed."
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='ss-dialog-note ss-dialog-note-blue'>"
        "<span class='material-symbols-rounded'>schedule</span>"
        "<div>"
        f"<b>₱{amount:,.2f}</b> will be charged today.<br>"
        f"<span style='font-size:0.82rem;'>"
        f"Prorated for the <b>{days_left}</b> days remaining in "
        f"your current <b>{cycle_days}-day</b> billing cycle."
        "</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p style='font-size:0.85rem; color:var(--ls-text-soft); "
        "margin-top:0.75rem;'>"
        "Your next renewal date and price will remain the same."
        "</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    cancel_col, confirm_col = st.columns(2)

    with cancel_col:
        if st.button(
            "Cancel",
            key="ss_change_abort",
            width="stretch",
        ):
            st.rerun()

    with confirm_col:
        if st.button(
            "Proceed to PayMongo",
            key="ss_change_confirm_upgrade",
            type="primary",
            icon=":material/arrow_forward:",
            width="stretch",
        ):
            _start_upgrade_checkout(subscription_id, target_plan_id)


def _start_upgrade_checkout(subscription_id, target_plan_id):
    """Create the PayMongo session and hand off to the checkout screen."""

    with st.spinner("Preparing checkout..."):

        result = create_upgrade_checkout_session(
            subscription_id,
            target_plan_id,
        )

    if not result.get("success"):
        st.error(
            result.get("message", "Failed to create checkout session.")
        )
        return

    st.session_state[SESSION_RENEWAL_PAYMENT] = result["payment_id"]
    st.session_state[SESSION_RENEWAL_URL] = result["checkout_url"]
    st.session_state[SESSION_UPGRADE_FLOW] = True

    st.rerun()


# ============================================================
# UPGRADE SUCCESS SCREEN
# ============================================================

def show_upgrade_success_screen():

    st.markdown(
        "<div style='text-align:center; margin-bottom:0.5rem;'>"
        "<span class='material-symbols-rounded' "
        "style='font-size:56px; color:var(--ls-success);'>"
        "upgrade"
        "</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>"
        "Plan Upgraded</h2>",
        unsafe_allow_html=True,
    )

    st.success(
        "Your payment was received and your new plan is "
        "now active."
    )

    st.info(
        "All new features and limits are available immediately. "
        "Your billing date stays the same."
    )

    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button(
            "Back to Subscription Settings",
            type="primary",
            use_container_width=True,
            key="ss_upgrade_continue",
            icon=":material/arrow_forward:",
        ):
            _reset_renewal_session()
            st.session_state.pop(SESSION_UPGRADE_FLOW, None)
            st.session_state.pop("subscription_context", None)
            st.session_state.pop("grace_info", None)
            st.rerun()


# ============================================================
# PAYMENT HISTORY
# ============================================================

def render_payment_history(payments):

    section_title("Recent payments", "Your last five transactions.")

    if not payments:
        empty_state("No payments yet.")
        return

    with st.container(key="ss_payments"):

        st.markdown(
            "<div class='ss-payment-row ss-payment-header'>"
            "<span>Date</span><span>Type</span>"
            "<span>Amount</span><span>Status</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        for payment in payments:

            when = str(
                payment.get("paid_at")
                or payment.get("created_at")
                or "—"
            )[:10]

            ptype = payment.get("payment_type") or "—"
            amount = peso(payment.get("amount"))
            status = payment.get("status") or "—"

            if status == "paid":
                tone = "green"
            elif status == "pending":
                tone = "amber"
            elif status == "failed":
                tone = "red"
            else:
                tone = "slate"

            st.markdown(
                "<div class='ss-payment-row'>"
                f"<span>{safe(when)}</span>"
                f"<span class='ss-payment-type'>{safe(ptype)}</span>"
                f"<span class='ss-payment-amount'>{amount}</span>"
                "<span class='ss-payment-status-cell'>"
                f"<span class='ss-pill ss-pill-{tone}'>"
                f"{safe(status)}</span>"
                "</span>"
                "</div>",
                unsafe_allow_html=True,
            )
