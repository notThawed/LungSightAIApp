# streamlit_app/pages/hospital_administrator/subscription_gate.py

"""
Physician / Hospital Admin — Subscription Gate.

Handles:
  - Expired subscription takeover
  - Grace period warning banner
  - Pre-expiry info banner
  - Renewal flow (confirmation → PayMongo → success)
"""

import streamlit as st


# ============================================================
# SESSION KEYS
# ============================================================

SESSION_SHOW_RENEWAL      = "show_renewal_screen"
SESSION_RENEWAL_PAYMENT   = "renewal_payment_id"
SESSION_RENEWAL_URL       = "renewal_checkout_url"
SESSION_RENEWAL_SUCCESS   = "renewal_success"
SESSION_RENEWAL_DISMISSED = "renewal_banner_dismissed"


# ============================================================
# CSS — NOTIFICATION BANNERS
# ============================================================

_NOTIFICATION_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

.material-symbols-rounded {
  font-family: 'Material Symbols Rounded';
  font-feature-settings: 'liga';
  -webkit-font-smoothing: antialiased;
  vertical-align: middle;
}

/* ---------------------------------------------------------
   Renewal notification banner (inline, single-row)
   --------------------------------------------------------- */

.st-key-renewal_notification_info,
.st-key-renewal_notification_grace {
  padding: 12px 16px !important;
  border-radius: 10px !important;
  border: 1px solid !important;
  margin-bottom: 1rem !important;
  box-shadow: 0 1px 3px rgba(18, 40, 58, 0.04) !important;
}

.st-key-renewal_notification_info {
  background: #F5FBFC !important;
  border-color: #CFE7EB !important;
  border-left: 4px solid var(--ls-primary) !important;
}

.st-key-renewal_notification_grace {
  background: #FFFDF5 !important;
  border-color: #FDE7B5 !important;
  border-left: 4px solid var(--ls-warning) !important;
}

/* Compact buttons inside the banner */

.st-key-renewal_notification_info [data-testid="stButton"] button,
.st-key-renewal_notification_grace [data-testid="stButton"] button {
  min-height: 30px !important;
  height: 30px !important;
  padding: 0 12px !important;
  font-size: 12.5px !important;
  border-radius: 6px !important;
  margin: 0 !important;
}

.st-key-renewal_notification_info [data-testid="stButton"] button p,
.st-key-renewal_notification_grace [data-testid="stButton"] button p {
  font-size: 12.5px !important;
  font-weight: 600 !important;
}

.st-key-renewal_notification_info [data-testid="stButton"] button[data-baseweb="button"][kind="primary"] {
  background: var(--ls-primary) !important;
  border-color: var(--ls-primary) !important;
}

.st-key-renewal_notification_info [data-testid="stButton"] button[data-baseweb="button"][kind="primary"] p {
  color: #FFFFFF !important;
}

.st-key-renewal_notification_grace [data-testid="stButton"] button[data-baseweb="button"][kind="primary"] {
  background: var(--ls-warning) !important;
  border-color: var(--ls-warning) !important;
}

.st-key-renewal_notification_grace [data-testid="stButton"] button[data-baseweb="button"][kind="primary"] p {
  color: #FFFFFF !important;
}

/* Dismiss "×" button — ghost style */

[class*="st-key-renewal_dismiss_"] [data-testid="stButton"] button {
  min-height: 28px !important;
  height: 28px !important;
  width: 28px !important;
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  color: var(--ls-text-soft) !important;
  font-size: 16px !important;
}

[class*="st-key-renewal_dismiss_"] [data-testid="stButton"] button:hover {
  background: rgba(90, 111, 127, 0.10) !important;
  border-radius: 4px !important;
}

[class*="st-key-renewal_dismiss_"] [data-testid="stButton"] button p {
  font-size: 14px !important;
  font-weight: 500 !important;
  color: var(--ls-text-soft) !important;
}
"""


def _inject_css():
    st.markdown(f"<style>{_NOTIFICATION_CSS}</style>", unsafe_allow_html=True)


# ============================================================
# HELPERS
# ============================================================

def _reset_renewal_session():
    """Clear all renewal-related session keys."""

    for key in (
        SESSION_SHOW_RENEWAL,
        SESSION_RENEWAL_PAYMENT,
        SESSION_RENEWAL_URL,
        SESSION_RENEWAL_SUCCESS,
    ):
        st.session_state.pop(key, None)


def _start_renewal_flow():
    """Called when the user clicks Renew."""

    st.session_state[SESSION_SHOW_RENEWAL] = True
    st.rerun()


def _dismiss_banner():
    st.session_state[SESSION_RENEWAL_DISMISSED] = True
    st.rerun()


def _is_banner_dismissed():
    return bool(st.session_state.get(SESSION_RENEWAL_DISMISSED, False))


# ============================================================
# RENEW BUTTON (used on expired screen)
# ============================================================

def _render_renew_button(key_suffix="default"):

    if st.button(
        "Renew Subscription",
        type="primary",
        use_container_width=True,
        key=f"renew_button_{key_suffix}",
        icon=":material/autorenew:",
    ):
        _start_renewal_flow()


# ============================================================
# INLINE NOTIFICATION BANNER (single-row)
# ============================================================

def _render_inline_notification(tone, icon, message):
    """
    Render the single-row notification banner.

    Layout:
        [icon]  [message .........................]  [Renew]  [×]
    """

    key = f"renewal_notification_{tone}"

    with st.container(key=key):

        icon_col, msg_col, renew_col, dismiss_col = st.columns(
            [0.5, 8, 1.1, 0.5],
            vertical_alignment="center",
        )

        # Icon
        with icon_col:
            icon_color = "var(--ls-primary)" if tone == "info" else "var(--ls-warning)"
            st.markdown(
                f"<span class='material-symbols-rounded' "
                f"style='font-size:20px; color:{icon_color};'>"
                f"{icon}</span>",
                unsafe_allow_html=True,
            )

        # Message
        with msg_col:
            text_color = "var(--ls-ink)" if tone == "info" else "var(--ls-warning)"
            st.markdown(
                f"<p style='margin:0; font-size:13.5px; "
                f"line-height:1.4; color:{text_color};'>"
                f"{message}"
                f"</p>",
                unsafe_allow_html=True,
            )

        # Renew
        with renew_col:
            if st.button(
                "Renew",
                key=f"renew_inline_{tone}",
                type="primary",
                use_container_width=True,
            ):
                _start_renewal_flow()

        # Dismiss
        with dismiss_col:
            if st.button(
                "×",
                key=f"renewal_dismiss_{tone}",
                use_container_width=True,
            ):
                _dismiss_banner()


# ============================================================
# RENEWAL CONFIRMATION SCREEN
# ============================================================

def show_renewal_confirmation_screen(
    hospital_name=None,
    plan_name=None,
    billing_cycle=None,
    amount=None,
    is_expired_screen=False,
):

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>"
        "Renew Subscription"
        "</h2>",
        unsafe_allow_html=True,
    )

    if hospital_name:
        st.markdown(
            "<p style='text-align:center; color:var(--ls-text-soft); "
            "margin:0 0 1rem;'>"
            f"{hospital_name}"
            "</p>",
            unsafe_allow_html=True,
        )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Plan:** {plan_name or '—'}")

    with col2:
        st.write(f"**Billing Cycle:** {billing_cycle or '—'}")

    if amount is not None:
        st.metric("Amount Due", f"₱{amount:,.2f}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Cancel",
            use_container_width=True,
            key="renewal_cancel",
        ):
            _reset_renewal_session()
            st.rerun()

    with col2:
        if st.button(
            "Proceed to PayMongo",
            type="primary",
            use_container_width=True,
            key="renewal_proceed",
            icon=":material/arrow_forward:",
        ):
            _create_and_show_checkout()


def _create_and_show_checkout():

    from backend.payments import create_renewal_checkout_session

    subscription_id = st.session_state.get(
        "subscription_context", {}
    ).get("subscription_id")

    if not subscription_id:
        st.error(
            "Could not find your subscription. "
            "Please log out and log in again."
        )
        return

    with st.spinner("Preparing checkout..."):
        result = create_renewal_checkout_session(subscription_id)

    if not result.get("success"):
        st.error(
            result.get("message", "Failed to create checkout session.")
        )
        return

    st.session_state[SESSION_RENEWAL_PAYMENT] = result["payment_id"]
    st.session_state[SESSION_RENEWAL_URL] = result["checkout_url"]

    st.rerun()


# ============================================================
# CHECKOUT LINK SCREEN
# ============================================================

def show_checkout_link_screen():

    from backend.payments import get_renewal_status

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>"
        "Complete Your Payment"
        "</h2>",
        unsafe_allow_html=True,
    )

    st.success(
        "Your checkout session is ready. "
        "Complete the payment in the PayMongo tab."
    )

    checkout_url = st.session_state.get(SESSION_RENEWAL_URL)

    if checkout_url:
        st.markdown(
            f"<div style='text-align:center; margin:1rem 0;'>"
            f"<a href='{checkout_url}' target='_blank' "
            f"style='display:inline-block; padding:0.6rem 1.2rem; "
            f"background:var(--ls-primary); color:#FFFFFF; "
            f"text-decoration:none; border-radius:8px; "
            f"font-weight:600;'>"
            "Open PayMongo Checkout"
            "</a>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.info(
        "After paying, click **Refresh Status** below. "
        "Your subscription will be renewed once the "
        "payment is confirmed."
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Cancel",
            use_container_width=True,
            key="renewal_checkout_cancel",
        ):
            _reset_renewal_session()
            st.rerun()

    with col2:
        if st.button(
            "Refresh Status",
            type="primary",
            use_container_width=True,
            key="renewal_refresh",
            icon=":material/refresh:",
        ):

            payment_id = st.session_state.get(SESSION_RENEWAL_PAYMENT)

            if not payment_id:
                st.error("No payment in progress.")
                return

            status = get_renewal_status(payment_id)

            if status.get("paid"):
                st.session_state[SESSION_RENEWAL_SUCCESS] = True
                st.rerun()
            else:
                st.warning(
                    f"Payment status: **{status.get('status')}**. "
                    "Please wait a moment and try again."
                )


# ============================================================
# SUCCESS SCREEN
# ============================================================

def show_renewal_success_screen():

    st.markdown(
        "<div style='text-align:center; margin-bottom:0.5rem;'>"
        "<span class='material-symbols-rounded' "
        "style='font-size:56px; color:var(--ls-success);'>"
        "check_circle"
        "</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>"
        "Subscription Renewed</h2>",
        unsafe_allow_html=True,
    )

    st.success(
        "Your payment was received and your subscription "
        "has been renewed."
    )

    st.info(
        "Your new billing period will be reflected shortly. "
        "You can continue using LungSight."
    )

    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button(
            "Continue to Dashboard",
            type="primary",
            use_container_width=True,
            key="renewal_continue",
            icon=":material/arrow_forward:",
        ):
            _reset_renewal_session()
            st.session_state.pop("subscription_context", None)
            st.session_state.pop("grace_info", None)
            st.rerun()


# ============================================================
# EXPIRED SCREEN — TAKEOVER
# ============================================================

def show_expired_screen(
    hospital_name=None,
    plan_name=None,
    end_date=None,
    can_renew=False,
):

    if st.session_state.get(SESSION_RENEWAL_SUCCESS):
        show_renewal_success_screen()
        return

    if st.session_state.get(SESSION_RENEWAL_PAYMENT):
        show_checkout_link_screen()
        return

    if st.session_state.get(SESSION_SHOW_RENEWAL):
        ctx = st.session_state.get("subscription_context", {})
        show_renewal_confirmation_screen(
            hospital_name=hospital_name,
            plan_name=plan_name,
            billing_cycle=ctx.get("billing_cycle"),
            amount=ctx.get("amount"),
            is_expired_screen=True,
        )
        return

    _inject_css()

    st.markdown(
        "<div style='text-align:center; padding:2.5rem 1rem 0.5rem;'>"
        "<span class='material-symbols-rounded' "
        "style='font-size:64px; color:var(--ls-warning);'>lock</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>"
        "Subscription Expired</h2>",
        unsafe_allow_html=True,
    )

    if hospital_name:
        st.markdown(
            "<p style='text-align:center; color:var(--ls-text-soft);'>"
            f"{hospital_name}'s LungSight subscription has expired."
            "</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<p style='text-align:center; color:var(--ls-text-soft);'>"
            "Your hospital's LungSight subscription has expired."
            "</p>",
            unsafe_allow_html=True,
        )

    details = []

    if plan_name:
        details.append(f"Plan: {plan_name}")
    if end_date:
        details.append(f"Expired on: {end_date}")

    if details:
        st.markdown(
            "<p style='text-align:center; color:var(--ls-text-soft); "
            "margin-top:0.5rem;'>"
            + " &nbsp;&bull;&nbsp; ".join(details)
            + "</p>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<p style='text-align:center; color:var(--ls-text-soft); "
        "line-height:1.55;'>"
        "Access is suspended until the subscription is renewed.<br>"
        "Your data is safe and will be restored immediately "
        "upon renewal."
        "</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:

        if can_renew:
            _render_renew_button(key_suffix="expired")
        else:
            st.info(
                "Please contact your Hospital Administrator "
                "to renew."
            )

        if st.button(
            "Log out",
            use_container_width=True,
            key="expired_logout",
            icon=":material/logout:",
        ):
            st.session_state.logged_in = False
            st.session_state.user = None
            _reset_renewal_session()
            st.rerun()


# ============================================================
# GRACE PERIOD BANNER (single-row notification)
# ============================================================

def show_grace_banner(
    end_date,
    days_left,
    hospital_name=None,
    can_renew=False,
):

    # --------------------------------------------------------
    # Renewal sub-flow screens
    # --------------------------------------------------------

    if st.session_state.get(SESSION_RENEWAL_SUCCESS):
        show_renewal_success_screen()
        return

    if st.session_state.get(SESSION_RENEWAL_PAYMENT):
        show_checkout_link_screen()
        return

    if st.session_state.get(SESSION_SHOW_RENEWAL):
        ctx = st.session_state.get("subscription_context", {})
        show_renewal_confirmation_screen(
            hospital_name=hospital_name,
            plan_name=ctx.get("plan_name"),
            billing_cycle=ctx.get("billing_cycle"),
            amount=ctx.get("amount"),
        )
        return

    # --------------------------------------------------------
    # Dismissed?
    # --------------------------------------------------------

    if _is_banner_dismissed():
        return

    # --------------------------------------------------------
    # Inline notification
    # --------------------------------------------------------

    _inject_css()

    day_word = "day" if days_left == 1 else "days"

    if can_renew:

        _render_inline_notification(
            tone="grace",
            icon="warning",
            message=(
                f"Your subscription expired on "
                f"<b>{end_date}</b> &mdash; "
                f"<b>{days_left} {day_word}</b> left in grace period."
            ),
        )

    else:

        st.markdown(
            f"<div class='rn-banner-grace-static'>"
            f"<span class='material-symbols-rounded' "
            f"style='color:var(--ls-warning);'>warning</span> "
            f"Your subscription expired on <b>{end_date}</b>. "
            f"Please contact your Hospital Administrator to renew."
            f"</div>",
            unsafe_allow_html=True,
        )


# ============================================================
# PRE-EXPIRY BANNER (single-row notification)
# ============================================================

def show_pre_expiry_banner(
    end_date,
    days_left,
    hospital_name=None,
    can_renew=False,
):

    # --------------------------------------------------------
    # Renewal sub-flow screens
    # --------------------------------------------------------

    if st.session_state.get(SESSION_RENEWAL_SUCCESS):
        show_renewal_success_screen()
        return

    if st.session_state.get(SESSION_RENEWAL_PAYMENT):
        show_checkout_link_screen()
        return

    if st.session_state.get(SESSION_SHOW_RENEWAL):
        ctx = st.session_state.get("subscription_context", {})
        show_renewal_confirmation_screen(
            hospital_name=hospital_name,
            plan_name=ctx.get("plan_name"),
            billing_cycle=ctx.get("billing_cycle"),
            amount=ctx.get("amount"),
        )
        return

    # --------------------------------------------------------
    # Dismissed?
    # --------------------------------------------------------

    if _is_banner_dismissed():
        return

    # --------------------------------------------------------
    # Inline notification
    # --------------------------------------------------------

    _inject_css()

    day_word = "day" if days_left == 1 else "days"

    if can_renew:

        _render_inline_notification(
            tone="info",
            icon="notifications",
            message=(
                f"Your subscription expires in "
                f"<b>{days_left} {day_word}</b> "
                f"(on <b>{end_date}</b>). "
                f"Renew now to avoid interruption."
            ),
        )

    else:

        st.markdown(
            f"<div class='rn-banner-info-static'>"
            f"<span class='material-symbols-rounded' "
            f"style='color:var(--ls-primary);'>notifications</span> "
            f"Your subscription expires in <b>{days_left} {day_word}</b> "
            f"(on <b>{end_date}</b>). Please contact your Hospital "
            f"Administrator to renew."
            f"</div>",
            unsafe_allow_html=True,
        )


# ============================================================
# SUBSCRIPTION WARNINGS (dispatcher)
# ============================================================

def render_subscription_warnings(can_renew=False):

    context = st.session_state.get("subscription_context")

    if not context:
        return

    state = context.get("state")
    days_left = context.get("days_left")
    end_date = context.get("end_date")

    if state == "grace":
        show_grace_banner(
            end_date=end_date,
            days_left=days_left,
            can_renew=can_renew,
        )
        return

    if state == "active" and days_left is not None and 0 <= days_left <= 7:
        show_pre_expiry_banner(
            end_date=end_date,
            days_left=days_left,
            can_renew=can_renew,
        )