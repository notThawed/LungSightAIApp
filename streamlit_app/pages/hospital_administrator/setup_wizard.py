import streamlit as st

from backend.hospital_utils import (
    get_hospital_by_id,
    update_hospital_information,
    complete_hospital_setup
)


# ============================================================
# SETUP STEPS
# ============================================================

SETUP_STEPS = [

    "Hospital Profile",

    "Administrator Profile",

    "Hospital Configuration",

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

    return st.session_state.get(
        "user"
    )


# ============================================================
# GET HOSPITAL
# ============================================================

def get_current_hospital():

    user = get_current_user()

    if not user:

        return None

    hospital_id = user.get(
        "hospital_id"
    )

    if not hospital_id:

        return None

    return get_hospital_by_id(
        hospital_id
    )


# ============================================================
# PROGRESS
# ============================================================

def render_progress():

    current_step = (
        st.session_state.setup_step
    )

    total_steps = len(
        SETUP_STEPS
    )

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

    st.subheader(
        "Hospital Profile"
    )

    st.caption(
        "Review and confirm your hospital's "
        "information."
    )

    hospital_name = st.text_input(
        "Hospital Name *",
        value=hospital.get(
            "hospital_name",
            ""
        ),
        key="setup_hospital_name"
    )

    hospital_type_options = [

        "Government Hospital",

        "Private Hospital",

        "Medical Center",

        "Other",

    ]

    current_type = hospital.get(
        "hospital_type"
    )

    if current_type not in hospital_type_options:

        current_type = (
            hospital_type_options[0]
        )

    hospital_type = st.selectbox(
        "Hospital Type *",
        hospital_type_options,
        index=hospital_type_options.index(
            current_type
        ),
        key="setup_hospital_type"
    )

    address = st.text_area(
        "Complete Address *",
        value=hospital.get(
            "address",
            ""
        ),
        key="setup_hospital_address"
    )

    contact_number = st.text_input(
        "Contact Number",
        value=hospital.get(
            "contact_number",
            ""
        ) or "",
        key="setup_hospital_contact"
    )

    email = st.text_input(
        "Hospital Email",
        value=hospital.get(
            "email",
            ""
        ) or "",
        key="setup_hospital_email"
    )

    # --------------------------------------------------------
    # Website
    #
    # Only show this if your hospitals table eventually
    # contains a website column.
    # --------------------------------------------------------

    website = st.text_input(
        "Hospital Website",
        value=hospital.get(
            "website",
            ""
        ) or "",
        key="setup_hospital_website"
    )

    st.divider()

    if st.button(
        "Save & Continue",
        type="primary",
        use_container_width=True,
        key="setup_hospital_next"
    ):

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

        # ----------------------------------------------------
        # Update hospital
        # ----------------------------------------------------

        result = update_hospital_information(

            hospital_id=hospital.get(
                "hospital_id"
            ),

            hospital_name=
                hospital_name,

            hospital_type=
                hospital_type,

            address=
                address,

            contact_number=
                contact_number,

            email=
                email,

            website=
                website,

        )

        if not result["success"]:

            st.error(
                result["message"]
            )

            return

        st.session_state.setup_step = 1

        st.rerun()


# ============================================================
# STEP 2
# ADMINISTRATOR PROFILE
# ============================================================

def render_administrator_profile():

    user = get_current_user()

    st.subheader(
        "Administrator Profile"
    )

    st.caption(
        "Review the information associated with "
        "your Hospital Administrator account."
    )

    if not user:

        st.error(
            "Administrator information could not be found."
        )

        return

    first_name = st.text_input(
        "First Name *",
        value=user.get(
            "user_fname",
            ""
        ) or "",
        key="setup_admin_first_name"
    )

    middle_name = st.text_input(
        "Middle Name",
        value=user.get(
            "user_mname",
            ""
        ) or "",
        key="setup_admin_middle_name"
    )

    last_name = st.text_input(
        "Last Name *",
        value=user.get(
            "user_lname",
            ""
        ) or "",
        key="setup_admin_last_name"
    )

    email = st.text_input(
        "Email",
        value=user.get(
            "email",
            ""
        ) or "",
        disabled=True,
        key="setup_admin_email"
    )

    contact_number = st.text_input(
        "Contact Number",
        value=user.get(
            "user_contact_number",
            ""
        ) or "",
        key="setup_admin_contact"
    )

    st.info(
        "Your administrator account was created "
        "during the hospital approval process."
    )

    st.divider()

    back_col, next_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="setup_admin_back"
        ):

            st.session_state.setup_step = 0

            st.rerun()

    with next_col:

        if st.button(
            "Save & Continue",
            type="primary",
            use_container_width=True,
            key="setup_admin_next"
        ):

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

            st.session_state.setup_admin_data = {

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

            st.session_state.setup_step = 2

            st.rerun()


# ============================================================
# STEP 3
# HOSPITAL CONFIGURATION
# ============================================================

def render_hospital_configuration():

    st.subheader(
        "Hospital Configuration"
    )

    st.caption(
        "Configure the basic LungSight workflow "
        "for your hospital."
    )

    st.markdown(
        "### Clinical Workflow"
    )

    department = st.selectbox(
        "Primary Department",
        [
            "Radiology",
            "Radiology / Imaging",
            "Other",
        ],
        key="setup_department"
    )

    physician_review_required = st.toggle(
        "Require Physician Review",
        value=True,
        key="setup_physician_review"
    )

    st.caption(
        "AI analysis is intended to support clinical "
        "review. Physician confirmation remains part "
        "of the workflow."
    )

    st.divider()

    st.markdown(
        "### System Preferences"
    )

    ai_assistance = st.toggle(
        "Enable AI Assistance",
        value=True,
        key="setup_ai_assistance"
    )

    st.caption(
        "AI assistance provides analysis to support "
        "authorized healthcare professionals."
    )

    st.divider()

    st.session_state.setup_configuration = {

        "department":
            department,

        "physician_review_required":
            physician_review_required,

        "ai_assistance":
            ai_assistance,

    }

    back_col, next_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="setup_config_back"
        ):

            st.session_state.setup_step = 1

            st.rerun()

    with next_col:

        if st.button(
            "Save & Continue",
            type="primary",
            use_container_width=True,
            key="setup_config_next"
        ):

            st.session_state.setup_step = 3

            st.rerun()


# ============================================================
# STEP 4
# REVIEW & CONFIRM
# ============================================================

def render_review(hospital):

    st.subheader(
        "Review & Confirm"
    )

    st.caption(
        "Review your setup information before "
        "activating your LungSight hospital account."
    )

    # ========================================================
    # HOSPITAL
    # ========================================================

    st.markdown(
        "### Hospital Profile"
    )

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
    # ADMINISTRATOR
    # ========================================================

    st.markdown(
        "### Administrator"
    )

    admin_data = st.session_state.get(
        "setup_admin_data",
        {}
    )

    full_name = " ".join(
        filter(
            None,
            [
                admin_data.get(
                    "first_name"
                ),
                admin_data.get(
                    "middle_name"
                ),
                admin_data.get(
                    "last_name"
                ),
            ]
        )
    )

    st.write(
        f"**Name:** "
        f"{full_name or '-'}"
    )

    st.write(
        f"**Email:** "
        f"{admin_data.get('email', '-')}"
    )

    st.write(
        f"**Contact Number:** "
        f"{admin_data.get('contact_number', '-')}"
    )

    st.divider()

    # ========================================================
    # CONFIGURATION
    # ========================================================

    st.markdown(
        "### Hospital Configuration"
    )

    configuration = st.session_state.get(
        "setup_configuration",
        {}
    )

    st.write(
        f"**Primary Department:** "
        f"{configuration.get('department', '-')}"
    )

    st.write(
        f"**Physician Review Required:** "
        f"{'Yes' if configuration.get('physician_review_required') else 'No'}"
    )

    st.write(
        f"**AI Assistance:** "
        f"{'Enabled' if configuration.get('ai_assistance') else 'Disabled'}"
    )

    st.divider()

    # ========================================================
    # SUBSCRIPTION
    # ========================================================

    st.markdown(
        "### Subscription"
    )

    st.info(
        "Your hospital subscription is currently "
        "Inactive. Completing the setup will activate "
        "the subscription associated with your approved "
        "hospital application."
    )

    st.divider()

    # ========================================================
    # CONFIRMATION
    # ========================================================

    confirmation = st.checkbox(
        "I have reviewed the information above and "
        "confirm that it is correct.",
        key="setup_final_confirmation"
    )

    st.divider()

    back_col, complete_col = st.columns(2)

    with back_col:

        if st.button(
            "Back",
            use_container_width=True,
            key="setup_review_back"
        ):

            st.session_state.setup_step = 2

            st.rerun()

    with complete_col:

        if st.button(
            "Complete Setup",
            type="primary",
            use_container_width=True,
            key="setup_complete"
        ):

            if not confirmation:

                st.error(
                    "Please confirm that the information "
                    "is correct before completing setup."
                )

                return

            # ------------------------------------------------
            # Complete setup
            # ------------------------------------------------

            result = complete_hospital_setup(
                hospital.get(
                    "hospital_id"
                )
            )

            if not result["success"]:

                st.error(
                    result["message"]
                )

                return

            # ------------------------------------------------
            # Store completion state
            # ------------------------------------------------

            st.session_state.setup_completed = True

            # ------------------------------------------------
            # Clear wizard state
            # ------------------------------------------------

            st.session_state.pop(
                "setup_step",
                None
            )

            st.session_state.pop(
                "setup_admin_data",
                None
            )

            st.session_state.pop(
                "setup_configuration",
                None
            )

            st.session_state.pop(
                "setup_final_confirmation",
                None
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

    if hospital.get(
        "setup_completed",
        False
    ):

        st.success(
            "Hospital setup has already been completed."
        )

        return

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    st.title(
        "Welcome to LungSight"
    )

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

    current_step = (
        st.session_state.setup_step
    )

    if current_step == 0:

        render_hospital_profile(
            hospital
        )

    elif current_step == 1:

        render_administrator_profile()

    elif current_step == 2:

        render_hospital_configuration()

    elif current_step == 3:

        render_review(
            hospital
        )