import streamlit as st

from backend.hospital_utils import (
    get_hospital_by_id,
    update_hospital_information,
    complete_hospital_setup,
)

from backend.subscription_utils import (
    get_hospital_subscription_details,
)


# ============================================================
# SETUP STEPS
# ============================================================

SETUP_STEPS = [
    "Hospital Profile",
    "Your Administrator Account",
    "Your Subscription",
    "Review & Confirm",
]


# ============================================================
# INITIALIZE SETUP
# ============================================================

def initialize_setup():

    if "setup_step" not in st.session_state:

        st.session_state.setup_step = 0


# ============================================================
# GET CURRENT USER
# ============================================================

def get_current_user():

    return st.session_state.get("user")


# ============================================================
# GET HOSPITAL
# ============================================================

def get_current_hospital():

    user = get_current_user()

    if not user:

        return None

    hospital_id = user.get("hospital_id")

    if not hospital_id:

        return None

    return get_hospital_by_id(hospital_id)


# ============================================================
# PROGRESS
# ============================================================

def render_progress():

    current_step = st.session_state.setup_step

    total_steps = len(SETUP_STEPS)

    st.progress(
        (current_step + 1) / total_steps
    )

    st.caption(
        f"Step {current_step + 1} of "
        f"{total_steps} — "
        f"{SETUP_STEPS[current_step]}"
    )


# ============================================================
# STEP 1
# HOSPITAL PROFILE
# ============================================================

def render_hospital_profile(hospital):

    st.subheader("Hospital Profile")

    st.caption(
        "Review and confirm your hospital's information."
    )

    hospital_name = st.text_input(
        "Hospital Name *",
        value=hospital.get("hospital_name", ""),
        key="setup_hospital_name",
    )

    hospital_type_options = [
        "Government Hospital",
        "Private Hospital",
        "Medical Center",
        "Other",
    ]

    current_type = hospital.get("hospital_type")

    if current_type not in hospital_type_options:

        current_type = hospital_type_options[0]

    hospital_type = st.selectbox(
        "Hospital Type *",
        hospital_type_options,
        index=hospital_type_options.index(current_type),
        key="setup_hospital_type",
    )

    address = st.text_area(
        "Complete Address *",
        value=hospital.get("address", ""),
        key="setup_hospital_address",
    )

    contact_number = st.text_input(
        "Contact Number",
        value=hospital.get("contact_number", "") or "",
        key="setup_hospital_contact",
    )

    email = st.text_input(
        "Hospital Email",
        value=hospital.get("email", "") or "",
        key="setup_hospital_email",
    )

    website = st.text_input(
        "Hospital Website",
        value=hospital.get("website", "") or "",
        key="setup_hospital_website",
    )

    st.divider()

    if st.button(
        "Save & Continue",
        type="primary",
        use_container_width=True,
        key="setup_hospital_next",
    ):

        if not hospital_name.strip():

            st.error("Hospital name is required.")

            return

        if not address.strip():

            st.error("Hospital address is required.")

            return

        result = update_hospital_information(

            hospital_id=hospital.get("hospital_id"),

            hospital_name=hospital_name,

            hospital_type=hospital_type,

            address=address,

            contact_number=contact_number,

            email=email,

            website=website,
        )

        if not result["success"]:

            st.error(result["message"])

            return

        st.session_state.setup_step = 1

        st.rerun()


# ============================================================
# STEP 2
# YOUR ADMINISTRATOR ACCOUNT (READ-ONLY)
# ============================================================

def render_administrator_profile():

    user = get_current_user()

    st.subheader("Your Administrator Account")

    st.caption(
        "This is the account you're currently signed in as. "
        "Contact your system administrator if any details "
        "are incorrect."
    )

    if not user:

        st.error(
            "Administrator information could not be found."
        )

        return

    # --------------------------------------------------------
    # Build full name
    # --------------------------------------------------------

    full_name = " ".join(
        filter(
            None,
            [
                user.get("first_name"),
                user.get("middle_name"),
                user.get("last_name"),
            ],
        )
    )

    if not full_name:

        full_name = user.get("name") or "-"

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    st.write(f"**Name:** {full_name}")

    st.write(f"**Email:** {user.get('email', '-')}")

    st.write(
        f"**Contact Number:** "
        f"{user.get('contact_number') or '-'}"
    )

    st.divider()

    back_col, next_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="setup_admin_back",
        ):

            st.session_state.setup_step = 0

            st.rerun()

    with next_col:

        if st.button(
            "Continue",
            type="primary",
            use_container_width=True,
            key="setup_admin_next",
        ):

            st.session_state.setup_step = 2

            st.rerun()


# ============================================================
# STEP 3
# YOUR SUBSCRIPTION (READ-ONLY)
# ============================================================

def render_subscription_summary(hospital):

    st.subheader("Your Subscription")

    st.caption(
        "Here's the LungSight plan your hospital is "
        "subscribed to."
    )

    subscription = get_hospital_subscription_details(
        hospital.get("hospital_id")
    )

    if not subscription:

        st.warning(
            "No subscription information could be found "
            "for your hospital. Please contact support."
        )

        st.divider()

        if st.button(
            "Back",
            use_container_width=True,
            key="setup_subscription_back",
        ):

            st.session_state.setup_step = 1

            st.rerun()

        return

    # --------------------------------------------------------
    # Plan header
    # --------------------------------------------------------

    st.markdown(
        f"## {subscription.get('plan_name') or 'Subscription Plan'}"
    )

    description = subscription.get("description")

    if description:

        st.caption(description)

    st.divider()

    # --------------------------------------------------------
    # Billing cycle + price
    # --------------------------------------------------------

    billing_cycle = subscription.get("billing_cycle", "Monthly")

    if billing_cycle == "Yearly":

        amount = float(
            subscription.get("price_yearly") or 0
        )

        price_label = "₱{:,.2f} / year".format(amount)

    else:

        amount = float(
            subscription.get("price_monthly") or 0
        )

        price_label = "₱{:,.2f} / month".format(amount)

    col1, col2 = st.columns(2)

    with col1:

        st.metric("Billing Cycle", billing_cycle)

    with col2:

        st.metric("Price", price_label)

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    st.markdown("### Subscription Period")

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Start Date:** "
            f"{subscription.get('start_date') or '-'}"
        )

    with col2:

        st.write(
            f"**End Date:** "
            f"{subscription.get('end_date') or '-'}"
        )

    # --------------------------------------------------------
    # Plan limits
    # --------------------------------------------------------

    st.markdown("### Plan Limits")

    col1, col2, col3 = st.columns(3)

    max_users = subscription.get("max_users")

    max_patients = subscription.get("max_patients")

    max_xrays = subscription.get("max_xrays_per_month")

    with col1:

        st.metric(
            "Maximum Users",
            "Unlimited" if max_users is None else f"{max_users:,}",
        )

    with col2:

        st.metric(
            "Maximum Patients",
            "Unlimited" if max_patients is None else f"{max_patients:,}",
        )

    with col3:

        st.metric(
            "Monthly X-rays",
            "Unlimited" if max_xrays is None else f"{max_xrays:,}",
        )

    st.divider()

    # --------------------------------------------------------
    # Navigation
    # --------------------------------------------------------

    back_col, next_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="setup_subscription_back",
        ):

            st.session_state.setup_step = 1

            st.rerun()

    with next_col:

        if st.button(
            "Continue",
            type="primary",
            use_container_width=True,
            key="setup_subscription_next",
        ):

            st.session_state.setup_step = 3

            st.rerun()


# ============================================================
# STEP 4
# REVIEW & CONFIRM
# ============================================================

def render_review(hospital):

    st.subheader("Review & Confirm")

    st.caption(
        "Review your setup information before activating "
        "your LungSight hospital account."
    )

    # ========================================================
    # HOSPITAL
    # ========================================================

    st.markdown("### Hospital Profile")

    st.write(
        f"**Hospital Name:** "
        f"{hospital.get('hospital_name', '-')}"
    )

    st.write(
        f"**Hospital Type:** "
        f"{hospital.get('hospital_type', '-')}"
    )

    st.write(
        f"**Address:** "
        f"{hospital.get('address', '-')}"
    )

    st.write(
        f"**Contact Number:** "
        f"{hospital.get('contact_number', '-')}"
    )

    st.write(
        f"**Email:** "
        f"{hospital.get('email', '-')}"
    )

    st.divider()

    # ========================================================
    # ADMINISTRATOR (read-only, from logged-in user)
    # ========================================================

    st.markdown("### Your Administrator Account")

    user = get_current_user() or {}

    admin_full_name = " ".join(
        filter(
            None,
            [
                user.get("first_name"),
                user.get("middle_name"),
                user.get("last_name"),
            ],
        )
    )

    if not admin_full_name:

        admin_full_name = user.get("name") or "-"

    st.write(f"**Name:** {admin_full_name}")

    st.write(f"**Email:** {user.get('email', '-')}")

    st.write(
        f"**Contact Number:** "
        f"{user.get('contact_number') or '-'}"
    )

    st.divider()

    # ========================================================
    # SUBSCRIPTION
    # ========================================================

    st.markdown("### Your Subscription")

    subscription = get_hospital_subscription_details(
        hospital.get("hospital_id")
    )

    if subscription:

        st.write(
            f"**Plan:** "
            f"{subscription.get('plan_name') or '-'}"
        )

        st.write(
            f"**Billing Cycle:** "
            f"{subscription.get('billing_cycle') or '-'}"
        )

        billing_cycle = subscription.get("billing_cycle")

        if billing_cycle == "Yearly":

            amount = float(
                subscription.get("price_yearly") or 0
            )

        else:

            amount = float(
                subscription.get("price_monthly") or 0
            )

        st.write(f"**Price:** ₱{amount:,.2f}")

    else:

        st.warning("Subscription information not available.")

    st.divider()

    # ========================================================
    # CONFIRMATION
    # ========================================================

    confirmation = st.checkbox(
        "I have reviewed the information above and "
        "confirm that it is correct.",
        key="setup_final_confirmation",
    )

    st.divider()

    back_col, complete_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="setup_review_back",
        ):

            st.session_state.setup_step = 2

            st.rerun()

    with complete_col:

        if st.button(
            "Complete Setup",
            type="primary",
            use_container_width=True,
            key="setup_complete",
        ):

            if not confirmation:

                st.error(
                    "Please confirm that the information is "
                    "correct before completing setup."
                )

                return

            result = complete_hospital_setup(
                hospital.get("hospital_id")
            )

            if not result["success"]:

                st.error(result["message"])

                return

            st.session_state.setup_completed = True

            st.session_state.pop("setup_step", None)

            st.session_state.pop(
                "setup_final_confirmation", None
            )

            st.success(
                "Hospital setup completed successfully!"
            )

            st.info(
                "Your LungSight subscription is now active."
            )

            st.rerun()


# ============================================================
# MAIN SETUP WIZARD
# ============================================================

def show():

    # --------------------------------------------------------
    # Initialize
    # --------------------------------------------------------

    initialize_setup()

    # --------------------------------------------------------
    # Get hospital
    # --------------------------------------------------------

    hospital = get_current_hospital()

    if not hospital:

        st.error(
            "Hospital information could not be found."
        )

        return

    # --------------------------------------------------------
    # Already completed
    # --------------------------------------------------------

    if hospital.get("setup_completed", False):

        st.success(
            "Hospital setup has already been completed."
        )

        return

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    st.title("Welcome to LungSight")

    st.write(
        "Let's complete your hospital setup before "
        "you start using the LungSight system."
    )

    st.divider()

    # --------------------------------------------------------
    # Progress
    # --------------------------------------------------------

    render_progress()

    st.divider()

    # --------------------------------------------------------
    # Current step
    # --------------------------------------------------------

    current_step = st.session_state.setup_step

    if current_step == 0:

        render_hospital_profile(hospital)

    elif current_step == 1:

        render_administrator_profile()

    elif current_step == 2:

        render_subscription_summary(hospital)

    elif current_step == 3:

        render_review(hospital)