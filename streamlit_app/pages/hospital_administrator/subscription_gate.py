import streamlit as st


# ============================================================
# SESSION KEYS
# ============================================================

SESSION_SHOW_RENEWAL      = "show_renewal_screen"
SESSION_RENEWAL_PAYMENT   = "renewal_payment_id"
SESSION_RENEWAL_URL       = "renewal_checkout_url"
SESSION_RENEWAL_SUCCESS   = "renewal_success"


# ============================================================
# HELPERS
# ============================================================

def _reset_renewal_session():
    """
    Clears all renewal-related session keys.
    Called on cancel, after success, and on logout.
    """

    for key in (
        SESSION_SHOW_RENEWAL,
        SESSION_RENEWAL_PAYMENT,
        SESSION_RENEWAL_URL,
        SESSION_RENEWAL_SUCCESS,
    ):

        st.session_state.pop(key, None)


def _start_renewal_flow():
    """
    Called when the user clicks Renew.
    Sets the flag to show the confirmation screen.
    """

    st.session_state[SESSION_SHOW_RENEWAL] = True

    st.rerun()


# ============================================================
# RENEW BUTTON
# ============================================================

def _render_renew_button(key_suffix="default"):
    """
    Real renew button. Kicks off the confirmation screen.
    """

    if st.button(
        "Renew Subscription",
        type="primary",
        use_container_width=True,
        key=f"renew_button_{key_suffix}",
        icon=":material/autorenew:",
    ):

        _start_renewal_flow()


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
    """
    Shown after the user clicks Renew. Confirms what they're
    about to pay for, then sends them to PayMongo.

    Args:
        hospital_name:      str | None
        plan_name:          str | None
        billing_cycle:      str | None
        amount:             float | None
        is_expired_screen:  bool — if True, this is a takeover screen
                                    (expired state); if False, it's a
                                    full-page confirmation
    """

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>"
        "Renew Subscription"
        "</h2>",
        unsafe_allow_html=True,
    )

    if hospital_name:

        st.markdown(
            "<p style='text-align:center; color:#5A6F7F; "
            "margin:0 0 1rem;'>"
            f"{hospital_name}"
            "</p>",
            unsafe_allow_html=True,
        )

    st.divider()

    # --------------------------------------------------------
    # Plan details
    # --------------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:

        st.write(f"**Plan:** {plan_name or '—'}")

    with col2:

        st.write(f"**Billing Cycle:** {billing_cycle or '—'}")

    if amount is not None:

        st.metric(
            "Amount Due",
            f"₱{amount:,.2f}",
        )

    st.divider()

    # --------------------------------------------------------
    # Actions
    # --------------------------------------------------------

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
    """
    Calls create_renewal_checkout_session() and stores the
    result in session state. Then reruns so the checkout
    link screen renders.
    """

    from backend.payments import create_renewal_checkout_session

    subscription_id = st.session_state.get(
        "subscription_context", {}
    ).get("subscription_id")

    # Fallback: if we don't have it cached, error out
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
    """
    Shown after the checkout session is created. Gives the
    user a link to PayMongo and a Refresh Status button.
    """

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
            f"background:#0F7C88; color:#FFFFFF; "
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
    """
    Shown after the payment is confirmed.
    """

    st.markdown(
        "<div style='text-align:center; margin-bottom:0.5rem;'>"
        "<span class='material-symbols-rounded' "
        "style='font-size:56px; color:#2E8B6A;'>"
        "check_circle"
        "</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>"
        "Subscription Renewed"
        "</h2>",
        unsafe_allow_html=True,
    )

    st.success(
        "Your payment was received and your subscription "
        "has been renewed."
    )

    st.info(
        "Your new billing period will be reflected "
        "shortly. You can continue using LungSight."
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

            # Force a fresh subscription context on next rerun
            st.session_state.pop("subscription_context", None)

            st.session_state.pop("grace_info", None)

            st.rerun()


# ============================================================
# EXPIRED SCREEN — FULL PAGE TAKEOVER
# ============================================================

def show_expired_screen(
    hospital_name=None,
    plan_name=None,
    end_date=None,
    can_renew=False,
):
    """
    Full-page block shown when a hospital's subscription
    has passed the grace period.
    """

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

        # Get amount from cached context

        ctx = st.session_state.get("subscription_context", {})

        show_renewal_confirmation_screen(
            hospital_name=hospital_name,
            plan_name=plan_name,
            billing_cycle=ctx.get("billing_cycle"),
            amount=ctx.get("amount"),
            is_expired_screen=True,
        )

        return

    # --------------------------------------------------------
    # Default expired screen
    # --------------------------------------------------------

    st.markdown(
        "<style>"
        "@import url('https://fonts.googleapis.com/css2"
        "?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD"
        "@20..48,100..700,0..1,-50..200');"
        ".material-symbols-rounded {"
        "  font-family: 'Material Symbols Rounded';"
        "  font-weight: 400;"
        "  font-style: normal;"
        "  font-size: 24px;"
        "  line-height: 1;"
        "  letter-spacing: normal;"
        "  text-transform: none;"
        "  display: inline-flex;"
        "  align-items: center;"
        "  justify-content: center;"
        "  white-space: nowrap;"
        "  direction: ltr;"
        "  font-feature-settings: 'liga';"
        "  -webkit-font-smoothing: antialiased;"
        "  vertical-align: middle;"
        "}"
        "</style>"
        "<div style='text-align:center; padding:2.5rem 1rem 0.5rem;'>"
        "<span class='material-symbols-rounded' "
        "style='font-size:64px; color:#B45309;'>lock</span>"
        "</div>",
        unsafe_allow_html=True,
    )


    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>"
        "Subscription Expired"
        "</h2>",
        unsafe_allow_html=True,
    )

    if hospital_name:

        st.markdown(
            "<p style='text-align:center; color:#5A6F7F;'>"
            f"{hospital_name}'s LungSight subscription has expired."
            "</p>",
            unsafe_allow_html=True,
        )

    else:

        st.markdown(
            "<p style='text-align:center; color:#5A6F7F;'>"
            "Your hospital's LungSight subscription has expired."
            "</p>",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Detail pills (plan + expiry date)
    # --------------------------------------------------------

    details = []

    if plan_name:
        details.append(f"Plan: {plan_name}")

    if end_date:
        details.append(f"Expired on: {end_date}")

    if details:

        st.markdown(
            "<p style='text-align:center; color:#5A6F7F; "
            "margin-top:0.5rem;'>"
            + " &nbsp;&bull;&nbsp; ".join(details)
            + "</p>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<p style='text-align:center; color:#5A6F7F; "
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
# GRACE BANNER — YELLOW
# ============================================================

def show_grace_banner(
    end_date,
    days_left,
    hospital_name=None,
    can_renew=False,
):
    """
    Yellow banner shown during the grace period.
    """

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
    # Default grace banner
    # --------------------------------------------------------

    day_word = "day" if days_left == 1 else "days"

    st.markdown(
        "<div style='display:flex; gap:0.6rem; align-items:flex-start; "
        "padding:0.75rem 1rem; background:#FEF3C7; "
        "border:1px solid #FCD34D; border-radius:10px; "
        "margin-bottom:1rem;'>"
        "<span class='material-symbols-rounded' "
        "style='color:#B45309; font-size:20px;'>"
        "warning"
        "</span>"
        "<div style='font-size:0.88rem; color:#78350F; "
        "line-height:1.5;'>"
        f"Your subscription expired on <b>{end_date}</b>. "
        f"You have <b>{days_left} {day_word}</b> left in the "
        "grace period. Renew now to avoid losing access."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 1])

    with col2:

        if can_renew:

            _render_renew_button(key_suffix="grace")

        else:

            st.caption(
                "Please contact your Hospital Administrator "
                "to renew."
            )


# ============================================================
# PRE-EXPIRY BANNER — BLUE
# ============================================================

def show_pre_expiry_banner(
    end_date,
    days_left,
    hospital_name=None,
    can_renew=False,
):
    """
    Blue banner shown in the days before a subscription expires.
    """

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
    # Default pre-expiry banner
    # --------------------------------------------------------

    day_word = "day" if days_left == 1 else "days"

    st.markdown(
        "<div style='display:flex; gap:0.6rem; align-items:flex-start; "
        "padding:0.75rem 1rem; background:#E8F4F6; "
        "border:1px solid #CFE7EB; border-radius:10px; "
        "margin-bottom:1rem;'>"
        "<span class='material-symbols-rounded' "
        "style='color:#0F7C88; font-size:20px;'>"
        "notifications"
        "</span>"
        "<div style='font-size:0.88rem; color:#12283A; "
        "line-height:1.5;'>"
        f"Your subscription expires in "
        f"<b>{days_left} {day_word}</b> "
        f"(on <b>{end_date}</b>). "
        "Renew now to avoid interruption."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 1])

    with col2:

        if can_renew:

            _render_renew_button(key_suffix="pre_expiry")

        else:

            st.caption(
                "Please contact your Hospital Administrator "
                "to renew."
            )


# ============================================================
# SUBSCRIPTION WARNINGS (dispatcher)
# ============================================================

def render_subscription_warnings(can_renew=False):
    """
    Renders the appropriate banner based on the cached
    subscription context in st.session_state.
    """

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