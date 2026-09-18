import streamlit as st


# ============================================================
# APPLICATION STEPS
# ============================================================

APPLICATION_STEPS = [
    "Hospital Information",
    "Authorized Representative",
    "Selected Subscription",
    "Hospital Administrator",
    "Agreement",
    "Review & Submit",
]


# ============================================================
# INITIALIZE APPLICATION
# ============================================================

def initialize_application(plan):

    # --------------------------------------------------------
    # If the selected plan changed, create a new application
    # --------------------------------------------------------

    current_plan_id = plan.get("plan_id")

    existing_application = st.session_state.get(
        "client_application"
    )

    existing_plan_id = None

    if existing_application:

        existing_plan_id = (
            existing_application
            .get("subscription", {})
            .get("plan_id")
        )

    # --------------------------------------------------------
    # Initialize only when:
    # 1. No application exists
    # 2. A different plan was selected
    # --------------------------------------------------------

    if (
        existing_application is None
        or existing_plan_id != current_plan_id
    ):

        st.session_state.client_application = {

            "hospital": {},

            "representative": {},

            "subscription": {
                "plan_id": plan.get("plan_id"),
                "plan_name": plan.get("plan_name"),
                "price_monthly": plan.get("price_monthly"),
                "price_yearly": plan.get("price_yearly"),
                "max_users": plan.get("max_users"),
                "max_patients": plan.get("max_patients"),
                "max_xrays_per_month": plan.get(
                    "max_xrays_per_month"
                ),
            },

            "administrator": {},

            "agreement": {},
        }

        # Start at Step 1
        st.session_state.client_application_step = 0

    # --------------------------------------------------------
    # Safety fallback
    # --------------------------------------------------------

    if "client_application_step" not in st.session_state:

        st.session_state.client_application_step = 0


# ============================================================
# CLEAR APPLICATION
# ============================================================

def clear_application():

    st.session_state.pop(
        "client_application",
        None
    )

    st.session_state.pop(
        "client_application_step",
        None
    )

    st.session_state.pop(
        "selected_plan",
        None
    )

    st.session_state.pop(
        "show_application_form",
        None
    )

    st.session_state.pop(
        "application_submitted",
        None
    )


# ============================================================
# PROGRESS INDICATOR
# ============================================================

def render_progress():

    current_step = (
        st.session_state.client_application_step
    )

    total_steps = len(APPLICATION_STEPS)

    st.markdown(
        "### Hospital Application"
    )

    st.progress(
        (current_step + 1) / total_steps
    )

    st.caption(
        f"Step {current_step + 1} of "
        f"{total_steps} — "
        f"{APPLICATION_STEPS[current_step]}"
    )


# ============================================================
# STEP 1
# HOSPITAL INFORMATION
# ============================================================

def render_hospital_information():

    st.subheader(
        "Hospital Information"
    )

    st.caption(
        "Provide the official information of the "
        "hospital or healthcare facility."
    )

    existing_data = (
        st.session_state.client_application[
            "hospital"
        ]
    )

    hospital_types = [
        "Government Hospital",
        "Private Hospital",
        "Medical Center",
        "Other",
    ]

    current_hospital_type = existing_data.get(
        "hospital_type",
        "Government Hospital"
    )

    if current_hospital_type not in hospital_types:

        current_hospital_type = hospital_types[0]

    with st.form(
        "hospital_information_form"
    ):

        hospital_name = st.text_input(
            "Hospital Name *",
            value=existing_data.get(
                "hospital_name",
                ""
            ),
            placeholder="e.g. Mandaue City Hospital"
        )

        hospital_type = st.selectbox(
            "Hospital Type *",
            hospital_types,
            index=hospital_types.index(
                current_hospital_type
            )
        )

        address = st.text_area(
            "Complete Address *",
            value=existing_data.get(
                "address",
                ""
            ),
            placeholder=(
                "Street / Barangay / "
                "City / Province"
            )
        )

        contact_number = st.text_input(
            "Hospital Contact Number *",
            value=existing_data.get(
                "contact_number",
                ""
            ),
            placeholder="+63 9XX XXX XXXX"
        )

        hospital_email = st.text_input(
            "Official Hospital Email *",
            value=existing_data.get(
                "hospital_email",
                ""
            ),
            placeholder="hospital@example.com"
        )

        website = st.text_input(
            "Hospital Website",
            value=existing_data.get(
                "website",
                ""
            ),
            placeholder="https://example.com"
        )

        st.divider()

        submitted = st.form_submit_button(
            "Next",
            use_container_width=True
        )

    if submitted:

        if not hospital_name.strip():

            st.error(
                "Hospital name is required."
            )

            return

        if not address.strip():

            st.error(
                "Hospital address is required."
            )

            return

        if not contact_number.strip():

            st.error(
                "Hospital contact number is required."
            )

            return

        if not hospital_email.strip():

            st.error(
                "Official hospital email is required."
            )

            return

        st.session_state.client_application[
            "hospital"
        ] = {

            "hospital_name":
                hospital_name.strip(),

            "hospital_type":
                hospital_type,

            "address":
                address.strip(),

            "contact_number":
                contact_number.strip(),

            "hospital_email":
                hospital_email.strip(),

            "website":
                website.strip(),
        }

        # Move to Step 2
        st.session_state.client_application_step = 1

        st.rerun()


# ============================================================
# STEP 2
# AUTHORIZED REPRESENTATIVE
# ============================================================

def render_authorized_representative():

    st.subheader(
        "Authorized Representative"
    )

    st.caption(
        "Provide the details of the person authorized "
        "to submit this application on behalf of the hospital."
    )

    existing_data = (
        st.session_state.client_application[
            "representative"
        ]
    )

    with st.form(
        "authorized_representative_form"
    ):

        first_name = st.text_input(
            "First Name *",
            value=existing_data.get(
                "first_name",
                ""
            )
        )

        middle_name = st.text_input(
            "Middle Name",
            value=existing_data.get(
                "middle_name",
                ""
            )
        )

        last_name = st.text_input(
            "Last Name *",
            value=existing_data.get(
                "last_name",
                ""
            )
        )

        position = st.text_input(
            "Position / Designation *",
            value=existing_data.get(
                "position",
                ""
            ),
            placeholder="e.g. Hospital Director"
        )

        contact_number = st.text_input(
            "Contact Number *",
            value=existing_data.get(
                "contact_number",
                ""
            ),
            placeholder="+63 9XX XXX XXXX"
        )

        email = st.text_input(
            "Email Address *",
            value=existing_data.get(
                "email",
                ""
            ),
            placeholder="representative@hospital.org"
        )

        st.divider()

        back_col, next_col = st.columns(2)

        with back_col:

            back = st.form_submit_button(
                "Back",
                use_container_width=True
            )

        with next_col:

            next_button = st.form_submit_button(
                "Next",
                use_container_width=True
            )

    if back:

        st.session_state.client_application_step = 0

        st.rerun()

    if next_button:

        if not first_name.strip():

            st.error(
                "First name is required."
            )

            return

        if not last_name.strip():

            st.error(
                "Last name is required."
            )

            return

        if not position.strip():

            st.error(
                "Position / designation is required."
            )

            return

        if not contact_number.strip():

            st.error(
                "Contact number is required."
            )

            return

        if not email.strip():

            st.error(
                "Email address is required."
            )

            return

        st.session_state.client_application[
            "representative"
        ] = {

            "first_name":
                first_name.strip(),

            "middle_name":
                middle_name.strip(),

            "last_name":
                last_name.strip(),

            "position":
                position.strip(),

            "contact_number":
                contact_number.strip(),

            "email":
                email.strip(),
        }

        # Move to Step 3
        st.session_state.client_application_step = 2

        st.rerun()


# ============================================================
# STEP 3
# SELECTED SUBSCRIPTION
# ============================================================

def render_subscription_confirmation():

    st.subheader(
        "Selected Subscription"
    )

    st.caption(
        "Review the subscription plan selected for "
        "this hospital application."
    )

    subscription = (
        st.session_state.client_application[
            "subscription"
        ]
    )

    st.markdown(
        f"## {subscription.get('plan_name', 'Subscription Plan')}"
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Monthly Price",
            f"₱{float(subscription.get('price_monthly') or 0):,.2f}"
        )

    with col2:

        st.metric(
            "Yearly Price",
            f"₱{float(subscription.get('price_yearly') or 0):,.2f}"
        )

    st.divider()

    st.markdown(
        "### Plan Limits"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        max_users = subscription.get(
            "max_users"
        )

        st.metric(
            "Maximum Users",
            max_users
            if max_users is not None
            else "Unlimited"
        )

    with col2:

        max_patients = subscription.get(
            "max_patients"
        )

        st.metric(
            "Maximum Patients",
            max_patients
            if max_patients is not None
            else "Unlimited"
        )

    with col3:

        max_xrays = subscription.get(
            "max_xrays_per_month"
        )

        st.metric(
            "Monthly X-rays",
            max_xrays
            if max_xrays is not None
            else "Unlimited"
        )

    st.divider()

    st.info(
        "The selected subscription will be associated "
        "with this hospital application. Subscription "
        "activation will be subject to application approval."
    )

    back_col, next_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="subscription_back"
        ):

            st.session_state.client_application_step = 1

            st.rerun()

    with next_col:

        if st.button(
            "Next",
            use_container_width=True,
            key="subscription_next"
        ):

            st.session_state.client_application_step = 3

            st.rerun()


# ============================================================
# STEP 4
# HOSPITAL ADMINISTRATOR
# ============================================================

def render_hospital_administrator():

    st.subheader(
        "Hospital Administrator"
    )

    st.caption(
        "Provide the information of the person who "
        "will manage the LungSight account for the hospital."
    )

    existing_data = (
        st.session_state.client_application[
            "administrator"
        ]
    )

    with st.form(
        "hospital_administrator_form"
    ):

        first_name = st.text_input(
            "First Name *",
            value=existing_data.get(
                "first_name",
                ""
            )
        )

        middle_name = st.text_input(
            "Middle Name",
            value=existing_data.get(
                "middle_name",
                ""
            )
        )

        last_name = st.text_input(
            "Last Name *",
            value=existing_data.get(
                "last_name",
                ""
            )
        )

        email = st.text_input(
            "Administrator Email *",
            value=existing_data.get(
                "email",
                ""
            ),
            placeholder="admin@hospital.org"
        )

        contact_number = st.text_input(
            "Contact Number *",
            value=existing_data.get(
                "contact_number",
                ""
            ),
            placeholder="+63 9XX XXX XXXX"
        )

        st.info(
            "The email address provided here will be "
            "used for the hospital administrator account."
        )

        st.divider()

        back_col, next_col = st.columns(2)

        with back_col:

            back = st.form_submit_button(
                "Back",
                use_container_width=True
            )

        with next_col:

            next_button = st.form_submit_button(
                "Next",
                use_container_width=True
            )

    if back:

        st.session_state.client_application_step = 2

        st.rerun()

    if next_button:

        if not first_name.strip():

            st.error(
                "First name is required."
            )

            return

        if not last_name.strip():

            st.error(
                "Last name is required."
            )

            return

        if not email.strip():

            st.error(
                "Administrator email is required."
            )

            return

        if not contact_number.strip():

            st.error(
                "Contact number is required."
            )

            return

        st.session_state.client_application[
            "administrator"
        ] = {

            "first_name":
                first_name.strip(),

            "middle_name":
                middle_name.strip(),

            "last_name":
                last_name.strip(),

            "email":
                email.strip(),

            "contact_number":
                contact_number.strip(),
        }

        # Move to Step 5
        st.session_state.client_application_step = 4

        st.rerun()


# ============================================================
# STEP 5
# AGREEMENT
# ============================================================

def render_agreement():

    st.subheader(
        "Agreement"
    )

    st.caption(
        "Please review and acknowledge the LungSight "
        "subscription and system usage terms."
    )

    st.markdown(
        """
        ### LungSight Service Agreement

        By proceeding with this application, the hospital
        acknowledges that:

        - The information provided in this application is
          accurate and complete.
        - The selected subscription will be subject to
          approval by the LungSight system administrator.
        - LungSight is intended to support healthcare
          professionals and does not replace professional
          medical judgment.
        - Hospital users are responsible for maintaining
          the confidentiality of their account credentials.
        - Patient information must be handled in accordance
          with applicable privacy and security requirements.
        """
    )

    st.divider()

    agreed = st.checkbox(
        "I have read and agree to the LungSight Service Agreement."
    )

    st.divider()

    back_col, next_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="agreement_back"
        ):

            st.session_state.client_application_step = 3

            st.rerun()

    with next_col:

        if st.button(
            "Next",
            use_container_width=True,
            key="agreement_next"
        ):

            if not agreed:

                st.error(
                    "You must agree to the service agreement "
                    "before continuing."
                )

                return

            st.session_state.client_application[
                "agreement"
            ] = {
                "agreed": True
            }

            st.session_state.client_application_step = 5

            st.rerun()


# ============================================================
# STEP 6
# REVIEW & SUBMIT
# ============================================================

def render_review_submit():

    st.subheader(
        "Review Application"
    )

    st.caption(
        "Please review the information below before "
        "submitting your hospital application."
    )

    application = (
        st.session_state.client_application
    )

    # ========================================================
    # HOSPITAL
    # ========================================================

    st.markdown(
        "### 1. Hospital Information"
    )

    hospital = application["hospital"]

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
        f"**Hospital Email:** "
        f"{hospital.get('hospital_email', '-')}"
    )

    if hospital.get("website"):

        st.write(
            f"**Website:** "
            f"{hospital.get('website')}"
        )

    st.divider()

    # ========================================================
    # REPRESENTATIVE
    # ========================================================

    st.markdown(
        "### 2. Authorized Representative"
    )

    representative = application[
        "representative"
    ]

    st.write(
        f"**Name:** "
        f"{representative.get('first_name', '')} "
        f"{representative.get('middle_name', '')} "
        f"{representative.get('last_name', '')}"
    )

    st.write(
        f"**Position:** "
        f"{representative.get('position', '-')}"
    )

    st.write(
        f"**Contact:** "
        f"{representative.get('contact_number', '-')}"
    )

    st.write(
        f"**Email:** "
        f"{representative.get('email', '-')}"
    )

    st.divider()

    # ========================================================
    # SUBSCRIPTION
    # ========================================================

    st.markdown(
        "### 3. Selected Subscription"
    )

    subscription = application[
        "subscription"
    ]

    st.write(
        f"**Plan:** "
        f"{subscription.get('plan_name', '-')}"
    )

    st.write(
        f"**Monthly Price:** "
        f"₱{float(subscription.get('price_monthly') or 0):,.2f}"
    )

    st.write(
        f"**Yearly Price:** "
        f"₱{float(subscription.get('price_yearly') or 0):,.2f}"
    )

    st.divider()

    # ========================================================
    # ADMINISTRATOR
    # ========================================================

    st.markdown(
        "### 4. Hospital Administrator"
    )

    administrator = application[
        "administrator"
    ]

    st.write(
        f"**Name:** "
        f"{administrator.get('first_name', '')} "
        f"{administrator.get('middle_name', '')} "
        f"{administrator.get('last_name', '')}"
    )

    st.write(
        f"**Email:** "
        f"{administrator.get('email', '-')}"
    )

    st.write(
        f"**Contact:** "
        f"{administrator.get('contact_number', '-')}"
    )

    st.divider()

    # ========================================================
    # AGREEMENT
    # ========================================================

    st.markdown(
        "### 5. Agreement"
    )

    if application["agreement"].get("agreed"):

        st.success(
            "Service agreement accepted."
        )

    else:

        st.warning(
            "Service agreement has not been accepted."
        )

    st.divider()

    # ========================================================
    # ACTIONS
    # ========================================================

    back_col, submit_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="review_back"
        ):

            st.session_state.client_application_step = 4

            st.rerun()

    with submit_col:

        if st.button(
            "Submit Application",
            use_container_width=True,
            type="primary",
            key="submit_application"
        ):

            st.session_state.application_submitted = True

            st.rerun()


# ============================================================
# APPLICATION SUBMITTED
# ============================================================

def render_application_submitted():

    st.success(
        "Application submitted successfully."
    )

    st.markdown(
        """
        ### What happens next?

        Your hospital application will be reviewed by
        the LungSight system administrator.

        Once approved:

        1. Your hospital record will be created.
        2. The selected subscription will be assigned.
        3. The hospital administrator account will be created.
        4. Login credentials will be sent to the
           administrator's registered email address.
        """
    )

    st.info(
        "Test submission rani paker"
        "Unya na ang database"
    )

    if st.button(
        "Close",
        use_container_width=True
    ):

        clear_application()

        st.rerun()


# ============================================================
# MAIN APPLICATION DIALOG
# ============================================================

@st.dialog(
    "LungSight Hospital Application",
    width="large"
)
def show_client_application(plan):

    # --------------------------------------------------------
    # Initialize
    # --------------------------------------------------------

    initialize_application(plan)

    # --------------------------------------------------------
    # Submitted screen
    # --------------------------------------------------------

    if st.session_state.get(
        "application_submitted",
        False
    ):

        render_application_submitted()

        return

    # --------------------------------------------------------
    # Progress
    # --------------------------------------------------------

    render_progress()

    st.divider()

    current_step = (
        st.session_state.client_application_step
    )

    # --------------------------------------------------------
    # Route current step
    # --------------------------------------------------------

    if current_step == 0:

        render_hospital_information()

    elif current_step == 1:

        render_authorized_representative()

    elif current_step == 2:

        render_subscription_confirmation()

    elif current_step == 3:

        render_hospital_administrator()

    elif current_step == 4:

        render_agreement()

    elif current_step == 5:

        render_review_submit()